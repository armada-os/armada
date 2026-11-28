#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
STORE="$ROOT/decky/armada-store"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
# Every block reads the catalog from this checkout, never the network.
export ARMADA_STORE_CATALOG_BASE="$STORE"

SHARED="$ROOT/decky/shared/armada-apps/py_modules"
# The shared engine is copied into each plugin at build time; tests use it in place.
export PYTHONPATH="$SHARED${PYTHONPATH:+:$PYTHONPATH}"
python3 -m compileall -q "$STORE/main.py" "$STORE/py_modules/armada_store" "$SHARED/armada_apps"

# The catalog is data the backend trusts; a typo here breaks every install.
python3 - "$STORE" <<'PY'
import json, re, sys, pathlib
store = pathlib.Path(sys.argv[1])
doc = json.loads((store / "catalog-v1.json").read_text())
apps = doc["apps"]

sys.path.insert(0, str(store / "py_modules"))
import armada_store
from armada_apps import catalog
from armada_store import remote_catalog

assert remote_catalog.CATALOG_FILE == "catalog-v1.json"
assert type(doc["schemaVersion"]) is int and doc["schemaVersion"] == remote_catalog.SCHEMA_VERSION
remote_catalog.parse_catalog((store / "catalog-v1.json").read_bytes())

ids = [a["id"] for a in apps]
assert len(ids) == len(set(ids)), "duplicate app ids"
assert not set(ids) & armada_store.MOVED_TO_EMULATION, set(ids) & armada_store.MOVED_TO_EMULATION

# Categories: every one shown here, names only in the UI's languages.
categories = doc["categories"]
for category in categories:
    assert catalog.category_problem(category) is None, (category, catalog.category_problem(category))
shown = {c["id"] for c in categories}
assert "android" in shown, "the Android section was dropped"
for app in apps:
    assert app["category"] in shown, (app["id"], app["category"])

# Nothing may ask for a Store newer than this one.
version = catalog.store_version()
for item in apps + categories:
    if "minStoreVersion" in item:
        assert catalog.parse_version(item["minStoreVersion"]) <= version, item["id"]

for app in apps:
    install = app["install"]
    kind = install["type"]
    assert kind in catalog.INSTALL_TYPES, (app["id"], kind)
    if kind == "flatpak":
        assert install.get("ref"), app["id"]
    if kind == "system":
        # Owned by the image: the Store only offers it a Steam shortcut.
        assert install.get("exec", "").startswith("/"), app["id"]
        assert not install.get("releases"), app["id"]
    if kind == "appimage":
        assert install.get("filename"), app["id"]
        assert "/" not in install["filename"], app["id"]
    if install.get("asset"):
        re.compile(install["asset"])
    if install.get("checksum"):
        re.compile(install["checksum"])
    # Becomes controller_neptune_<name>.vdf, one of Steam's own templates.
    template = app.get("controllerTemplate")
    if template is not None:
        assert re.fullmatch(r"[a-z0-9_+]+", template), app["id"]
        assert catalog.launch_spec(app)["controllerTemplate"] == template, app["id"]
    else:
        assert "controllerTemplate" not in (catalog.launch_spec(app) or {}), app["id"]
    # A tool that needs Steam closed must never be offered as a Steam shortcut.
    if app.get("desktopOnly"):
        assert catalog.launch_spec(app) is None, app["id"]

# Every shipped entry must pass the Store's own entry check, or it is hidden.
# system entries point into the image, which this checkout is not.
for app in apps:
    if app["install"]["type"] != "system":
        assert catalog.entry_problem(app, shown) is None, (app["id"], catalog.entry_problem(app, shown))

assert any(a.get("desktopOnly") for a in apps), "expected at least one desktop-only entry"
print("catalog: %d apps in %d categories, %d appimage, %d flatpak" % (
    len(apps), len(categories),
    sum(1 for a in apps if a["install"]["type"] == "appimage"),
    sum(1 for a in apps if a["install"]["type"] == "flatpak")))
PY

# The Store grants a Flatpak only what its entry asks for, and uninstalling
# clears that again so a later install never inherits it.
python3 - "$STORE" <<'PY'
import sys, pathlib, threading
store = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(store / "py_modules"))
import armada_store
from armada_apps import installers

sent = []
installers.subprocess.run = lambda argv, **kw: sent.append(argv) or type(
    "R", (), {"returncode": 0, "stderr": b"", "stdout": b""})()
installers.override_flatpak("org.example.App", ["--filesystem=home"])
assert sent[-1] == ["flatpak", "override", "--system", "org.example.App", "--filesystem=home"], sent[-1]

installers._run_flatpak = lambda argv, cancel, on_percent: (0, b"")
installers.uninstall_flatpak("org.example.App", threading.Event())
assert sent[-1] == ["flatpak", "override", "--system", "--reset", "org.example.App"], sent[-1]
# Already gone is fine, and the reset still runs.
installers._run_flatpak = lambda argv, cancel, on_percent: (1, b"error: org.example.Gone not installed")
installers.uninstall_flatpak("org.example.Gone", threading.Event())
assert sent[-1][-1] == "org.example.Gone", sent[-1]
print("overrides: per entry only, reset on uninstall")
PY

# dbus-broker only watches service directories that exist when it starts, so
# the first Flatpak export into a missing one is invisible until the next boot.
python3 - "$ROOT" <<'PY'
import sys, pathlib
rule = pathlib.Path(sys.argv[1]) / "system_files/usr/lib/tmpfiles.d/armada-flatpak-dbus.conf"
assert rule.exists(), "no tmpfiles rule for the flatpak D-Bus service dir"
lines = [l.strip() for l in rule.read_text().splitlines()
         if l.strip() and not l.startswith("#")]
assert lines == ["d /var/lib/flatpak/exports/share/dbus-1/services 0755 root root -"], lines
print("dbus service dir: created at boot so the bus watches it from the start")
PY

# Release selection, against the shapes real forges actually return.
python3 - "$STORE" <<'PY'
import sys, pathlib, json, io
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / "py_modules"))
import armada_store
from armada_apps import installers

def resolve(releases, pattern):
    payload = io.BytesIO(json.dumps(releases).encode())
    payload.geturl = lambda: "https://example.invalid"
    payload.__enter__ = lambda self=payload: self
    payload.__exit__ = lambda *a: False
    installers.urllib.request.urlopen = lambda *a, **k: payload
    return installers.resolve_release("https://example.invalid", pattern)[:3]

def rel(tag, date, asset, prerelease=False):
    return {"tag_name": tag, "published_at": date, "prerelease": prerelease,
            "assets": [{"name": asset, "browser_download_url": "https://x/" + asset}]}

# RPCS3's arm64 feed comes back ordered by tag string, not date, so the newest
# build is not the first entry.
out_of_order = [
    rel("build-ffeb", "2025-09-19T08:53:01Z", "rpcs3-v0.0.37_linux_aarch64.AppImage"),
    rel("build-ff99", "2026-02-20T09:41:40Z", "rpcs3-v0.0.39_linux_aarch64.AppImage"),
    rel("build-ff16", "2026-07-30T15:12:06Z", "rpcs3-v0.0.41_linux_aarch64.AppImage"),
]
tag, url, stamp = resolve(out_of_order, r"^rpcs3-v[0-9].*_linux_aarch64\.AppImage$")
assert "v0.0.41" in url, "picked a stale build: " + url

# Prereleases lose to any stable build, whatever the dates say.
mixed = [
    rel("v2-pre", "2026-08-01T00:00:00Z", "App-v2-aarch64.AppImage", prerelease=True),
    rel("v1", "2026-07-01T00:00:00Z", "App-v1-aarch64.AppImage"),
]
tag, url, stamp = resolve(mixed, r"^App-v[0-9]-aarch64\.AppImage$")
assert tag == "v1", tag
# ...but a project that only ever publishes prereleases stays installable.
tag, url, stamp = resolve([mixed[0]], r"^App-v[0-9]-aarch64\.AppImage$")
assert tag == "v2-pre", tag

