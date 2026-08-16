#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
STORE="$ROOT/decky/armada-store"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

python3 -m compileall -q "$STORE/main.py" "$STORE/py_modules/armada_store"

# The catalog is data the backend trusts; a typo here breaks every install.
python3 - "$STORE" <<'PY'
import json, re, sys, pathlib
store = pathlib.Path(sys.argv[1])
catalog = json.loads((store / "catalog.json").read_text())
apps = catalog["apps"]

ids = [a["id"] for a in apps]
assert len(ids) == len(set(ids)), "duplicate app ids"

sys.path.insert(0, str(store / "py_modules"))
from armada_store import catalog, postinstall

for app in apps:
    install = app["install"]
    kind = install["type"]
    assert kind in ("flatpak", "appimage", "deckyplugin", "system"), (app["id"], kind)
    assert app["category"] in ("emulators", "applications", "plugins"), app["id"]
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
    # A tool that needs Steam closed must never be offered as a Steam shortcut.
    if app.get("desktopOnly"):
        assert catalog.launch_spec(app) is None, app["id"]
    # A declared handler that does not exist fails every install of that app.
    name = app.get("postInstall")
    if name:
        assert name in postinstall.HANDLERS, (app["id"], name)

# Every template a handler seeds has to be present to be packaged.
for template in ("es-de/es_find_rules.xml", "es-de/es_systems.xml"):
    assert (store / "templates" / template).is_file(), template

assert any(a.get("desktopOnly") for a in apps), "expected at least one desktop-only entry"
print("catalog: %d apps, %d appimage, %d flatpak" % (
    len(apps),
    sum(1 for a in apps if a["install"]["type"] == "appimage"),
    sum(1 for a in apps if a["install"]["type"] == "flatpak")))
PY

# ES-DE's custom files are XML that ES-DE parses at startup; malformed ones
# are silently ignored and every custom emulator disappears.
python3 - "$STORE" <<'PY'
import sys, pathlib, xml.etree.ElementTree as ET
store = pathlib.Path(sys.argv[1])
rules = ET.parse(store / "templates/es-de/es_find_rules.xml").getroot()
names = {e.get("name") for e in rules.findall("emulator")}
# ARMSX2 is the only emulator bundled ES-DE cannot find on its own.
assert names == {"ARMSX2"}, names
# Every entry here REPLACES the bundled one and takes its extensions and
# alternative launch commands with it, so it must carry ES-DE's whole entry.
systems = ET.parse(store / "templates/es-de/es_systems.xml").getroot()
# Cemu needs no entry: ES-DE's own CEMU rule already finds ~/Applications.
assert {s.findtext("name") for s in systems.findall("system")} == {"ps2"}
ps2 = next(s for s in systems.findall("system") if s.findtext("name") == "ps2")
assert {c.get("label") for c in ps2.findall("command")} == {
    "ARMSX2", "LRPS2", "PCSX2", "PCSX2 (Standalone)", "PCSX2 Legacy (Standalone)",
    "Play! (Standalone)", "Shortcut or script"}
assert ".desktop" in (ps2.findtext("extension") or "").split()
print("es-de templates: %d rules, %d systems" % (len(names), len(systems.findall("system"))))
PY

# Sandbox overrides are applied from code, not from the catalog, so nothing in
# catalog.json shows that every flatpak gets removable media. Pin it here.
python3 - "$STORE" <<'PY'
import sys, pathlib, json
store = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(store / "py_modules"))
from armada_store import installers

sent = []
installers.subprocess.run = lambda argv, **kw: sent.append(argv) or type(
    "R", (), {"returncode": 0, "stderr": b"", "stdout": b""})()

for app in json.loads((store / "catalog.json").read_text())["apps"]:
    install = app["install"]
    if install["type"] == "flatpak":
        installers.override_flatpak(install["ref"], install.get("overrides"))

assert sent, "no flatpak in the catalog to override"
for argv in sent:
    ref = argv[3]
    assert "--filesystem=/run/media" in argv, "no SD card access for " + ref
    assert "--filesystem=/media" in argv, "no /media access for " + ref
    assert argv[:3] == ["flatpak", "override", "--system"], argv

count = len(sent)

