import fcntl
import json
import os
import pty
import re
import select
import ssl
import struct
import subprocess
import termios
import threading
import urllib.parse
import urllib.request
import zipfile

from . import paths, userfs
from .proc import clean_env

DOWNLOAD_CHUNK = 262144
PERCENT_RE = re.compile(rb"(\d{1,3})%")
# flatpak renders "Installing 2/5" and restarts its percentage for every
# operation (each runtime, then the app), so weight them into one bar.
FLATPAK_OP_RE = re.compile(rb"(?:Installing|Updating|Uninstalling)\s+(\d+)/(\d+)")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|[\r\x00-\x08\x0b-\x1f]")
PLUGIN_PARTS = ("homebrew", "plugins")
DESKTOP_PARTS = (".local", "share", "applications")


class Cancelled(Exception):
    pass


# Decky's loader is a PyInstaller bundle whose OpenSSL looks for CA certs at
# the build distro's paths, so the default context can come up empty here.
CA_BUNDLES = (
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/ssl/cert.pem",
)

_ssl_context_cache = None


def _ssl_context():
    global _ssl_context_cache
    if _ssl_context_cache is None:
        context = ssl.create_default_context()
        if not context.cert_store_stats().get("x509_ca"):
            for bundle in CA_BUNDLES:
                try:
                    context.load_verify_locations(bundle)
                    break
                except OSError:
                    continue
        _ssl_context_cache = context
    return _ssl_context_cache


def _request(url):
    return urllib.request.Request(url, headers={
        "User-Agent": "armada-store/1.0",
        "Accept": "application/vnd.github+json, application/json;q=0.9, */*;q=0.5",
    })


def _release_assets(release):
    assets = release.get("assets")
    # GitLab nests downloads as assets.links[]; GitHub and Forgejo use a flat
    # assets[] with browser_download_url.
    if isinstance(assets, dict):
        return [(link.get("name") or "", link.get("url")) for link in assets.get("links") or []]
    return [(asset.get("name") or "", asset.get("browser_download_url")) for asset in assets or []]


# ISO-8601 sorts correctly as a string, so no parsing is needed to order these.
def _release_date(release):
    for key in ("published_at", "released_at", "created_at"):
        value = release.get(key)
        if value:
            return str(value)
    return ""


def resolve_release_asset(releases_url, asset_pattern):
    with urllib.request.urlopen(_request(releases_url), timeout=30, context=_ssl_context()) as resp:
        data = json.load(resp)
    releases = [data] if isinstance(data, dict) else data
    pattern = re.compile(asset_pattern)
    # Prereleases lose to any stable build, but a project that publishes
    # nothing else must stay installable.
    for skip_prerelease in (True, False):
        best = None
        for release in releases:
            if release.get("draft") or (skip_prerelease and release.get("prerelease")):
                continue
            for name, url in _release_assets(release):
                if url and pattern.search(name):
                    # RPCS3's arm64 feed is ordered by tag string, so taking
                    # the head of the list pinned a build a year stale.
                    if best is None or _release_date(release) > best[0]:
                        best = (_release_date(release), release.get("tag_name") or "", url)
                    break
        if best is not None:
            return best[1], best[2], best[0]
    raise RuntimeError("No release asset matched " + asset_pattern)


def _https_only(url):
    if url.lower().startswith("https://"):
        return True
    # Escape hatch for file:// fixtures.
    return os.environ.get("ARMADA_STORE_ALLOW_INSECURE_URLS") == "1"


def download_to(fh, url, cancel, progress):
    if not _https_only(url):
        raise RuntimeError("Refusing non-HTTPS download URL")
    with urllib.request.urlopen(_request(url), timeout=60, context=_ssl_context()) as resp:
        final = resp.geturl() or url
        if not _https_only(final):
            raise RuntimeError("Refusing redirect to non-HTTPS URL")
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            if cancel.is_set():
                raise Cancelled()
            chunk = resp.read(DOWNLOAD_CHUNK)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            progress(done, total)