# A draft is never a shipping build, so it must lose even to a prerelease.
drafted = [
    dict(rel("v3-draft", "2026-09-01T00:00:00Z", "App-v3-aarch64.AppImage"), draft=True),
    rel("v2-pre", "2026-08-01T00:00:00Z", "App-v2-aarch64.AppImage", prerelease=True),
]
tag, url, stamp = resolve(drafted, r"^App-v[0-9]-aarch64\.AppImage$")
assert tag == "v2-pre", "a draft was selected: " + tag
# A mutable tag ("nightly") never changes, so the release date has to be what
# update detection compares.
assert stamp, "resolver must return a release date"
print("release selection: newest-by-date, prerelease fallback, stamp OK")
PY

# Installer behaviour against real archives, with the network stubbed out.
python3 - "$STORE" "$WORK" <<'PY'
import os, sys, pathlib, threading, zipfile
store, work = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
home = work / "home"
(home / "Applications").mkdir(parents=True)
os.environ["DECKY_USER_HOME"] = str(home)
os.environ["DECKY_USER"] = os.environ.get("USER", "nobody")
os.environ["DECKY_PLUGIN_DIR"] = str(store)
os.environ["ARMADA_STORE_STATE_DIR"] = str(work / "state")
sys.path.insert(0, str(store / "py_modules"))

import armada_store
from armada_apps import installers

# A Decky plugin release, shaped like the real zip: one top-level directory
# with a space in the name and an executable payload.
src = work / "plugin-src" / "Test Plugin"
(src / "bin").mkdir(parents=True)
(src / "plugin.json").write_text('{"name": "Test Plugin"}')
(src / "bin" / "tool").write_text("#!/bin/sh\n")
archive = work / "plugin.zip"
with zipfile.ZipFile(archive, "w") as z:
    for path in sorted(src.rglob("*")):
        info = zipfile.ZipInfo(str(path.relative_to(src.parent)) + ("/" if path.is_dir() else ""))
        info.external_attr = (0o755 if path.name == "tool" else 0o644) << 16
        z.writestr(info, b"" if path.is_dir() else path.read_bytes())

os.environ["ARMADA_ALLOW_INSECURE_URLS"] = "1"
installers.resolve_release = lambda *a, **k: ("v1", archive.as_uri(), "2026-01-01T00:00:00Z", None)
cancel = threading.Event()
noop = lambda *a: None

dirname, tag, stamp = installers.install_decky_plugin({"releases": "x", "asset": "y"}, cancel, noop, noop)
assert dirname == "Test Plugin", dirname
installed = home / "homebrew/plugins/Test Plugin"
assert (installed / "plugin.json").is_file()
assert os.access(installed / "bin/tool", os.X_OK), "zip lost the executable bit"
installers.install_decky_plugin({"releases": "x", "asset": "y"}, cancel, noop, noop)
assert (installed / "plugin.json").is_file(), "reinstall left it half-published"
installers.remove_decky_plugin({"dir": dirname})
assert not installed.exists()

evil = work / "evil.zip"
with zipfile.ZipFile(evil, "w") as z:
    z.writestr("ok/../../escaped", b"x")
installers.resolve_release = lambda *a, **k: ("v1", evil.as_uri(), "2026-01-01T00:00:00Z", None)
try:
    installers.install_decky_plugin({"releases": "x", "asset": "y"}, cancel, noop, noop)
    raise AssertionError("traversing member was accepted")
except RuntimeError as error:
    assert "Unsafe archive member" in str(error), error

# A plugin with a fixed folder (one the image may have seeded) must be that
# plugin, carry a plain version, and be newer than what is installed.
import json
def plugin_zip(name, folder, version, manifest=True):
    path = work / name
    with zipfile.ZipFile(path, "w") as z:
        if manifest:
            z.writestr(folder + "/plugin.json", '{"name": "Fixed"}')
        if version is not None:
            z.writestr(folder + "/package.json", json.dumps({"version": version}))
    return path
fixed = {"releases": "x", "asset": "y", "dir": "fixed-plugin"}
for zip_name, folder, version, manifest, message in (
        ("wrong.zip", "other-plugin", "1.0.0", True, "not the fixed-plugin plugin"),
        ("nomanifest.zip", "fixed-plugin", "1.0.0", False, "not the fixed-plugin plugin"),
        ("noversion.zip", "fixed-plugin", None, True, "no plain version"),
        ("betaversion.zip", "fixed-plugin", "1.0.0-beta", True, "no plain version")):
    archive_path = plugin_zip(zip_name, folder, version, manifest)
    installers.resolve_release = lambda *a, p=archive_path, **k: ("v1", p.as_uri(), "", None)
    try:
        installers.install_decky_plugin(fixed, cancel, noop, noop)
        raise AssertionError("accepted " + zip_name)
    except RuntimeError as error:
        assert message in str(error), (zip_name, error)
seeded = home / "homebrew/plugins/fixed-plugin"
seeded.mkdir(parents=True)
(seeded / "plugin.json").write_text('{"name": "Other"}')
(seeded / "package.json").write_text('{"version": "1.0.0"}')
# A release with another plugin's manifest must not replace this one, or boot
# sync would keep it for its higher version.
archive_path = plugin_zip("impostor.zip", "fixed-plugin", "9.0.0")
installers.resolve_release = lambda *a, p=archive_path, **k: ("v9", p.as_uri(), "", None)
try:
    installers.install_decky_plugin(fixed, cancel, noop, noop)
    raise AssertionError("replaced a plugin with another one")
except RuntimeError as error:
    assert "not Other" in str(error), error
(seeded / "plugin.json").write_text('{"name": "Fixed"}')
(seeded / "package.json").write_text('{"version": "1.2.0"}')
for version, ok in (("1.2", False), ("1.1.9", False), ("1.2.1", True)):
    archive_path = plugin_zip("v%s.zip" % version, "fixed-plugin", version)
    installers.resolve_release = lambda *a, p=archive_path, **k: ("v" + version, p.as_uri(), "", None)
    try:
        installers.install_decky_plugin(fixed, cancel, noop, noop)
        assert ok, "downgraded or reinstalled to " + version
    except RuntimeError as error:
        assert not ok and "Already up to date" in str(error), (version, error)
assert json.loads((seeded / "package.json").read_text())["version"] == "1.2.1"

# Desktop entries: AppImages have no other launcher in desktop mode.
app = {"id": "quiver", "name": "Quiver", "summary": "", "category": "applications", "icon": ""}
installers.write_desktop_entry(app, str(home / "Applications/Quiver.AppImage"))
entry = home / ".local/share/applications/armada-quiver.desktop"
text = entry.read_text()
assert 'Exec="%s"' % (home / "Applications/Quiver.AppImage") in text, text
assert "Categories=Game;" in text and "X-Armada-Store=quiver" in text, text
installers.remove_desktop_entry("quiver")
assert not entry.exists()

# A cancelled job must not stop a committed install from getting its entry.
cancel.set()
installers.write_desktop_entry(app, str(home / "Applications/Quiver.AppImage"))
assert entry.exists(), "cancellation blocked the desktop entry"
cancel.clear()
installers.remove_desktop_entry("quiver")

print("installers: plugin, fixed plugin folder, desktop entry OK")
PY

# Proton builds and Turnip drivers: checksums, archive layouts, the fixed
# folder name, and refusals that must leave nothing behind.
python3 - "$STORE" "$WORK" <<'PY'
import hashlib, io, json, os, sys, pathlib, tarfile, threading, zipfile
store, work = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]) / "components"
home = work / "home"
home.mkdir(parents=True)
os.environ["DECKY_USER_HOME"] = str(home)
os.environ["DECKY_USER"] = os.environ.get("USER", "nobody")
os.environ["DECKY_PLUGIN_DIR"] = str(store)
os.environ["ARMADA_STORE_STATE_DIR"] = str(work / "state")
os.environ["ARMADA_ALLOW_INSECURE_URLS"] = "1"
sys.path.insert(0, str(store / "py_modules"))
import armada_store
from armada_apps import catalog, installers, jobs, records