# No catalog entry needs a per-app override today, so drive it directly.
installers.override_flatpak("org.example.App", ["--filesystem=home"])
extra = sent[-1]
assert "--filesystem=home" in extra, extra
assert "--filesystem=/run/media" in extra, extra

print("overrides: %d flatpaks, all get /run/media and /media" % count)
PY

# Release selection, against the shapes real forges actually return.
python3 - "$STORE" <<'PY'
import sys, pathlib, json, io
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / "py_modules"))
from armada_store import installers

def resolve(releases, pattern):
    payload = io.BytesIO(json.dumps(releases).encode())
    payload.geturl = lambda: "https://example.invalid"
    payload.__enter__ = lambda self=payload: self
    payload.__exit__ = lambda *a: False
    installers.urllib.request.urlopen = lambda *a, **k: payload
    return installers.resolve_release_asset("https://example.invalid", pattern)

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

from armada_store import installers, postinstall

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

os.environ["ARMADA_STORE_ALLOW_INSECURE_URLS"] = "1"
installers.resolve_release_asset = lambda *a, **k: ("v1", archive.as_uri(), "2026-01-01T00:00:00Z")
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
installers.resolve_release_asset = lambda *a, **k: ("v1", evil.as_uri(), "2026-01-01T00:00:00Z")
try:
    installers.install_decky_plugin({"releases": "x", "asset": "y"}, cancel, noop, noop)
    raise AssertionError("traversing member was accepted")
except RuntimeError as error:
    assert "Unsafe archive member" in str(error), error

# Desktop entries: AppImages have no other launcher in desktop mode.
app = {"id": "flycast", "name": "Flycast", "summary": "Dreamcast", "category": "emulators", "icon": ""}
installers.write_desktop_entry(app, str(home / "Applications/Flycast.AppImage"))
entry = home / ".local/share/applications/armada-flycast.desktop"
text = entry.read_text()
assert 'Exec="%s"' % (home / "Applications/Flycast.AppImage") in text, text
assert "Categories=Game;Emulator;" in text and "X-Armada-Store=flycast" in text, text
installers.remove_desktop_entry("flycast")
assert not entry.exists()

# A cancelled job must not stop a committed install from getting its entry.
cancel.set()
installers.write_desktop_entry(app, str(home / "Applications/Flycast.AppImage"))
assert entry.exists(), "cancellation blocked the desktop entry"
cancel.clear()
installers.remove_desktop_entry("flycast")

# RetroArch seeding keeps the flatpak skeleton and never clobbers user edits.
postinstall._skeleton = lambda: 'assets_directory = "/app/share/libretro/assets/"\n'
postinstall.run({"id": "retroarch", "postInstall": "retroarch-cores-url"})
cfg = home / ".var/app/org.libretro.RetroArch/config/retroarch/retroarch.cfg"
seeded = cfg.read_text()
assert postinstall.CORES_URL in seeded and "assets_directory" in seeded, seeded
postinstall.run({"id": "retroarch", "postInstall": "retroarch-cores-url"})
assert cfg.read_text() == seeded, "second run rewrote the config"

# A value the user picked must survive reseeding, per the handler contract.
cfg.write_text('%s = "https://example.invalid/mine/"\n' % postinstall.CORES_URL_KEY)
postinstall.run({"id": "retroarch", "postInstall": "retroarch-cores-url"})
assert "example.invalid" in cfg.read_text(), "clobbered a user-chosen URL"
# ...but an empty value is the broken state the seeding exists to fix.
cfg.write_text('%s = ""\n' % postinstall.CORES_URL_KEY)
postinstall.run({"id": "retroarch", "postInstall": "retroarch-cores-url"})
assert postinstall.CORES_URL in cfg.read_text(), "empty value was not seeded"

# ES-DE templates land once and are then left alone.
postinstall.run({"id": "es-de", "postInstall": "es-de-custom-systems"})
rules = home / "ES-DE/custom_systems/es_find_rules.xml"
assert "ARMSX2" in rules.read_text()
rules.write_text("<ruleList/>\n")
postinstall.run({"id": "es-de", "postInstall": "es-de-custom-systems"})
assert rules.read_text() == "<ruleList/>\n", "reinstall clobbered a customised file"

