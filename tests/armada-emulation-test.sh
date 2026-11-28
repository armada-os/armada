#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
EMU="$ROOT/decky/armada-emulation"
SHARED="$ROOT/decky/shared/armada-apps/py_modules"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
# The shared engine is copied into each plugin at build time; tests use it in place.
export PYTHONPATH="$SHARED:$EMU/py_modules${PYTHONPATH:+:$PYTHONPATH}"
export DECKY_PLUGIN_DIR="$EMU"

python3 -m compileall -q "$EMU/main.py" "$EMU/py_modules/armada_emulation"

# The catalog ships inside the plugin; every entry must pass the engine's check.
# The Store hides exactly the apps Emulation took over.
MOVED=$(PYTHONPATH="$SHARED:$ROOT/decky/armada-store/py_modules" python3 -c \
    'import json, armada_store; print(json.dumps(sorted(armada_store.MOVED_TO_EMULATION)))')
python3 - "$EMU" "$MOVED" <<'PY'
import json, pathlib, sys
emu = pathlib.Path(sys.argv[1])
moved = json.loads(sys.argv[2])
import armada_emulation
from armada_apps import catalog
from armada_emulation import setup

doc = json.loads((emu / "catalog.json").read_text())
catalog.parse_document((emu / "catalog.json").read_bytes())
apps = doc["apps"]
ids = {a["id"] for a in apps}
assert ids == set(moved), (ids ^ set(moved))
shown = {c["id"] for c in doc["categories"]}
for category in doc["categories"]:
    assert catalog.category_problem(category) is None, category
for app in apps:
    assert catalog.entry_problem(app, shown) is None, (app["id"], catalog.entry_problem(app, shown))
assert [a["id"] for a in catalog.catalog_apps()] == [a["id"] for a in apps]
# Setup is keyed by id, so a renamed id would silently lose its config.
assert set(setup.TEMPLATES) | set(setup.STEPS) <= ids
for app_id, (folder, dest, names) in setup.TEMPLATES.items():
    for name in names:
        assert (emu / "templates" / folder / name).is_file(), (app_id, name)
on_disk = {p.relative_to(emu / "templates") for p in (emu / "templates").rglob("*") if p.is_file()}
listed = {pathlib.Path(folder) / name for folder, _, names in setup.TEMPLATES.values() for name in names}
assert on_disk == listed, on_disk ^ listed

# Every app that changed packaging must declare the ref it displaces, or an
# existing install is stranded with no way to remove it.
declared = {c.get("ref") for a in apps for c in (a.get("conflicts") or [])}
assert {"org.duckstation.DuckStation", "net.rpcs3.RPCS3", "net.kuribo64.melonDS",
        "org.azahar_emu.Azahar", "app.xemu.xemu"} <= declared, declared
duck = next(a for a in apps if a["id"] == "duckstation")
assert catalog.present_conflicts(duck, set()) == []
assert len(catalog.present_conflicts(duck, {"org.duckstation.DuckStation"})) == 1
print("emulation catalog: %d apps, %d with templates" % (len(apps), len(setup.TEMPLATES)))
PY

# ES-DE's custom files are XML that ES-DE parses at startup; malformed ones
# are silently ignored and every custom emulator disappears.
python3 - "$EMU" <<'PY'
import sys, pathlib, re, xml.etree.ElementTree as ET
emu = pathlib.Path(sys.argv[1])
rules = ET.parse(emu / "templates/es-de/es_find_rules.xml").getroot()
names = {e.get("name") for e in rules.findall("emulator")}
# The emulators Emulation installs that ES-DE's linuxarm rules cannot find.
assert names == {"ARMSX2", "BIGPEMU", "CEMU", "PICO-8_64", "VITA3K", "XENIAEDGE"}, names
# Every entry here REPLACES the bundled one and takes its extensions and
# alternative launch commands with it, so it must carry ES-DE's whole entry.
systems = ET.parse(emu / "templates/es-de/es_systems.xml").getroot()
assert {s.findtext("name") for s in systems.findall("system")} == {
    "pico8", "ps2", "psvita", "scummvm", "wiiu", "xbox360"}