# Checksum files: sha256sum and sha512sum styles, binary-mode "*", bare digests.
a, b = "a" * 64, "b" * 128
assert installers.expected_digest(a + "  x.zip\n", "x.zip") == ("sha256", a)
assert installers.expected_digest(b + " *dir/x.tar.gz\n", "x.tar.gz") == ("sha512", b)
assert installers.expected_digest(a + "\n", "x.zip") == ("sha256", a)
for text in (a + "  other.zip\n", "", "not a digest  x.zip\n", a + "  x.zip\n" + a + "  x.zip\n"):
    try:
        installers.expected_digest(text, "x.zip")
        raise AssertionError("accepted checksum file: " + repr(text))
    except RuntimeError:
        pass


# The checksum file must come from the asset's own release.
def resolve(releases, asset, checksum):
    payload = io.BytesIO(json.dumps(releases).encode())
    payload.geturl = lambda: "https://example.invalid"
    payload.__enter__ = lambda self=payload: self
    payload.__exit__ = lambda *a: False
    real = installers.urllib.request.urlopen
    installers.urllib.request.urlopen = lambda *a, **k: payload
    try:
        return installers.resolve_release("https://example.invalid", asset, checksum)
    finally:
        installers.urllib.request.urlopen = real


def rel(tag, date, *names):
    return {"tag_name": tag, "published_at": date,
            "assets": [{"name": n, "browser_download_url": "https://x/" + n} for n in names]}


feed = [rel("v2", "2026-02-01T00:00:00Z", "T-v2.zip"),
        rel("v1", "2026-01-01T00:00:00Z", "T-v1.zip", "T-v1.zip.sha256")]
tag, url, stamp, sums = resolve(feed, r"^T-v\d\.zip$", r"^T-v\d\.zip\.sha256$")
assert (tag, sums) == ("v1", "https://x/T-v1.zip.sha256"), (tag, sums)
assert resolve(feed, r"^T-v\d\.zip$", None)[0] == "v2"


def serve(path, digest=None):
    sums = None
    if digest is not None:
        sums = path.with_name(path.name + ".sha256")
        sums.write_text(digest + "  " + path.name + "\n")
    installers.resolve_release = lambda *a, **k: ("v1.0.0", path.as_uri(), "2026-11-26T04:08:30Z",
                                                  sums.as_uri() if sums else None)


cancel = threading.Event()
noop = lambda *a: None


def elf(libc=b"libc.so.6"):
    head = bytearray(64)
    head[:5] = b"\x7fELF\x02"
    head[18:20] = b"\xb7\x00"
    return bytes(head) + b"\0" + libc + b"\0"


# Turnip: the zip carries an Android and a Linux build; only the named folder
# lands, under the app id, with its checksum checked.
turnip = work / "DD-Turnip-v1.0.0.zip"
with zipfile.ZipFile(turnip, "w") as z:
    z.writestr("android/libvulkan_freedreno.so", elf(b"libc.so"))
    z.writestr("android/meta.json", "{}")
    z.writestr("linux/libvulkan_freedreno.so", elf())
    z.writestr("linux/meta.json", '{"name": "DD-Turnip v1.0.0"}')
    z.writestr("manifest.json", "{}")
digest = hashlib.sha256(turnip.read_bytes()).hexdigest()
install = {"type": "turnip", "releases": "x", "asset": "y", "checksum": "z", "path": "linux"}
serve(turnip, digest)
assert installers.install_component("dd-turnip", install, cancel, noop, noop) == ("v1.0.0", "2026-11-26T04:08:30Z")
driver = home / ".local/share/armada/turnip/dd-turnip"
assert sorted(p.name for p in driver.iterdir()) == ["libvulkan_freedreno.so", "meta.json"], list(driver.iterdir())
installers.install_component("dd-turnip", install, cancel, noop, noop)
assert (driver / "libvulkan_freedreno.so").is_file(), "an update left it half-published"
assert not [p for p in home.iterdir() if p.name.startswith(".armada-store-")], "staging left behind"

for case, folder in (("checksum mismatch", "linux"), ("android build", "android"), ("missing folder", "nope")):
    serve(turnip, "0" * 64 if case == "checksum mismatch" else digest)
    try:
        installers.install_component("dd-turnip-2", dict(install, path=folder), cancel, noop, noop)
        raise AssertionError(case + " was accepted")
    except RuntimeError:
        pass
    assert not (driver.parent / "dd-turnip-2").exists(), case + " left a folder"

app = {"id": "dd-turnip", "install": install}
records.record_component("dd-turnip", "v1.0.0", "2026-11-26T04:08:30Z")
assert catalog.installed_info(app, records.load_state(), set()) == {
    "installed": True, "version": "v1.0.0", "date": "2026-11-26T04:08:30Z"}
assert catalog.launch_spec(app) is None, "a driver is not something Steam launches"
assert catalog.removable(app)


# Proton: the tool folder is renamed to the app id and re-registered under it,
# so Steam's per-game pick survives updates whose folder and name carry the
# version. Its display name stays.
def proton(path, folder, extra=()):
    with tarfile.open(path, "w:gz") as tar:
        def add(name, data, mode=0o644):
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), mode
            tar.addfile(info, io.BytesIO(data))
        add(folder + "/proton", b"#!/usr/bin/env python3\n", 0o755)
        add(folder + "/compatibilitytool.vdf",
            b'"compatibilitytools"\n{\n  "compat_tools"\n  {\n    "Foo-Proton-1.2" // Internal name\n'
            b'    {\n      "install_path" "."\n      "display_name" "Foo Proton 1.2"\n'
            b'      "from_oslist"  "windows"\n      "to_oslist"    "linux"\n    }\n  }\n}\n')
        add(folder + "/files/lib/libx.so", b"x")
        link = tarfile.TarInfo(folder + "/files/lib/liby.so")
        link.type, link.linkname = tarfile.SYMTYPE, "libx.so"
        tar.addfile(link)
        for member in extra:
            tar.addfile(member)


tool = work / "Foo-Proton-1.2-aarch64.tar.gz"
proton(tool, "Foo Proton 1.2")
serve(tool)
pinstall = {"type": "proton", "releases": "x", "asset": "y"}
installers.install_component("foo-proton", pinstall, cancel, noop, noop)
dest = home / ".local/share/Steam/compatibilitytools.d/foo-proton"
vdf = (dest / "compatibilitytool.vdf").read_text()
assert '"foo-proton"' in vdf and '"Foo Proton 1.2"' in vdf and "Foo-Proton-1.2" not in vdf, vdf
assert os.access(dest / "proton", os.X_OK), "tar lost the executable bit"
assert (dest / "files/lib/liby.so").is_symlink(), "an in-tree symlink was dropped"

escape = tarfile.TarInfo("Foo Proton 1.2/files/evil")
escape.type, escape.linkname = tarfile.SYMTYPE, "/etc/passwd"
proton(tool, "Foo Proton 1.2", [escape])
serve(tool)
try:
    installers.install_component("foo-proton-2", pinstall, cancel, noop, noop)
    raise AssertionError("an absolute symlink was accepted")
except tarfile.TarError:
    pass
assert not (dest.parent / "foo-proton-2").exists(), "a refused archive left a folder"

two = work / "two.tar.gz"
with tarfile.open(two, "w:gz") as tar:
    for folder in ("a", "b"):
        tar.addfile(tarfile.TarInfo(folder + "/proton"), io.BytesIO(b""))
serve(two)
try:
    installers.install_component("foo-proton-3", pinstall, cancel, noop, noop)
    raise AssertionError("two top-level folders accepted")
except RuntimeError as error:
    assert "Unexpected archive layout" in str(error), error