# An unknown handler must fail loudly rather than install a broken app.
try:
    postinstall.run({"id": "x", "postInstall": "nope"})
    raise AssertionError("unknown handler was accepted")
except RuntimeError:
    pass

print("installers: plugin, desktop entry, seeding and clobber guards OK")
PY

# Every app that changed packaging must declare the ref it displaces, or an
# existing install is stranded with no way to remove it from the Store.
python3 - "$STORE" <<'PY'
import sys, pathlib, json
store = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(store / "py_modules"))
from armada_store import catalog

apps = json.loads((store / "catalog.json").read_text())["apps"]
declared = {c.get("ref") for a in apps for c in (a.get("conflicts") or [])}
assert declared, "no conflicts declared"

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

# Armada Control wraps these as "armada-game-launch %command% <options>", so a
# flag here reaches the app; for flatpaks it must stay after the run target.
heroic = catalog.launch_spec(next(a for a in apps if a["id"] == "heroic"))
assert heroic["launchOptions"] == "--no-sandbox", heroic
flat = catalog.launch_spec({"name": "x", "install": {
    "type": "flatpak", "ref": "org.example.App", "launchOptions": "--foo"}})
assert flat["launchOptions"] == "run org.example.App --foo", flat

duck = next(a for a in apps if a["id"] == "duckstation")
assert catalog.present_conflicts(duck, set()) == [], "conflict reported while absent"
present = catalog.present_conflicts(duck, {"org.duckstation.DuckStation"})
assert len(present) == 1 and present[0]["type"] == "flatpak", present

print("conflicts: %d declared, detection tracks installed refs" % len(declared))
PY

# A replacement can finish with the panel closed, so the queued re-add has to
# live in backend state rather than in a job transition the panel might miss.
python3 - "$STORE" <<'PY'
import sys, pathlib, tempfile, os
store_dir = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(store_dir / "py_modules"))
os.environ["ARMADA_STORE_STATE_DIR"] = str(pathlib.Path(tempfile.mkdtemp()))
from armada_store import store

store.record_shortcut("duckstation", 4242)
assert store.pending_shortcuts() == []

# The ordinary guard skips an app that already has a shortcut; a replacement has
# to queue anyway, because its record still points at the packaging being removed.
store.add_pending_shortcut("duckstation")
assert store.pending_shortcuts() == []
store.add_pending_shortcut("duckstation", force=True)
store.add_pending_shortcut("duckstation", force=True)
assert store.pending_shortcuts() == ["duckstation"], store.pending_shortcuts()

# The old record survives until the new shortcut exists, so the frontend still
# knows which shortcut to remove if the panel reopens mid-swap.
assert store.shortcuts().get("duckstation") == 4242

# The removal phase drops only the record; the add it still owes has to survive,
# or a failure between the two phases loses the shortcut entirely.
store.clear_shortcut("duckstation", keep_pending=True, expected=4242)
assert store.pending_shortcuts() == ["duckstation"], store.pending_shortcuts()
assert "duckstation" not in store.shortcuts()

# That call can land after the swap was cancelled and a new shortcut recorded,
# so it must not delete a record it never set out to remove.
store.record_shortcut("es-de", 1111)
store.add_pending_shortcut("es-de", force=True)
store.clear_shortcut("es-de")
store.record_shortcut("es-de", 2222)
store.clear_shortcut("es-de", keep_pending=True, expected=1111)
assert store.shortcuts().get("es-de") == 2222, store.shortcuts()

store.record_shortcut("duckstation", 5252)
assert store.pending_shortcuts() == []
assert store.shortcuts()["duckstation"] == 5252

# Removing the shortcut by hand cancels a queued add, or it comes straight back.
store.add_pending_shortcut("azahar", force=True)
store.clear_shortcut("azahar")
assert store.pending_shortcuts() == [], store.pending_shortcuts()

# Same for an uninstall, which is the path that runs when removal from Steam failed.
store.record_shortcut("vita3k", 6262)
store.add_pending_shortcut("vita3k", force=True)
store.clear_pending_shortcut("vita3k")
assert store.pending_shortcuts() == [], store.pending_shortcuts()

print("shortcut queue: one list, forced re-add on replace, cancelled on removal")
PY

printf 'Armada Store test passed\n'
