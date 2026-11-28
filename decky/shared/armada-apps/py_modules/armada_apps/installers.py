import fcntl
import hashlib
import json
import os
import re
import select
import ssl
import struct
import subprocess
import tarfile
import termios
import threading
import urllib.parse
import urllib.request
import zipfile

from . import paths, userfs
from .proc import clean_env
from .profile import profile

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
        "User-Agent": "armada/1.0",
        "Accept": "application/vnd.github+json, application/json;q=0.9, */*;q=0.5",
    })


def _release_assets(release):
    assets = release.get("assets")
    # GitLab nests downloads as assets.links[]; GitHub and Forgejo use a flat
    # assets[] with browser_download_url.
    if isinstance(assets, dict):
        return [(link.get("name") or "", link.get("url"), "") for link in assets.get("links") or []]
    return [(asset.get("name") or "", asset.get("browser_download_url"), _asset_date(asset))
            for asset in assets or []]


# ISO-8601 sorts correctly as a string, so no parsing is needed to order these.
def _release_date(release):
    for key in ("published_at", "released_at", "created_at"):
        value = release.get(key)
        if value:
            return str(value)
    return ""


# A fixed-tag release that has its assets replaced keeps its publication date.
def _asset_date(asset):
    for key in ("updated_at", "created_at"):
        value = asset.get(key)
        if value:
            return str(value)
    return ""


def resolve_release(releases_url, asset_pattern, checksum_pattern=None):
    """(tag, asset url, stamp, checksum url) of the newest matching release;
    the checksum file must come from the same release as the asset."""
    with urllib.request.urlopen(_request(releases_url), timeout=30, context=_ssl_context()) as resp:
        data = json.load(resp)
    releases = [data] if isinstance(data, dict) else data
    pattern = re.compile(asset_pattern)
    checksum = re.compile(checksum_pattern) if checksum_pattern else None
    # Prereleases lose to any stable build, but a project that publishes
    # nothing else must stay installable.
    for skip_prerelease in (True, False):
        best = None
        for release in releases:
            if release.get("draft") or (skip_prerelease and release.get("prerelease")):
                continue
            assets = _release_assets(release)
            for name, url, asset_date in assets:
                if url and pattern.search(name):
                    sums = [sum_url for sum_name, sum_url, _ in assets
                            if checksum and sum_url and checksum.search(sum_name)]
                    if checksum and not sums:
                        break
                    # RPCS3's arm64 feed is ordered by tag string, so taking
                    # the head of the list pinned a build a year stale.
                    date = _release_date(release)
                    if best is None or date > best[0]:
                        best = (date, release.get("tag_name") or "", url, asset_date or date,
                                sums[0] if sums else None)
                    break
        if best is not None:
            return best[1], best[2], best[3], best[4]
    raise RuntimeError("No release asset matched " + asset_pattern)


CHECKSUM_LIMIT = 65536
DIGESTS = {64: "sha256", 128: "sha512"}


def expected_digest(text, asset_name):
    """(algorithm, hex digest) for asset_name from a sha256sum or sha512sum
    style file; a file with a single bare digest names no file."""
    found = []
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if not parts:
            continue
        digest = parts[0].lower()
        if len(digest) not in DIGESTS or not re.fullmatch(r"[0-9a-f]+", digest):
            continue
        name = parts[1].lstrip("*").strip() if len(parts) > 1 else ""
        found.append((name, digest))
    named = [digest for name, digest in found if name.rsplit("/", 1)[-1] == asset_name]
    if not named and len(found) == 1 and not found[0][0]:
        named = [found[0][1]]
    if len(named) != 1:
        raise RuntimeError("Checksum file has no entry for " + asset_name)
    return DIGESTS[len(named[0])], named[0]