# path reaches into the archive, also through a link inside it, never out of it.
sysroot = work / "sysroot.tar.gz"
with tarfile.open(sysroot, "w:gz") as tar:
    for name, data in (("./usr/lib64/libvulkan_freedreno.so", elf()), ("./usr/bin/tool", b"x")):
        info = tarfile.TarInfo(name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    link = tarfile.TarInfo("./usr/lib")
    link.type, link.linkname = tarfile.SYMTYPE, "lib64"
    tar.addfile(link)
serve(sysroot)
for path in ("usr/lib64", "usr/lib"):
    installers.install_component("sysroot-turnip", {"type": "turnip", "releases": "x", "asset": "y", "path": path},
                                 cancel, noop, noop)
    got = home / ".local/share/armada/turnip/sysroot-turnip"
    assert not got.is_symlink() and (got / "libvulkan_freedreno.so").is_file(), path
proton(tool, "Foo Proton 1.2")
nested = work / "nested.tar.gz"
with tarfile.open(tool) as src, tarfile.open(nested, "w:gz") as tar:
    for member in src.getmembers():
        member.name = "release/" + member.name
        tar.addfile(member, src.extractfile(member) if member.isfile() else None)
serve(nested)
installers.install_component("nested-proton", dict(pinstall, path="release/Foo Proton 1.2"), cancel, noop, noop)
assert (home / ".local/share/Steam/compatibilitytools.d/nested-proton/proton").is_file()
for bad in ("../x", "/abs", "a//b", "a/./b", "a/../b", "", "a/", "x/" * 9 + "x"):
    entry = {"id": "bad", "name": "Bad", "category": "turnip", "icon": "",
             "install": {"type": "turnip", "releases": "https://x", "asset": "y", "path": bad}}
    assert catalog.entry_problem(entry) == "bad install for turnip", (bad, catalog.entry_problem(entry))

# A driver's path is not an imported APK's: its menu offers Uninstall.
payload = {a["id"]: a for a in catalog.catalog_payload()["apps"]}
assert payload["droiddeck-turnip"]["imported"] is False

# An updated Decky plugin is queued for Decky to reload, under its Decky
# name; a first install is not, since Decky loads new plugins itself.
from armada_apps import userfs
plugins = home / "homebrew/plugins"
(plugins / "Some Plugin").mkdir(parents=True)
(plugins / "Some Plugin/plugin.json").write_text('{"name": "Some Plugin"}')
records.record_plugin("some-plugin", "Some Plugin", "v1", "s1")
real_install = installers.install_decky_plugin
plugin_app = {"id": "some-plugin", "name": "Some", "category": "plugins", "icon": "",
              "install": {"type": "deckyplugin", "releases": "https://x", "asset": "y"}}
installers.install_decky_plugin = lambda *a, **k: ("Some Plugin", "v2", "s2")
job = jobs.Job("some-plugin", "install", plugin_app)
jobs._execute(job)
assert job.phase == "done", job.error
assert jobs.status_payload()["reload"] == ["Some Plugin"], jobs.status_payload()["reload"]
(plugins / "New Plugin").mkdir()
(plugins / "New Plugin/plugin.json").write_text('{"name": "New Plugin"}')
installers.install_decky_plugin = lambda *a, **k: ("New Plugin", "v1", "s1")
jobs._execute(jobs.Job("new-plugin", "install", dict(plugin_app, id="new-plugin")))
installers.install_decky_plugin = real_install
assert records.pending_reloads() == ["Some Plugin"], records.pending_reloads()
records.clear_pending_reload("Some Plugin")
assert records.pending_reloads() == []

# Staging a killed install left behind goes at load; nothing else does.
for name in (".armada-store-proton.4242", ".armada-store-proton.x", ".armada-store-recovery-ab12", ".other-proton.1"):
    (home / name).mkdir()
    (home / name / "file").write_text("x")
userfs.sweep_staging()
assert not (home / ".armada-store-proton.4242").exists()
for name in (".armada-store-proton.x", ".armada-store-recovery-ab12", ".other-proton.1"):
    assert (home / name).exists(), name

# Update checks make the same pick as installs, checksum file included.
from armada_apps import updates
asked = []
real_resolve = updates.resolve_release
updates.resolve_release = lambda releases, asset, checksum=None: asked.append(checksum) or ("v1", "u", "s", None)
assert updates._lookup({"releases": "x", "asset": "y", "checksum": "z"}) == ("v1", "s")
updates.resolve_release = real_resolve
assert asked == ["z"], asked
assert updates._release_key({"releases": "x", "asset": "y"}) != updates._release_key({"releases": "x", "asset": "y", "checksum": "z"})

# An entry's version pattern picks what the panel shows from a release tag;
# without one, or when it doesn't match, the tag shows as it is.
labeled = {"install": {"version": "^GE-Proton(.+)$"}}
assert catalog.version_label(labeled, "GE-Proton11-14") == "11-14"
assert catalog.version_label(labeled, "nightly") == "nightly"
assert catalog.version_label({"install": {}}, "v1.0") == "v1.0"
for bad in ("^GE-Proton.+$", "(", ""):
    entry = {"id": "bad", "name": "Bad", "category": "proton", "icon": "",
             "install": {"type": "proton", "releases": "https://x", "asset": "y", "version": bad}}
    assert catalog.entry_problem(entry) == "bad install for proton", (bad, catalog.entry_problem(entry))
(home / ".local/share/armada/turnip/droiddeck-turnip").mkdir(parents=True)
records.record_component("droiddeck-turnip", "DD-Turnip-v1.0.0", "2026-11-26T04:08:30Z")
assert catalog.installed_map()["droiddeck-turnip"]["version"] == "1.0.0"

# Uninstall through the job runner removes exactly the app's folder.
job = jobs.Job("foo-proton", "uninstall", {"id": "foo-proton", "install": pinstall})
jobs._execute(job)
assert job.phase == "done", job.error
assert not dest.exists() and dest.parent.is_dir()
print("components: checksums, Turnip and Proton layouts, fixed names, refusals, plugin reload, staging sweep OK")
PY

# Launch commands and conflict detection.
python3 - "$STORE" <<'PY'
import os, sys, pathlib, json, tempfile, zipfile
store = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(store / "py_modules"))
import armada_store
from armada_apps import catalog
from armada_store import android, shortcuts

apps = json.loads((store / "catalog-v1.json").read_text())["apps"]
for app in apps:
    for entry in app.get("conflicts") or []:
        assert entry.get("type") in ("flatpak", "appimage"), entry
        assert entry.get("ref") or entry.get("filename"), entry
        # A conflict naming the app's own packaging would replace it forever.
        assert entry.get("ref") != (app["install"].get("ref")), entry

# A bare download URL carries no release date, so update detection has nothing
# to compare and the app can never offer an update.
for app in apps:
    install = app["install"]
    if install["type"] in ("appimage", "deckyplugin"):
        assert install.get("releases"), "%s has no release feed" % app["id"]
        assert install.get("asset"), "%s has no asset pattern" % app["id"]

for app in apps:
    spec = catalog.launch_spec(app)
    if spec:
        options = spec["launchOptions"]
        assert catalog.LAUNCH_WRAPPER in options, (app["id"], options)
        assert options.count(catalog.LAUNCH_WRAPPER) == 1, (app["id"], options)

heroic = catalog.launch_spec(next(a for a in apps if a["id"] == "heroic"))
assert heroic["launchOptions"] == catalog.DEFAULT_LAUNCH_OPTIONS + " --no-sandbox", heroic
flat = catalog.launch_spec({"name": "x", "install": {
    "type": "flatpak", "ref": "org.example.App", "launchOptions": "--foo"}})
assert flat["launchOptions"] == catalog.DEFAULT_LAUNCH_OPTIONS + " run org.example.App --foo", flat
assert catalog.wrap_launch_options("%command% --foo") == catalog.DEFAULT_LAUNCH_OPTIONS + " --foo"
assert catalog.wrap_launch_options(catalog.DEFAULT_LAUNCH_OPTIONS) == catalog.DEFAULT_LAUNCH_OPTIONS
with tempfile.NamedTemporaryFile() as custom:
    prepared = shortcuts.prepare_shortcut(custom.name)
assert prepared["launchOptions"] == catalog.DEFAULT_LAUNCH_OPTIONS, prepared
assert "compatTool" not in prepared, prepared