ps2 = next(s for s in systems.findall("system") if s.findtext("name") == "ps2")
assert {c.get("label") for c in ps2.findall("command")} == {
    "ARMSX2", "LRPS2", "Shortcut or script"}
assert ".desktop" in (ps2.findtext("extension") or "").split()
# A system whose emulator is unreachable is worse than no override at all.
BUNDLED = {"RETROARCH", "OS-SHELL", "PICO-8", "SCUMMVM", "DREAMM"}
for system in systems.findall("system"):
    for command in system.findall("command"):
        for used in re.findall(r"%EMULATOR_([A-Z0-9_.!-]+)%", command.text or ""):
            assert used in names | BUNDLED, (system.findtext("name"), used)
    assert system.findtext("platform"), system.findtext("name")
print("es-de templates: %d rules, %d systems" % (len(names), len(systems.findall("system"))))
PY

# Setup, overrides, takeover from the Store and the rollback guard.
python3 - "$EMU" "$WORK" <<'PY'
import asyncio, json, os, pathlib, sys, threading
emu, work = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
home, state, bundled = work / "home", work / "state", work / "bundled"
for path in (home / "Applications", state, bundled):
    path.mkdir(parents=True)
store_state = work / "store-state.json"
os.environ.update({"DECKY_USER_HOME": str(home), "DECKY_USER": os.environ.get("USER", "nobody"),
                   "ARMADA_EMULATION_STATE_DIR": str(state), "ARMADA_BUNDLED_PLUGINS": str(bundled),
                   "ARMADA_EMULATION_STORE_STATE": str(store_state)})
import armada_emulation
from armada_apps import catalog, installers, jobs, paths, records
from armada_emulation import setup, takeover
assert str(paths.state_root()) == str(state)

# RetroArch seeding keeps the flatpak skeleton and never clobbers user edits.
setup._skeleton = lambda: 'assets_directory = "/app/share/libretro/assets/"\n'
retroarch = catalog.find_app("retroarch")
setup.after_install(retroarch)
cfg = home / ".var/app/org.libretro.RetroArch/config/retroarch/retroarch.cfg"
seeded = cfg.read_text()
assert setup.CORES_URL in seeded and "assets_directory" in seeded, seeded
setup.after_install(retroarch)
assert cfg.read_text() == seeded, "second run rewrote the config"
# A value the user picked must survive reseeding.
cfg.write_text('%s = "https://example.invalid/mine/"\n' % setup.CORES_URL_KEY)
setup.after_install(retroarch)
assert "example.invalid" in cfg.read_text(), "clobbered a user-chosen URL"
# ...but an empty value is the broken state the seeding exists to fix.
cfg.write_text('%s = ""\n' % setup.CORES_URL_KEY)
setup.after_install(retroarch)
assert setup.CORES_URL in cfg.read_text(), "empty value was not seeded"

# ES-DE templates land once and are then left alone; Reset rewrites them and
# keeps the old file.
es_de = catalog.find_app("es-de")
setup.after_install(es_de)
rules = home / "ES-DE/custom_systems/es_find_rules.xml"
assert "ARMSX2" in rules.read_text()
rules.write_text("<ruleList/>\n")
setup.after_install(es_de)
assert rules.read_text() == "<ruleList/>\n", "reinstall clobbered a customised file"
setup.reset_config("es-de")
assert "ARMSX2" in rules.read_text() and (rules.parent / "es_find_rules.xml.bak").read_text() == "<ruleList/>\n"
try:
    setup.reset_config("dolphin")
    raise AssertionError("reset an app without templates")
except RuntimeError:
    pass
# A FIFO in the destination is refused, not opened.
melon = home / ".config/melonDS"
melon.mkdir(parents=True)
os.mkfifo(melon / "melonDS.toml")
try:
    setup.after_install(catalog.find_app("melonds"))
    raise AssertionError("seeded over a FIFO")
except RuntimeError as error:
    assert "regular file" in str(error), error
(melon / "melonDS.toml").unlink()