def _clean_output(raw):
    text = ANSI_RE.sub("\n", raw.decode("utf-8", errors="replace"))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _run_flatpak(args, cancel, on_percent):
    # flatpak renders progress only on a sized tty with TERM set, and
    # --noninteractive suppresses it entirely; -y alone keeps this unattended.
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    env = clean_env({"LC_ALL": "C.UTF-8", "TERM": "xterm"})
    proc = subprocess.Popen(["flatpak", *args], stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    output = b""
    op_index = 0
    op_total = 0
    try:
        while True:
            if cancel.is_set():
                raise Cancelled()
            ready, _, _ = select.select([master], [], [], 0.25)
            if ready:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                output = (output + chunk)[-16384:]
                ops = FLATPAK_OP_RE.findall(chunk)
                if ops:
                    op_index, op_total = int(ops[-1][0]), int(ops[-1][1])
                matches = PERCENT_RE.findall(chunk)
                if matches:
                    percent = min(100, int(matches[-1]))
                    if op_total > 1 and op_index:
                        # Equal weight per operation: sizes are unknown up front,
                        # but the result is continuous across operation changes.
                        percent = int(((op_index - 1) + percent / 100.0) / op_total * 100)
                    on_percent(max(0, min(100, percent)))
            elif proc.poll() is not None:
                break
    finally:
        os.close(master)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        proc.wait()
    return proc.returncode, output


def install_flatpak(ref, cancel, on_percent):
    args = ["install", "--system", "--or-update", "-y", "flathub", ref]
    code, output = _run_flatpak(args, cancel, on_percent)
    if code != 0:
        message = _clean_output(output)
        if "already installed" in message:
            return
        raise RuntimeError(message or "flatpak install failed ({})".format(code))


# Emulator manifests rarely grant removable media, and DuckStation's grants no
# filesystem access at all. Armada mounts cards under /run/media.
BASE_OVERRIDES = ("--filesystem=/run/media", "--filesystem=/media")


# Persistent rather than a `flatpak run` argument: ES-DE launches the flatpak
# export directly, bypassing the Steam shortcut.
def override_flatpak(ref, extra=None):
    result = subprocess.run(
        ["flatpak", "override", "--system", ref, *BASE_OVERRIDES, *(extra or ())],
        capture_output=True,
        timeout=30,
        env=clean_env(),
    )
    if result.returncode != 0:
        message = _clean_output(result.stderr or result.stdout)
        raise RuntimeError(message or "flatpak override failed ({})".format(result.returncode))


def flatpak_location(ref):
    result = subprocess.run(
        ["flatpak", "info", "--show-location", "--system", ref],
        capture_output=True,
        text=True,
        timeout=30,
        env=clean_env(),
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def uninstall_flatpak(ref, cancel):
    code, output = _run_flatpak(["uninstall", "--system", "-y", ref], cancel, lambda p: None)
    if code != 0:
        message = _clean_output(output)
        if "not installed" in message:
            return
        raise RuntimeError(message or "flatpak uninstall failed ({})".format(code))


def install_appimage(install, cancel, progress):
    filename = install["filename"]
    tag = stamp = ""
    url = install.get("url")
    if not url:
        tag, url, stamp = resolve_release_asset(install["releases"], install["asset"])
    home_fd, staging_name, staging_fd = userfs.make_staging("download")
    apps_fd = None
    try:
        with userfs.create_file(staging_fd, filename, 0o755) as fh:
            download_to(fh, url, cancel, progress)
        apps_fd = userfs.open_user_path(["Applications"], create=True)
        userfs.rename(staging_fd, filename, apps_fd, filename)
    finally:
        if apps_fd is not None:
            os.close(apps_fd)
        userfs.cleanup_staging(home_fd, staging_name, staging_fd)
    return filename, tag, stamp


# An AppImage is just a file in ~/Applications, so desktop mode has no other way
# to launch one. Flatpaks export their own entry.
ICON_PARTS = (".local", "share", "icons", "hicolor", "128x128", "apps")
DESKTOP_CATEGORIES = {"emulators": "Game;Emulator;", "applications": "Game;", "plugins": ""}


def _desktop_value(text):
    return str(text or "").replace("\\", "\\\\").replace("\n", " ").strip()


def _icon_name(app_id, url):
    # Extension follows the source: a .svg saved as .png is a broken icon in
    # every menu that trusts the suffix.
    suffix = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    if suffix not in (".png", ".svg", ".jpg", ".jpeg", ".xpm"):
        suffix = ".png"
    return "armada-{}{}".format(app_id, suffix)


def _fetch_icon(app_id, url):
    if not url:
        return ""
    name = _icon_name(app_id, url)
    icons_fd = userfs.open_user_path(list(ICON_PARTS), create=True)
    try:
        with userfs.create_file(icons_fd, name, 0o644) as fh:
            # Deliberately uncancellable: the install is already committed, and
            # aborting here left the app without a desktop entry.
            download_to(fh, url, threading.Event(), lambda done, total: None)
    except Exception:
        userfs.unlink(icons_fd, name)
        return ""
    finally:
        os.close(icons_fd)
    return str(paths.user_home().joinpath(*ICON_PARTS) / name)


def desktop_entry_name(app_id):
    return "armada-{}.desktop".format(app_id)


def write_desktop_entry(app, exec_path):
    app_id = app.get("id") or ""
    icon = _fetch_icon(app_id, app.get("icon"))
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Name=" + _desktop_value(app.get("name") or app_id),
        "Comment=" + _desktop_value(app.get("summary")),
        'Exec="{}"'.format(exec_path),
        "Terminal=false",
        "Categories=" + DESKTOP_CATEGORIES.get(app.get("category") or "", "Game;"),
        # Tags the entry as armada-store's so uninstall never removes a hand-made one.
        "X-Armada-Store=" + app_id,
    ]
    if icon:
        lines.insert(5, "Icon=" + icon)
    desktop_fd = userfs.open_user_path(list(DESKTOP_PARTS), create=True)
    try:
        with userfs.create_file(desktop_fd, desktop_entry_name(app_id), 0o644) as fh:
            fh.write(("\n".join(lines) + "\n").encode("utf-8"))
    finally:
        os.close(desktop_fd)


def remove_desktop_entry(app_id):
    try:
        desktop_fd = userfs.open_user_path(list(DESKTOP_PARTS))
    except FileNotFoundError:
        pass
    else:
        try:
            userfs.unlink(desktop_fd, desktop_entry_name(app_id))
        finally:
            os.close(desktop_fd)
    try:
        icons_fd = userfs.open_user_path(list(ICON_PARTS))
    except FileNotFoundError:
        return
    try:
        for suffix in (".png", ".svg", ".jpg", ".jpeg", ".xpm"):
            userfs.unlink(icons_fd, "armada-{}{}".format(app_id, suffix))
    finally:
        os.close(icons_fd)


def remove_appimage(install, record):
    filename = install.get("filename") or (record or {}).get("filename")
    if not filename or "/" in filename:
        return
    try:
        apps_fd = userfs.open_user_path(["Applications"])
    except FileNotFoundError:
        return
    try:
        userfs.unlink(apps_fd, filename)
    finally:
        os.close(apps_fd)


# RENAME_EXCHANGE keeps the live name pointing at one complete tree even
# across a crash; the park-and-restore fallback only covers exceptions.
def _publish_tree(home_fd, staging_name, staging_fd, dest_fd, dirname, preserved):
    publish_src = "tree/" + dirname
    try:
        userfs.exchange(staging_fd, publish_src, dest_fd, dirname)
        return
    except FileNotFoundError:
        # Nothing at the live name yet: a plain rename is atomic on its own.
        os.rename(publish_src, dirname, src_dir_fd=staging_fd, dst_dir_fd=dest_fd)
        return
    except NotImplementedError:
        pass
    backed_up = False
    try:
        os.rename(dirname, "previous", src_dir_fd=dest_fd, dst_dir_fd=staging_fd)
        backed_up = True
    except FileNotFoundError:
        pass
    try:
        os.rename(publish_src, dirname, src_dir_fd=staging_fd, dst_dir_fd=dest_fd)
    except Exception as publish_error:
        restored = False
        if backed_up:
            try:
                os.rename("previous", dirname, src_dir_fd=staging_fd, dst_dir_fd=dest_fd)
                restored = True
            except OSError:
                pass
        if backed_up and not restored:
            rescue = ".armada-store-recovery-" + os.urandom(3).hex()
            try:
                os.rename(staging_name, rescue, src_dir_fd=home_fd, dst_dir_fd=home_fd)
            except OSError:
                rescue = staging_name
            userfs.grant_user_fd(staging_fd)
            preserved[0] = True
            raise RuntimeError(
                "Install failed and the previous version could not be restored; "
                "backup kept at ~/{}/previous".format(rescue)
            ) from publish_error
        raise


def _extract_zip(archive_path, tree_path, cancel, on_extract):
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        total = len(infos) or 1
        for index, info in enumerate(infos):
            if cancel.is_set():
                raise Cancelled()
            # ZipFile.extract sanitises these silently; a refusal is safer than
            # a member landing somewhere other than where it claims to.
            if info.filename.startswith("/") or ".." in info.filename.split("/"):
                raise RuntimeError("Unsafe archive member: " + info.filename)
            archive.extract(info, tree_path)
            # Zip stores the Unix mode in the high half of external_attr, and
            # the plugin's bundled binaries are useless without the exec bit.
            mode = info.external_attr >> 16
            if mode & 0o111:
                target = os.path.join(tree_path, info.filename)
                os.chmod(target, os.stat(target).st_mode | 0o111)
            if index % 25 == 0:
                on_extract(index, total)
    return [info.filename for info in infos]


def install_decky_plugin(install, cancel, on_download, on_extract):
    tag, url, stamp = resolve_release_asset(install["releases"], install["asset"])
    home_fd, staging_name, staging_fd = userfs.make_staging("plugin")
    plugins_fd = None
    preserved_staging = [False]
    try:
        with userfs.create_file(staging_fd, "archive", 0o600) as fh:
            download_to(fh, url, cancel, on_download)
        os.mkdir("tree", dir_fd=staging_fd)
        tree_path = userfs.proc_path(staging_fd, "tree")
        names = _extract_zip(userfs.proc_path(staging_fd, "archive"), tree_path, cancel, on_extract)
        top = {name.split("/", 1)[0] for name in names if name and not name.startswith((".", "/"))}
        if len(top) != 1:
            raise RuntimeError("Unexpected archive layout: " + ", ".join(sorted(top)[:4]))
        dirname = top.pop()
        userfs.lchown_tree(os.path.join(tree_path, dirname))
        plugins_fd = userfs.open_user_path(list(PLUGIN_PARTS), create=True)
        _publish_tree(home_fd, staging_name, staging_fd, plugins_fd, dirname, preserved_staging)
        return dirname, tag, stamp
    finally:
        if plugins_fd is not None:
            os.close(plugins_fd)
        if preserved_staging[0]:
            for fd in (staging_fd, home_fd):
                try:
                    os.close(fd)
                except OSError:
                    pass
        else:
            userfs.cleanup_staging(home_fd, staging_name, staging_fd)


def remove_decky_plugin(record):
    dirname = (record or {}).get("dir") or ""
    if not dirname or "/" in dirname or dirname in (".", ".."):
        raise RuntimeError("No recorded plugin directory")
    try:
        plugins_fd = userfs.open_user_path(list(PLUGIN_PARTS))
    except FileNotFoundError:
        return
    try:
        userfs.remove_entry(plugins_fd, dirname)
    finally:
        os.close(plugins_fd)


# Decky hot-loads a new plugin but leaves a running one on its old code, so an
# update needs this; the delay lets the job finish before the backend is killed.
def restart_decky():
    subprocess.Popen(
        ["systemd-run", "--collect", "--no-block", "--on-active=5",
         "systemctl", "restart", "plugin_loader.service"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=clean_env(),
    )