# APKs run through Lepton (Armada); a renamed non-APK is treated as a plain file.
with tempfile.TemporaryDirectory() as tmp:
    apk = pathlib.Path(tmp, "com.example.game.apk")
    with zipfile.ZipFile(apk, "w") as z:
        z.writestr("AndroidManifest.xml", b"")
    fake = pathlib.Path(tmp, "notes.apk")
    fake.write_text("not a zip")
    android.ANDROID_COMPAT_TOOL_DIR = tmp
    prepared = shortcuts.prepare_shortcut(str(apk))
    assert prepared["compatTool"] == "lepton_armada", prepared
    assert prepared["name"] == "com example game", prepared
    assert prepared["launchOptions"] == catalog.DEFAULT_LAUNCH_OPTIONS, prepared
    assert not os.access(apk, os.X_OK), "an APK must not be made executable"
    assert "compatTool" not in shortcuts.prepare_shortcut(str(fake))
    android.ANDROID_COMPAT_TOOL_DIR = str(pathlib.Path(tmp, "missing"))
    try:
        shortcuts.prepare_shortcut(str(apk))
        raise AssertionError("APK accepted without Lepton (Armada)")
    except ValueError:
        pass

repackaged = {"id": "app", "conflicts": [{"type": "flatpak", "ref": "org.example.Old"}]}
assert catalog.present_conflicts(repackaged, set()) == [], "conflict reported while absent"
present = catalog.present_conflicts(repackaged, {"org.example.Old"})
assert len(present) == 1 and present[0]["type"] == "flatpak", present

print("launch options and conflict detection OK")
PY

# A replacement can finish with the panel closed, so the queued re-add has to
# live in backend state rather than in a job transition the panel might miss.
python3 - "$STORE" <<'PY'
import sys, pathlib, tempfile, os
store_dir = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(store_dir / "py_modules"))
os.environ["ARMADA_STORE_STATE_DIR"] = str(pathlib.Path(tempfile.mkdtemp()))
import armada_store
from armada_apps import records

records.record_shortcut("duckstation", 4242)
assert records.pending_shortcuts() == []

# The ordinary guard skips an app that already has a shortcut; a replacement has
# to queue anyway, because its record still points at the packaging being removed.
records.add_pending_shortcut("duckstation")
assert records.pending_shortcuts() == []
records.add_pending_shortcut("duckstation", force=True)
records.add_pending_shortcut("duckstation", force=True)
assert records.pending_shortcuts() == ["duckstation"], records.pending_shortcuts()

# The old record survives until the new shortcut exists, so the frontend still
# knows which shortcut to remove if the panel reopens mid-swap.
assert records.shortcuts().get("duckstation") == 4242

# The removal phase drops only the record; the add it still owes has to survive,
# or a failure between the two phases loses the shortcut entirely.
records.clear_shortcut("duckstation", keep_pending=True, expected=4242)
assert records.pending_shortcuts() == ["duckstation"], records.pending_shortcuts()
assert "duckstation" not in records.shortcuts()

# That call can land after the swap was cancelled and a new shortcut recorded,
# so it must not delete a record it never set out to remove.
records.record_shortcut("es-de", 1111)
records.add_pending_shortcut("es-de", force=True)
records.clear_shortcut("es-de")
records.record_shortcut("es-de", 2222)
records.clear_shortcut("es-de", keep_pending=True, expected=1111)
assert records.shortcuts().get("es-de") == 2222, records.shortcuts()

records.record_shortcut("duckstation", 5252)
assert records.pending_shortcuts() == []
assert records.shortcuts()["duckstation"] == 5252

# Removing the shortcut by hand cancels a queued add, or it comes straight back.
records.add_pending_shortcut("azahar", force=True)
records.clear_shortcut("azahar")
assert records.pending_shortcuts() == [], records.pending_shortcuts()

# Same for an uninstall, which is the path that runs when removal from Steam failed.
records.record_shortcut("vita3k", 6262)
records.add_pending_shortcut("vita3k", force=True)
records.clear_pending_shortcut("vita3k")
assert records.pending_shortcuts() == [], records.pending_shortcuts()

print("shortcut queue: one list, forced re-add on replace, cancelled on removal")
PY

# The remote catalog: source parsing, fetch and cache, schema version,
# categories, per-entry filtering, and entries kept for apps whose listing
# went away.
python3 - "$STORE" "$WORK" <<'PY'
import email.message, io, json, os, pathlib, sys, time, urllib.error
store, work = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]) / "remote"
home, state, remote, bundled = work / "home", work / "state", work / "remote", work / "bundled-plugins"
for path in (home / "Applications", state, remote, bundled):
    path.mkdir(parents=True)
os.environ.update({"DECKY_USER_HOME": str(home), "DECKY_USER": os.environ.get("USER", "nobody"),
                   "DECKY_PLUGIN_DIR": str(store), "ARMADA_STORE_STATE_DIR": str(state),
                   "ARMADA_STORE_CATALOG_BASE": str(remote),
                   "ARMADA_BUNDLED_PLUGINS": str(bundled),
                   "ARMADA_STORE_OS_VERSION_FILE": str(work / "version")})
sys.path.insert(0, str(store / "py_modules"))
import armada_store
from armada_apps import catalog, jobs, records
from armada_store import remote_catalog as rc

# Sources: the default, a branch, a URL, a directory; junk is refused.
del os.environ["ARMADA_STORE_CATALOG_BASE"]
assert rc.source() == "https://downloads.armadaos.dev/store"
assert rc.parse_source("feature/x") == rc.REPO_RAW.format(branch="feature/x")
assert rc.parse_source("https://example.org/base/") == "https://example.org/base"
assert rc.parse_source("/srv/catalog/") == "/srv/catalog"
for bad in ("../etc", "a/../b", "http://example.org", "a b", "a//b", ""):
    try:
        rc.parse_source(bad)
        raise AssertionError("accepted source " + repr(bad))
    except ValueError:
        pass
# The override must be root-owned and writable by root alone.
override = state / rc.OVERRIDE_FILE
override.write_text(str(remote) + "\n")
if os.geteuid() == 0:
    override.chmod(0o644)
    assert rc.source() == str(remote), "root's override was ignored"
    override.chmod(0o666)
assert rc.source() == rc.DEFAULT_SOURCE, "an unsafe override was honoured"
override.unlink()
override.symlink_to(work / "elsewhere")
assert rc.source() == rc.DEFAULT_SOURCE, "followed a symlinked override"
override.unlink()
os.environ["ARMADA_STORE_CATALOG_BASE"] = str(remote)

APPS = {"id": "applications", "name": {"en": "Applications", "zh-CN": "应用程序"}, "icon": "layout-grid.svg"}
ANDROID = {"id": "android", "name": "Android Apps", "icon": "android.svg"}
def entry(app_id, **extra):
    app = {"id": app_id, "name": app_id.title(), "summary": "", "category": "applications", "icon": "",
           "install": {"type": "system", "exec": "/bin/sh"}}
    app.update(extra)
    return app
def document(apps, categories=None):
    return {"schemaVersion": 1, "categories": [APPS, ANDROID] if categories is None else categories,
            "apps": apps}
def publish(apps, categories=None):
    (remote / rc.CATALOG_FILE).write_text(json.dumps(document(apps, categories)))
    assert rc.refresh() in (True, False)
def shown():
    return [a["id"] for a in catalog.catalog_apps()]

# Offline before any fetch: the bundled catalog.
assert rc.active()["origin"] == "bundled"
assert "moonlight" in shown()