def verify_download(path, url, checksum_url, cancel):
    if not checksum_url:
        return
    if not _https_only(checksum_url):
        raise RuntimeError("Refusing non-HTTPS checksum URL")
    with urllib.request.urlopen(_request(checksum_url), timeout=30, context=_ssl_context()) as resp:
        if not _https_only(resp.geturl() or checksum_url):
            raise RuntimeError("Refusing redirect to non-HTTPS URL")
        text = resp.read(CHECKSUM_LIMIT + 1)
    if len(text) > CHECKSUM_LIMIT:
        raise RuntimeError("Checksum file too large")
    asset_name = urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/", 1)[-1])
    algorithm, expected = expected_digest(text.decode("utf-8", "replace"), asset_name)
    digest = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        while True:
            if cancel.is_set():
                raise Cancelled()
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise RuntimeError("Download does not match its checksum")


def _https_only(url):
    if url.lower().startswith("https://"):
        return True
    # Escape hatch for file:// fixtures.
    return os.environ.get("ARMADA_ALLOW_INSECURE_URLS") == "1"


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
    master, slave = os.openpty()
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


# Persistent rather than a `flatpak run` argument: a Steam shortcut is not the
# only way an app gets launched.
def override_flatpak(ref, options):
    result = subprocess.run(
        ["flatpak", "override", "--system", ref, *options],
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
        if "not installed" not in message:
            raise RuntimeError(message or "flatpak uninstall failed ({})".format(code))
    # Overrides outlive the app, and a later install from anywhere would
    # inherit them. This also drops manual changes to its system override.
    try:
        subprocess.run(["flatpak", "override", "--system", "--reset", ref],
                       capture_output=True, timeout=30, env=clean_env())
    except (OSError, subprocess.TimeoutExpired):
        pass


def install_appimage(install, cancel, progress):
    filename = install["filename"]
    tag = stamp = ""
    url = install.get("url")
    checksum_url = None
    if not url:
        tag, url, stamp, checksum_url = resolve_release(
            install["releases"], install["asset"], install.get("checksum"))
    home_fd, staging_name, staging_fd = userfs.make_staging("download")
    apps_fd = None
    try:
        with userfs.create_file(staging_fd, filename, 0o755) as fh:
            download_to(fh, url, cancel, progress)
        verify_download(userfs.proc_path(staging_fd, filename), url, checksum_url, cancel)
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
    # The recorded file is what was downloaded; the catalog may have renamed it since.
    filename = (record or {}).get("filename") or install.get("filename")
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
def _publish_tree(home_fd, staging_name, staging_fd, dest_fd, dirname, preserved, source=None):
    publish_src = source or "tree/" + dirname
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
            rescue = ".{}-recovery-{}".format(profile.name, os.urandom(3).hex())
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


def _check_fixed_plugin(expected, dirname, tree):
    """A plugin with a fixed folder replaces whatever is there, maybe the
    image's copy, so the zip must be that plugin and newer than what runs."""
    from .catalog import parse_version

    def manifest_name(folder):
        try:
            with open(os.path.join(folder, "plugin.json"), encoding="utf-8") as fh:
                name = json.load(fh).get("name")
        except (OSError, ValueError, AttributeError):
            return None
        return name if isinstance(name, str) and name else None

    name = manifest_name(tree)
    if dirname != expected or name is None:
        raise RuntimeError("Release is not the {} plugin".format(expected))
    # Boot sync keeps a newer copy, so a mispackaged release would stick.
    installed = manifest_name(str(paths.plugins_dir() / expected))
    if installed is not None and installed != name:
        raise RuntimeError("Release is {}, not {}".format(name, installed))
    try:
        with open(os.path.join(tree, "package.json"), encoding="utf-8") as fh:
            new = parse_version(json.load(fh).get("version"))
    except (OSError, ValueError, AttributeError):
        new = None
    if new is None:
        raise RuntimeError("Release has no plain version in package.json")
    try:
        current = parse_version(json.loads((paths.plugins_dir() / expected / "package.json").read_text("utf-8"))["version"])
    except (OSError, ValueError, KeyError, TypeError):
        current = None
    if current is not None and new <= current:
        raise RuntimeError("Already up to date")


def install_decky_plugin(install, cancel, on_download, on_extract):
    tag, url, stamp, checksum_url = resolve_release(install["releases"], install["asset"], install.get("checksum"))
    home_fd, staging_name, staging_fd = userfs.make_staging("plugin")
    plugins_fd = None
    preserved_staging = [False]
    try:
        with userfs.create_file(staging_fd, "archive", 0o600) as fh:
            download_to(fh, url, cancel, on_download)
        verify_download(userfs.proc_path(staging_fd, "archive"), url, checksum_url, cancel)
        os.mkdir("tree", dir_fd=staging_fd)
        tree_path = userfs.proc_path(staging_fd, "tree")
        names = _extract_zip(userfs.proc_path(staging_fd, "archive"), tree_path, cancel, on_extract)
        top = {name.split("/", 1)[0] for name in names if name and not name.startswith((".", "/"))}
        if len(top) != 1:
            raise RuntimeError("Unexpected archive layout: " + ", ".join(sorted(top)[:4]))
        dirname = top.pop()
        if install.get("dir"):
            _check_fixed_plugin(install["dir"], dirname, os.path.join(tree_path, dirname))
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


def _extract_tar(archive_path, tree_path, cancel, on_extract):
    names = []
    total = os.path.getsize(archive_path) or 1
    with open(archive_path, "rb") as raw, tarfile.open(fileobj=raw, mode="r:*") as archive:
        for index, member in enumerate(archive):
            if cancel.is_set():
                raise Cancelled()
            if member.name.startswith("/") or ".." in member.name.split("/"):
                raise RuntimeError("Unsafe archive member: " + member.name)
            # The data filter refuses links out of the tree, devices and
            # setuid bits, and leaves ownership to lchown_tree.
            archive.extract(member, tree_path, filter="data")
            names.append(member.name)
            if index % 200 == 0:
                on_extract(raw.tell(), total)
    return names


def _extract_archive(archive_path, tree_path, asset_name, cancel, on_extract):
    if asset_name.lower().endswith(".zip"):
        return _extract_zip(archive_path, tree_path, cancel, on_extract)
    return _extract_tar(archive_path, tree_path, cancel, on_extract)


def _inside(tree, path):
    """tree/path, refusing one that resolves outside the tree through a link."""
    folder = os.path.join(tree, path) if path else tree
    real, root = os.path.realpath(folder), os.path.realpath(tree)
    if real != root and not real.startswith(root + os.sep):
        raise RuntimeError("Archive path leaves the archive: " + path)
    return folder


def _proton_payload(tree, names, app_id, path):
    """The tool folder, re-registered under app_id: Steam stores each game's
    pick by the tool's internal name, and releases put the version in it."""
    if path:
        folder = _inside(tree, path)
    else:
        names = [name[2:] if name.startswith("./") else name for name in names]
        top = {name.split("/", 1)[0] for name in names if name and not name.startswith((".", "/"))}
        if len(top) != 1:
            raise RuntimeError("Unexpected archive layout: " + ", ".join(sorted(top)[:4]))
        folder = os.path.join(tree, top.pop())
    manifest = os.path.join(folder, "compatibilitytool.vdf")
    if not (os.path.isfile(os.path.join(folder, "proton")) and os.path.isfile(manifest)):
        raise RuntimeError("Release is not a Proton build")
    with open(manifest, encoding="utf-8", errors="replace") as fh:
        found = re.search(r'"display_name"\s+"([^"\n]*)"', fh.read())
    display = found.group(1) if found else app_id
    with open(manifest, "w", encoding="utf-8") as fh:
        fh.write(PROTON_MANIFEST.format(name=app_id, display=display))
    return folder


PROTON_MANIFEST = """"compatibilitytools"
{{
  "compat_tools"
  {{
    "{name}"
    {{
      "install_path" "."
      "display_name" "{display}"
      "from_oslist" "windows"
      "to_oslist" "linux"
    }}
  }}
}}
"""
TURNIP_LIBRARY = "libvulkan_freedreno.so"
TURNIP_LIBRARY_LIMIT = 128 << 20


def _turnip_payload(tree, install):
    folder = _inside(tree, install.get("path"))
    library = os.path.join(folder, TURNIP_LIBRARY)
    if not os.path.isfile(library) or os.path.islink(library):
        raise RuntimeError("Release has no " + TURNIP_LIBRARY)
    # An Android (bionic) build has the same layout but cannot load here.
    with open(library, "rb") as fh:
        data = fh.read(TURNIP_LIBRARY_LIMIT)
    if not (data[:5] == b"\x7fELF\x02" and data[18:20] == b"\xb7\x00" and b"libc.so.6\0" in data):
        raise RuntimeError("Release has no ARM64 Linux driver")
    return folder


def install_component(app_id, install, cancel, on_download, on_extract):
    """A Proton build or Turnip driver, unpacked into its kind's folder under
    the name app_id, so an update replaces it in place."""
    kind = install["type"]
    tag, url, stamp, checksum_url = resolve_release(install["releases"], install["asset"], install.get("checksum"))
    asset_name = urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/", 1)[-1])
    home_fd, staging_name, staging_fd = userfs.make_staging(kind)
    dest_fd = None
    preserved_staging = [False]
    try:
        with userfs.create_file(staging_fd, "archive", 0o600) as fh:
            download_to(fh, url, cancel, on_download)
        archive = userfs.proc_path(staging_fd, "archive")
        verify_download(archive, url, checksum_url, cancel)
        os.mkdir("tree", dir_fd=staging_fd)
        tree = userfs.proc_path(staging_fd, "tree")
        names = _extract_archive(archive, tree, asset_name, cancel, on_extract)
        os.unlink("archive", dir_fd=staging_fd)
        if kind == "proton":
            payload = _proton_payload(tree, names, app_id, install.get("path"))
        else:
            payload = _turnip_payload(tree, install)
        os.mkdir("out", dir_fd=staging_fd)
        # Resolved, so a path through a link moves the folder, not the link.
        source = os.path.relpath(os.path.realpath(payload), os.path.realpath(userfs.proc_path(staging_fd)))
        os.rename(source, "out/" + app_id, src_dir_fd=staging_fd, dst_dir_fd=staging_fd)
        userfs.lchown_tree(userfs.proc_path(staging_fd, "out/" + app_id))
        dest_fd = userfs.open_user_path(list(paths.COMPONENT_PARTS[kind]), create=True)
        _publish_tree(home_fd, staging_name, staging_fd, dest_fd, app_id, preserved_staging, "out/" + app_id)
        return tag, stamp
    finally:
        if dest_fd is not None:
            os.close(dest_fd)
        if preserved_staging[0]:
            for fd in (staging_fd, home_fd):
                try:
                    os.close(fd)
                except OSError:
                    pass
        else:
            userfs.cleanup_staging(home_fd, staging_name, staging_fd)


def remove_component(kind, app_id):
    if not app_id or "/" in app_id or app_id in (".", ".."):
        raise RuntimeError("Bad component name")
    try:
        dest_fd = userfs.open_user_path(list(paths.COMPONENT_PARTS[kind]))
    except FileNotFoundError:
        return
    try:
        userfs.remove_entry(dest_fd, app_id)
    finally:
        os.close(dest_fd)


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


# For when Decky's own reload is unavailable; the delay lets the call that
# asked for it return before the backend is killed.
def restart_decky():
    subprocess.Popen(
        ["systemd-run", "--collect", "--no-block", "--on-active=5",
         "systemctl", "restart", "plugin_loader.service"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=clean_env(),
    )


def plugin_name(dirname):
    """The name Decky knows an installed plugin by, from its plugin.json."""
    try:
        with open(paths.plugins_dir() / dirname / "plugin.json", encoding="utf-8") as fh:
            name = json.load(fh).get("name")
    except (OSError, ValueError, AttributeError):
        return None
    return name if isinstance(name, str) and name else None