# Every emulator Flatpak gets removable media, plus anything its entry asks for.
sent = []
installers.override_flatpak = lambda ref, options: sent.append((ref, list(options)))
installers.install_flatpak = lambda ref, cancel, on_percent: None
catalog.invalidate_flatpak_cache = lambda: None
job = jobs.Job("dolphin", "install", catalog.find_app("dolphin"))
jobs._execute(job)
assert job.phase == "done", job.error
assert sent == [("org.DolphinEmu.dolphin-emu", list(setup.BASE_OVERRIDES))], sent
payload = {a["id"]: a for a in catalog.catalog_payload()["apps"]}
assert payload["es-de"]["hasConfig"] and not payload["dolphin"]["hasConfig"]

# Taking over from the Store: entries, live AppImage records and shortcuts for
# Emulation's own apps, without touching the Store's file.
for key in ("entries", "shortcuts", "pendingShortcuts", "appimages", takeover.DONE_KEY):
    records._mutate_state(lambda s, key=key: s.pop(key, None))
(home / "Applications/Cemu.AppImage").write_text("")
old = {
    "appimages": {"cemu": {"filename": "Cemu.AppImage", "tag": "v1", "stamp": "2026-01-01T00:00:00Z"},
                  "ppsspp": {"filename": "PPSSPP.AppImage", "tag": "v9", "stamp": ""},
                  "quiver-launcher": {"filename": "QuiverLauncher.AppImage", "tag": "v3"}},
    "entries": {"cemu": {"id": "cemu"}, "moonlight": {"id": "moonlight"}},
    "shortcuts": {"cemu": 101, "moonlight": 202, "dolphin": True},
    "pendingShortcuts": ["vita3k", "moonlight"],
}
ids = [a["id"] for a in catalog.catalog_apps()]
store_state.write_text("not json")
takeover.run(ids)
assert takeover.DONE_KEY not in records.load_state(), "marked done after a failed read"
store_state.write_text(json.dumps(old))
before = store_state.read_text()
takeover.run(ids)
mine = records.load_state()
assert mine["appimages"] == {"cemu": old["appimages"]["cemu"]}, mine["appimages"]
assert mine["shortcuts"] == {"cemu": 101}, mine["shortcuts"]
assert mine["pendingShortcuts"] == ["vita3k"], mine["pendingShortcuts"]
assert set(mine["entries"]) == {"cemu"}, mine["entries"]
assert store_state.read_text() == before, "wrote to the Store's records"
# What happened here since stands: a shortcut removed or replaced here is not
# brought back by the same Store record.
records.clear_shortcut("cemu")
records.clear_pending_shortcut("vita3k")
takeover.run(ids)
assert "cemu" not in records.load_state()["shortcuts"], "re-adopted a removed shortcut"
assert records.load_state()["pendingShortcuts"] == [], "re-queued a shortcut"
# After a rollback, the older Store installs an emulator and adds its shortcut;
# back on this image, Emulation adopts it instead of offering a second one.
old["shortcuts"]["dolphin"] = 404
old["shortcuts"]["cemu"] = 505
store_state.write_text(json.dumps(old))
takeover.run(ids)
assert records.load_state()["shortcuts"] == {"dolphin": 404, "cemu": 505}, records.load_state()["shortcuts"]
records.record_shortcut("cemu", 606)
takeover.run(ids)
assert records.load_state()["shortcuts"]["cemu"] == 606, "an older record replaced a newer one"
# A Store that never ran leaves nothing to import.
store_state.unlink()
takeover.run([])

# The rollback guard: on an image that doesn't ship Emulation, it does nothing.
sys.path.insert(0, str(emu))
import main
plugin = main.Plugin()
payload = asyncio.run(plugin.get_catalog())
assert payload["notice"] and payload["apps"] == [], payload
try:
    asyncio.run(plugin.install_app("dolphin"))
    raise AssertionError("installed on an image without Emulation")
except RuntimeError:
    pass
(bundled / "armada-emulation").mkdir()
payload = asyncio.run(plugin.get_catalog())
assert "notice" not in payload and len(payload["apps"]) == 19, payload.get("notice")
print("emulation: setup, overrides, takeover and rollback guard OK")
PY

printf 'Armada Emulation test passed\n'