# A fetched catalog replaces the bundled one, judged entry by entry.
store_version = ".".join(map(str, catalog.store_version()))
publish([
    entry("demo"),
    entry("future-type", install={"type": "proton", "releases": "https://x"}),
    entry("future-field", install={"type": "system", "exec": "/bin/sh", "sandbox": "strict"}),
    entry("future-conflict", conflicts=[{"type": "snap", "name": "x"}]),
    entry("conflict-field", conflicts=[{"type": "flatpak", "ref": "org.example.A", "keep": True}]),
    entry("future-category", category="drivers"),
    entry("claims-android", category="android"),
    entry("needs-newer-store", minStoreVersion="99.0"),
    entry("needs-this-store", minStoreVersion=store_version + ".0"),
    entry("bad-version", minStoreVersion="1.0-beta"),
    entry("not-in-image", install={"type": "system", "exec": "/nonexistent/app"}),
    entry("moonlight-ish", summary="ignored", futureDisplayField={"x": 1}),
    entry("retroarch"),
    entry("Bad-Id"),
    {"id": "broken", "install": []},
])
assert rc.active()["origin"] == "remote"
assert shown() == ["demo", "needs-this-store", "moonlight-ish"], shown()

# Categories: hidden when malformed or gated, and their apps with them.
publish([entry("a"), entry("b", category="tools"), entry("c", category="gated"), entry("d", category="badname")],
        [APPS, {"id": "tools", "name": "Tools", "icon": "wrench.svg"},
         {"id": "gated", "name": "Gated", "minStoreVersion": "99"},
         {"id": "badname", "name": {"fr": "Outils"}},
         {"id": "badicon", "name": "X", "icon": "https://example.org/x.svg"},
         {"id": "other", "name": "Reserved"}, ANDROID])
assert [c["id"] for c in catalog.catalog_categories()] == ["applications", "tools", "android"]
assert shown() == ["a", "b"], shown()
# Duplicate category or app ids reject the document, not just the item.
for doc in (document([entry("a")], [APPS, APPS]), document([entry("a"), entry("a")])):
    try:
        rc.parse_catalog(json.dumps(doc))
        raise AssertionError("accepted duplicates")
    except ValueError:
        pass

# The schema version must be exactly this Store's: True and 1.0 both equal 1.
for version in (2, True, 1.0, "1", None):
    try:
        rc.parse_catalog(json.dumps(dict(document([]), schemaVersion=version)))
        raise AssertionError("accepted schemaVersion %r" % (version,))
    except ValueError:
        pass

# Flatpak refs must be application IDs, never flatpak options.
for ref in ("--all", "-y", "org", ""):
    assert catalog.entry_problem(entry("f", install={"type": "flatpak", "ref": ref})), ref
assert catalog.entry_problem(entry("f", install={"type": "flatpak", "ref": "org.example.App"})) is None
assert catalog.entry_problem(entry("f", conflicts=[{"type": "flatpak", "ref": "--all"}]))
assert catalog.entry_problem(entry("f", install={"type": "deckyplugin", "releases": "https://x",
                                                 "asset": "x", "dir": "../up"}))
# Versions compare as numbers, trailing zeros aside.
assert catalog.parse_version("0.2") == catalog.parse_version("0.2.0") < catalog.parse_version("0.10")
assert catalog.parse_version("v1.0") is None and catalog.parse_version("1.0-rc1") is None

# A broken fetch keeps the last good catalog.
publish([entry("demo")])
revision = rc.active()["revision"]
for junk in ('{"schemaVersion": 1, "categories": [], "apps": {}}', "not json",
             json.dumps({"apps": []}), json.dumps(dict(document([]), schemaVersion=2))):
    (remote / rc.CATALOG_FILE).write_text(junk)
    try:
        rc.refresh()
        raise AssertionError("accepted a broken catalog: " + junk)
    except ValueError:
        pass
    assert rc.active()["revision"] == revision
(remote / rc.CATALOG_FILE).write_bytes(b" " * (rc.MAX_CATALOG_BYTES + 1))
try:
    rc.refresh()
    raise AssertionError("accepted an oversized catalog")
except rc.Unavailable:
    pass
publish([entry("demo")])

# An image newer than the last fetch carries a newer catalog: it wins.
(work / "version").write_text(time.strftime("%Y%m%d", time.gmtime(time.time() + 86400 * 2)) + ".abc\n")
assert rc.active()["origin"] == "bundled"
(work / "version").write_text("unknown\n")
assert rc.active()["origin"] == "remote"
# A cache with a damaged envelope falls back instead of failing.
cache_path = state / rc.CACHE_FILE
good = cache_path.read_text()
for bad in ({"fetchedAt": "x"}, {"fetchedAt": 10 ** 30}, {"etag": 5}, {"source": None}):
    cache_path.write_text(json.dumps(dict(json.loads(good), **bad)))
    assert rc.active()["origin"] == "bundled", bad
# A cache from another schema's file is not used, and its ETag is not sent.
cache_path.write_text(json.dumps(dict(json.loads(good), file="catalog-v0.json", etag="old")))
assert rc.active()["origin"] == "bundled"
fetched = []
real_fetch = rc.fetch
rc.fetch = lambda base, rel, limit, etag=None: (rel == rc.CATALOG_FILE and fetched.append(etag)) or real_fetch(base, rel, limit, etag)
rc.refresh()
rc.fetch = real_fetch
assert fetched == [None], fetched
assert rc.active()["origin"] == "remote"
# A cache from another source is not used.
os.environ["ARMADA_STORE_CATALOG_BASE"] = str(work)
assert rc.active()["origin"] == "bundled"
os.environ["ARMADA_STORE_CATALOG_BASE"] = str(remote)

# A renamed AppImage in the catalog still finds and removes the file that was
# installed, by its download record.
import armada_store
from armada_apps import installers
renamed = entry("app", install={"type": "appimage", "releases": "https://example.org/r",
                                 "asset": "^App.*$", "filename": "Old.AppImage"})
(home / "Applications/Old.AppImage").write_text("#!/bin/sh\n")
records.record_appimage("app", "Old.AppImage", "v1")
records.record_entry("app", renamed)
renamed_new = json.loads(json.dumps(renamed))
renamed_new["install"]["filename"] = "New.AppImage"
publish([renamed_new])
current = records.load_state()
assert catalog.installed_info(catalog.find_app("app"), current, set())["installed"]
installers.remove_desktop_entry = lambda app_id: None
(home / "Applications/New.AppImage").write_text("not ours\n")
job = jobs.Job("app", "uninstall", catalog.find_app("app"))
jobs._execute(job)
assert job.phase == "done", job.error
assert not (home / "Applications/Old.AppImage").exists(), "left the installed file behind"
assert (home / "Applications/New.AppImage").exists(), "removed the catalog's new name instead"
(home / "Applications/New.AppImage").unlink()
assert "app" not in (records.load_state().get("entries") or {})

# Only apps Steam can launch are queued for a shortcut; a desktop-only one
# would sit in the queue forever.
saved_flatpak = (installers.install_flatpak, installers.override_flatpak, catalog.invalidate_flatpak_cache)
installers.install_flatpak = lambda ref, cancel, on_percent: None
installers.override_flatpak = lambda ref, options: None
catalog.invalidate_flatpak_cache = lambda: None
publish([entry("gamepad", install={"type": "flatpak", "ref": "org.example.Gamepad"}),
         entry("desk", desktopOnly=True, install={"type": "flatpak", "ref": "org.example.Desk"})])
for app_id, action in (("gamepad", "install"), ("desk", "install"), ("desk", "replace")):
    job = jobs.Job(app_id, action, catalog.find_app(app_id))
    jobs._execute(job)
    assert job.phase == "done", job.error
assert records.pending_shortcuts() == ["gamepad"], records.pending_shortcuts()
records.clear_pending_shortcut("gamepad")
installers.install_flatpak, installers.override_flatpak, catalog.invalidate_flatpak_cache = saved_flatpak

# Installs from before entries existed are adopted on the first status poll,
# and adoption never replaces an entry an install wrote meanwhile.
(home / "Applications/Old.AppImage").write_text("#!/bin/sh\n")
publish([renamed])
records.record_appimage("app", "Old.AppImage", "v1")
assert "app" not in (records.load_state().get("entries") or {})
catalog.installed_map()
assert records.load_state()["entries"]["app"]["install"]["filename"] == "Old.AppImage"
records.record_entry("app", renamed_new)
records.adopt_entry("app", renamed)
assert records.load_state()["entries"]["app"]["install"]["filename"] == "New.AppImage"
records.record_entry("app", renamed)
# ...and stay listed for removal after the catalog gates them, even past their
# own minStoreVersion after an OS rollback.
records.record_entry("app", dict(renamed, minStoreVersion="99"))
publish([entry("other")])
payload = {a["id"]: a for a in catalog.catalog_payload()["apps"]}
assert payload["app"]["retired"], payload.get("app")
records.clear_appimage("app")
(home / "Applications/Old.AppImage").unlink()
records.clear_entry("app")

# An installed app the catalog drops stays listed, for removal only.
dropped = entry("dropped", install={"type": "appimage", "releases": "https://example.org/r",
                                    "asset": "^D$", "filename": "D.AppImage"})
(home / "Applications/D.AppImage").write_text("")
records.record_appimage("dropped", "D.AppImage", "v1")
records.record_entry("dropped", dropped)
publish([entry("other")])
retired = catalog.find_app("dropped")
assert retired and retired["retired"]
payload = catalog.catalog_payload()
apps_by_id = {a["id"]: a for a in payload["apps"]}
assert apps_by_id["dropped"]["retired"] and not apps_by_id["dropped"]["canInstall"], apps_by_id["dropped"]
try:
    jobs.start("dropped", "install")
    raise AssertionError("reinstalled a retired app")
except ValueError:
    pass
# Its section went with it: it lands in the Store's own "other" section.
publish([entry("other", category="tools")], [{"id": "tools", "name": "Tools"}, ANDROID])
payload = catalog.catalog_payload()
assert {a["id"]: a["category"] for a in payload["apps"]}["dropped"] == "other"
assert [c["id"] for c in payload["categories"]] == ["tools", "android", "other"], payload["categories"]
# Empty sections are not shown, except Android, which Google Play fills.
publish([entry("other")], [APPS, {"id": "empty", "name": "Empty"}, ANDROID])
sections = [c["id"] for c in catalog.catalog_payload()["categories"]]
assert sections == ["applications", "android"], sections
# Gone from the device and the state: no longer listed.
(home / "Applications/D.AppImage").unlink()
records.clear_appimage("dropped")
records.clear_entry("dropped")
assert catalog.find_app("dropped") is None
assert "dropped" not in {a["id"] for a in catalog.catalog_payload()["apps"]}

# Emulators Armada Emulation manages: the Store's records for them stay (an
# older image still uses them) but it never lists, retires or acts on them.
emu = entry("retroarch", install={"type": "flatpak", "ref": "org.libretro.RetroArch"})
records.record_entry("retroarch", emu)
records.record_shortcut("retroarch", 777)
assert catalog.find_app("retroarch") is None
assert "retroarch" not in {a["id"] for a in catalog.catalog_payload()["apps"]}
try:
    jobs.start("retroarch", "uninstall")
    raise AssertionError("acted on a moved app")
except ValueError:
    pass
assert "retroarch" in records.load_state()["entries"], "dropped a moved app's record"

# A plugin the image ships has a fixed folder, is never removable, and updates
# by its own version against the release tag.
plugin = entry("bundled-plugin", category="applications",
               install={"type": "deckyplugin", "releases": "https://example.org/p", "asset": "^p\\\\.zip$",
                        "dir": "bundled-plugin"})
folder = home / "homebrew/plugins/bundled-plugin"
folder.mkdir(parents=True)
(folder / "plugin.json").write_text("{}")
(folder / "package.json").write_text('{"version": "1.2.0"}')
(bundled / "bundled-plugin").mkdir()
publish([plugin])
info = catalog.installed_info(catalog.find_app("bundled-plugin"), {}, set())
assert info == {"installed": True, "version": "1.2.0"}, info
assert not {a["id"]: a for a in catalog.catalog_payload()["apps"]}["bundled-plugin"]["removable"]
try:
    jobs.start("bundled-plugin", "uninstall")
    raise AssertionError("uninstall offered for a bundled plugin")
except ValueError:
    pass
import armada_store
from armada_apps import updates
updates.subprocess.run = lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
for tag, expected in (("v1.2.0", False), ("1.1.0", False), ("nightly", False), ("v1.3", True)):
    updates._cache.update({"at": None, "tags": {}, "stamps": {}})
    updates.resolve_release = lambda releases, asset, checksum=None, tag=tag: (tag, "https://example.org/p.zip", "", None)
    assert ("bundled-plugin" in updates.available()) == expected, tag
# A feed with no release yet is an answer: the cache warms and later checks
# skip the network. A failed request keeps it cold.
import urllib.error
for error, warm in ((urllib.error.HTTPError("u", 404, "Not Found", {}, None), True),
                    (RuntimeError("No release asset matched"), True),
                    (urllib.error.HTTPError("u", 403, "Forbidden", {}, None), False),
                    (urllib.error.URLError("down"), False)):
    calls = []
    def missing(*a, error=error, **k):
        calls.append(1)
        raise error
    updates._cache.update({"at": None, "tags": {}, "stamps": {}})
    updates.resolve_release = missing
    assert "bundled-plugin" not in updates.available(), error
    updates.available()
    assert len(calls) == (1 if warm else 2), (error, len(calls))

# Flatpak versions come from the same list and remote-ls calls, tab separated
# and possibly empty.
assert catalog.parse_flatpak_columns("org.a.App\t1.2.3\norg.b.App\t\n\n") == {"org.a.App": "1.2.3", "org.b.App": ""}
def flatpak_run(argv, *a, **k):
    out = "org.a.App\t2.0.0\n" if "remote-ls" in argv else "org.a.App\t1.2.3\norg.b.App\t\n"
    return type("R", (), {"returncode": 0, "stdout": out, "stderr": ""})()
updates.subprocess.run = flatpak_run
catalog.invalidate_flatpak_cache()
refs = catalog.flatpak_refs()
assert refs == {"org.a.App", "org.b.App"}, refs
app_a = entry("app-a", install={"type": "flatpak", "ref": "org.a.App"})
app_b = entry("app-b", install={"type": "flatpak", "ref": "org.b.App"})
assert catalog.installed_info(app_a, {}, refs) == {"installed": True, "version": "1.2.3"}
assert catalog.installed_info(app_b, {}, refs) == {"installed": True}
publish([app_a, app_b])
updates._cache.update({"at": None, "flatpak": {}, "tags": {}, "stamps": {}})
assert updates.available() == {"app-a": {"latest": "2.0.0"}}, updates.available()
catalog.invalidate_flatpak_cache()

# A fixed tag like "nightly" gets the upload date of its asset alongside.
nightly = entry("nightly-app", install={"type": "appimage", "releases": "https://example.org/n",
                                        "asset": "n\\\\.AppImage$", "filename": "Nightly.AppImage"})
(home / "Applications/Nightly.AppImage").write_text("")
nightly_state = {"appimages": {"nightly-app": {"filename": "Nightly.AppImage", "tag": "nightly",
                                               "stamp": "2026-11-20T04:00:00Z"}}}
assert catalog.installed_info(nightly, nightly_state, set()) == {
    "installed": True, "version": "nightly", "date": "2026-11-20T04:00:00Z"}
publish([nightly])
updates._cache.update({"at": None, "flatpak": {}, "tags": {}, "stamps": {}})
updates.resolve_release = lambda releases, asset, checksum=None: ("nightly", "https://example.org/n.AppImage", "2026-11-26T04:00:00Z", None)
real_load_state = records.load_state
records.load_state = lambda: nightly_state
try:
    assert updates.available() == {"nightly-app": {"latest": "nightly", "date": "2026-11-26T04:00:00Z"}}, updates.available()
finally:
    records.load_state = real_load_state
(home / "Applications/Nightly.AppImage").unlink()

# A removable plugin with a fixed folder is removed by that folder even
# without a record (the image or another install may have put it there).
loose = dict(plugin, id="loose-plugin", install=dict(plugin["install"], dir="loose-plugin"))
(home / "homebrew/plugins/loose-plugin").mkdir()
(home / "homebrew/plugins/loose-plugin/plugin.json").write_text("{}")
publish([loose])
job = jobs.Job("loose-plugin", "uninstall", catalog.find_app("loose-plugin"))
jobs._execute(job)
assert job.phase == "done", job.error
assert not (home / "homebrew/plugins/loose-plugin").exists(), "left the plugin installed"

# A system app the catalog drops is gone, not retired: the image always has
# it, so it would never stop looking installed. Only a shortcut the Store
# added keeps it listed, for cleanup.
image_app = entry("image-app")
records.record_entry("image-app", image_app)
publish([entry("fine")])
assert catalog.find_app("image-app") is None, "a dropped system app came back as retired"
records.record_shortcut("image-app", 909)
assert catalog.find_app("image-app")["retired"]
records.clear_shortcut("image-app")
records.clear_entry("image-app")

# A malformed id never takes the whole catalog down with it.
publish([{"id": [], "name": "x"}, entry("fine")])
assert shown() == ["fine"], shown()
jobs.status_payload()

# Launching an AppImage uses the file that was downloaded until the next
# install brings the catalog's new name.
launched = entry("renamed-app", install={"type": "appimage", "releases": "https://example.org/r",
                                         "asset": "^R$", "filename": "New.AppImage"})
(home / "Applications/Old.AppImage").write_text("")
records.record_appimage("renamed-app", "Old.AppImage", "v1")
assert catalog.launch_spec(launched)["exe"].endswith("/Old.AppImage")
(home / "Applications/Old.AppImage").unlink()
assert catalog.launch_spec(launched)["exe"].endswith("/New.AppImage")
records.clear_appimage("renamed-app")

# Android entries never pass through the catalog filter.
import armada_store
from armada_store import android
android_app = {"id": "android:org.example", "category": "android", "install": {"type": "android"}}
android.apps = lambda: [android_app]
assert android_app in catalog.all_apps()
android.apps = lambda: []

# HTTP: conditional requests, throttling and size limits.
class Response(io.BytesIO):
    def __init__(self, body, etag="e2"):
        super().__init__(body)
        self.headers = {"ETag": etag}
    def geturl(self):
        return "https://example.org/catalog-v1.json"
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
def http_error(code, headers=None):
    message = email.message.Message()
    for key, value in (headers or {}).items():
        message[key] = value
    return urllib.error.HTTPError("https://example.org", code, "x", message, None)
sent = []
def urlopen(request, timeout=None, context=None):
    sent.append(request)
    return replies.pop(0)() if callable(replies[0]) else replies.pop(0)
rc.urllib.request.urlopen = urlopen
def raise_(error):
    def fn():
        raise error
    return fn
replies = [Response(b"{}")]
assert rc.fetch("https://example.org", rc.CATALOG_FILE, 100) == (b"{}", "e2")
assert sent[-1].full_url == "https://example.org/catalog-v1.json", sent[-1].full_url
replies = [raise_(http_error(304))]
assert rc.fetch("https://example.org", rc.CATALOG_FILE, 100, "e1") == (None, "e1")
assert sent[-1].get_header("If-none-match") == "e1"
replies = [raise_(http_error(429, {"Retry-After": "120"}))]
try:
    rc.fetch("https://example.org", rc.CATALOG_FILE, 100)
    raise AssertionError("throttling not reported")
except rc.Throttled as error:
    assert error.retry_after == 120
replies = [Response(b"x" * 101)]
try:
    rc.fetch("https://example.org", rc.CATALOG_FILE, 100)
    raise AssertionError("oversized response accepted")
except rc.Unavailable:
    pass
# A catalog change to a release feed is looked up within the update TTL.
looked_up = []
def resolve(releases, asset, checksum=None):
    looked_up.append(releases)
    return ("v2", "https://example.org/a", "2026-02-01T00:00:00Z", None)
updates._cache.update({"at": None, "tags": {}, "stamps": {}})
updates.resolve_release = resolve
feed = entry("feed", install={"type": "appimage", "releases": "https://example.org/one",
                             "asset": "^F$", "filename": "F.AppImage"})
(home / "Applications/F.AppImage").write_text("")
records.record_appimage("feed", "F.AppImage", "v1", "2026-01-01T00:00:00Z")
publish([feed])
assert updates.available()["feed"]["latest"] == "v2"
moved = json.loads(json.dumps(feed))
moved["install"]["releases"] = "https://example.org/two"
publish([moved])
updates.available()
assert looked_up == ["https://example.org/one", "https://example.org/two"], looked_up
# Category icons: shipped files are usable SVGs, a new catalog brings fresh
# copies of its icons from the same source, an unchanged one only fetches
# what is missing, and nothing unsafe is kept.
from armada_apps import icons
import base64
for plugin in ("armada-store", "armada-emulation"):
    folder = store.parent / plugin
    for icon in folder.joinpath("icons").iterdir():
        assert icons.name_problem(icon.name) is None and icons.svg_problem(icon.read_bytes()) is None, icon
    doc = json.loads(next(folder.glob("catalog*.json")).read_text())
    for category in doc["categories"]:
        assert icons.name_problem(category["icon"]) is None, category
        assert (folder / "icons" / category["icon"]).is_file(), category["icon"]
assert icons.data_uri("layout-grid.svg").startswith("data:image/svg+xml;base64,")
assert icons.data_uri("nothing.svg") == ""
for bad in ("../x.svg", "/x.svg", "https://x/x.svg", "icons/x.svg", "X.svg", "x.png", None):
    assert icons.name_problem(bad), bad

def svg(mark):
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="{}" /></svg>'.format(mark).encode()
def served(name):
    return base64.b64decode(sections()[name].split(",", 1)[1]) if sections()[name] else b""
def sections():
    return {s["id"]: s["icon"] for s in catalog.catalog_payload()["categories"]}
(remote / "icons").mkdir(exist_ok=True)
(remote / "icons" / "new.svg").write_bytes(svg("M1 1"))
(remote / "icons" / "evil.svg").write_bytes(b'<!DOCTYPE svg [<!ENTITY a "x">]><svg/>')
(remote / "icons" / "layout-grid.svg").write_bytes(svg("M9 9"))
cats = [APPS, {"id": "new", "name": "New", "icon": "new.svg"}, {"id": "evil", "name": "Evil", "icon": "evil.svg"}]
publish([entry("a"), entry("b", category="new"), entry("c", category="evil")], cats)
assert served("new") == svg("M1 1")
assert sections()["evil"] == ""
assert served("applications") == svg("M9 9"), "the catalog's copy must win over the shipped one"
# The same catalog again: its icons are not fetched again.
(remote / "icons" / "new.svg").write_bytes(svg("M2 2"))
assert rc.refresh() is False
assert served("new") == svg("M1 1")
# A changed catalog brings every icon again, and a fetched icon survives its
# source going away.
publish([entry("a"), entry("b", category="new"), entry("c", category="evil"), entry("d", category="new")], cats)
assert served("new") == svg("M2 2")
(remote / "icons" / "new.svg").unlink()
publish([entry("a"), entry("b", category="new")], cats)
assert served("new") == svg("M2 2")
# That catalog's fetch of new.svg failed; the next refresh retries just it,
# and once stored nothing is fetched again.
(remote / "icons" / "new.svg").write_bytes(svg("M3 3"))
asked = []
real_fetch = rc.fetch
rc.fetch = lambda base, rel, limit, etag=None: (asked.append(rel), real_fetch(base, rel, limit, etag))[1]
rc.refresh()
assert served("new") == svg("M3 3")
assert [r for r in asked if r.startswith("icons/")] == ["icons/new.svg", "icons/evil.svg"], asked
asked.clear()
rc.refresh()
rc.fetch = real_fetch
assert [r for r in asked if r.startswith("icons/")] == ["icons/evil.svg"], asked
print("remote catalog: sources, fetch and fallback, schema, categories, filtering, retired and moved apps, icons OK")
PY

printf 'Armada Store test passed\n'
