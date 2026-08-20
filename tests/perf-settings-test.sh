#!/usr/bin/env bash
# Covers the performance-settings pipeline: armada_perf semantics (cpulist
# grammar, explicit-all vs unset, sanitize clamps, state layering), the
# armada-game-launch FEX path staying byte-identical when perf keys are
# present, the wrapper's explicit affinity reset, armada-powerd config
# parsing (old configs without [system] must still parse) and IRQ mask
# derivation, armada-control's PerfManager lifecycle, and the plugin's
# power-config render with cpu_governor editable.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

TWEAKS_FIXTURE="$WORK/game-tweaks.json"
SESSION_FILE="$ROOT/system_files/etc/gamescope-session-plus/sessions.d/steam"
SESSION_REALTIME_BLOCK="$(sed -n '/^_armada_tweaks_config=/,/^unset _armada_tweaks_config$/p' "$SESSION_FILE")"

session_realtime_value() {
    env -u GAMESCOPE_FORCE_VULKAN_REALTIME ARMADA_TWEAKS_CONFIG="$TWEAKS_FIXTURE" \
        bash -c "$SESSION_REALTIME_BLOCK"$'\n''printf "%s" "${GAMESCOPE_FORCE_VULKAN_REALTIME:-}"'
}

printf '{"global":{"gamescopeVulkanRealtime":true}}\n' > "$TWEAKS_FIXTURE"
[[ "$(session_realtime_value)" == 1 ]] || {
    printf 'FAIL: enabled session setting did not export realtime queue request\n' >&2
    exit 1
}
printf '{"global":{"gamescopeVulkanRealtime":false}}\n' > "$TWEAKS_FIXTURE"
[[ -z "$(session_realtime_value)" ]] || {
    printf 'FAIL: disabled session setting exported realtime queue request\n' >&2
    exit 1
}
printf '{"global":{}}\n' > "$TWEAKS_FIXTURE"
[[ -z "$(session_realtime_value)" ]] || {
    printf 'FAIL: absent session setting exported realtime queue request\n' >&2
    exit 1
}

python3 - "$ROOT" "$WORK" <<'PYEOF'
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import selectors
import subprocess
import sys
import tempfile
import time

ROOT, WORK = sys.argv[1], sys.argv[2]
LIB = os.path.join(ROOT, "system_files/usr/lib/armada")
LIBEXEC = os.path.join(ROOT, "system_files/usr/libexec/armada")
sys.path.insert(0, LIB)

import armada_perf as ap

failures = []


def check(name, condition):
    if not condition:
        failures.append(name)
        print(f"FAIL: {name}", file=sys.stderr)


def load_script(name):
    spec = importlib.util.spec_from_loader(
        name.replace("-", "_"),
        importlib.machinery.SourceFileLoader(
            name.replace("-", "_"), os.path.join(LIBEXEC, name)),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENV = {"ARMADA_BIG_CORES": "3-7", "ARMADA_PRIME_CORES": "7", "ARMADA_LITTLE_CORES": "0-2"}
ALL = ap.online_cpus()

# --- armada_perf: cpulist grammar -------------------------------------------
check("parse order preserved", ap.parse_cpulist("7,3-5") == [7, 3, 4, 5])
check("format roundtrip", ap.format_cpulist([3, 4, 5, 7]) == "3-5,7")
for bad in ("3,3", "a", "5-3", "1-x"):
    try:
        ap.parse_cpulist(bad)
        check(f"parse rejects {bad!r}", False)
    except ValueError:
        pass

# --- armada_perf: explicit-all vs unset -------------------------------------
check("unset is None", ap.resolve_cores(None, ENV) is None and ap.resolve_cores("", ENV) is None)
check("all is explicit full set", ap.resolve_cores("all", ENV) == ALL)
check("empty preset is explicit full set",
      ap.resolve_cores("little", {"ARMADA_LITTLE_CORES": ""}) == ALL)
check("preset resolves", ap.resolve_cores("big", ENV) == [3, 4, 5, 6, 7])
try:
    ap.resolve_cores(f"{max(ALL) + 1}", ENV)
    check("unknown cpu rejected", False)
except ValueError:
    pass

# --- armada_perf: sanitize + layering ---------------------------------------
clean = ap.sanitize_perf(
    {"nice": -99, "gamescopeNice": 99, "gamescopeRr": True, "scheduler": "lavd",
     "cores": "bogus list", "wineTopology": False}, ENV)
check("nice clamped", clean["nice"] == ap.NICE_MIN)
check("gamescope nice clamped", clean["gamescopeNice"] == ap.GAMESCOPE_NICE_MAX)
check("bad cores dropped", "cores" not in clean)
check("wineTopology false kept", clean["wineTopology"] is False)
check("unset keys stay absent", ap.sanitize_perf({}, ENV) == {})

state = {"global": {"gamescopeNice": -5, "gamescopeCores": [3, 4, 5, 6, 7]},
         "override": {"gamescopeCores": ALL, "gamescopeRr": True, "pid": 1}}
eff = ap.effective_state(state)
check("override all clears restrictive global", eff["gamescopeCores"] == ALL)
check("global survives where override silent", eff["gamescopeNice"] == -5)
check("override wins", eff["gamescopeRr"] is True)

tweaks = {"global": {"fexProfile": "default", "nice": -3},
          "games": {"620": {"nice": 0, "cores": "big"},
                    "999": {"enabled": False, "nice": -9}}}
merged = ap.merged_settings(tweaks, "620")
check("per-game overrides global", merged["nice"] == 0 and merged["cores"] == "big")
check("global key survives merge", merged["fexProfile"] == "default")
check("enabled:false game skipped", ap.merged_settings(tweaks, "999")["nice"] == -3)

# env is additive per-entry with null tombstones (lib AND wrapper copies)
env_tweaks = {"global": {"env": {"A": "1", "B": "2"}},
              "games": {"620": {"env": {"B": "override", "C": "3", "A": None}}}}
merged_env = ap.merged_settings(env_tweaks, "620")["env"]
check("env additive: game adds", merged_env.get("C") == "3")
check("env additive: game overrides entry", merged_env.get("B") == "override")
check("env tombstone removes global var", "A" not in merged_env)
check("env global-only view intact", ap.merged_settings(env_tweaks, None)["env"] == {"A": "1", "B": "2"})

# --- armada-game-launch: FEX path unchanged by perf keys --------------------
os.environ["XDG_CACHE_HOME"] = WORK
launch = load_script("armada-game-launch")
with open(os.path.join(LIBEXEC, "armada-game-launch"), "rb") as f:
    check("wrapper interpreter is PATH-independent", f.readline() == b"#!/usr/bin/python3\n")

appimage = pathlib.Path(WORK) / "test.AppImage"
appimage.write_bytes(b"\x7fELF" + b"\0" * 4 + b"AI\x02")
not_appimage = pathlib.Path(WORK) / "not-an-appimage"
not_appimage.write_bytes(b"#!/bin/sh\n")
fifo = pathlib.Path(WORK) / "argv-fifo"
os.mkfifo(fifo)
check("non-regular argv rejected", not launch.is_appimage(str(fifo)))
saved_path = os.environ.get("PATH")
try:
    os.environ["PATH"] = "/steam/runtime/bin"
    launch.prepare_appimage_path(["/steam-launch-wrapper", "--", str(appimage)])
    check("AppImage command chain gets standard PATH",
          os.environ["PATH"] == "/steam/runtime/bin:/usr/local/bin:/usr/bin:/bin")
    os.environ["PATH"] = "/steam/runtime/bin"
    launch.prepare_appimage_path(["/steam-launch-wrapper", "--", str(not_appimage)])
    check("non-AppImage PATH unchanged", os.environ["PATH"] == "/steam/runtime/bin")
    os.environ["PATH"] = "/usr/bin:/steam/runtime/bin:/bin"
    launch.prepare_appimage_path([str(appimage)])
    check("existing PATH order preserved",
          os.environ["PATH"] == "/usr/bin:/steam/runtime/bin:/bin:/usr/local/bin")
finally:
    if saved_path is None:
        os.environ.pop("PATH", None)
    else:
        os.environ["PATH"] = saved_path

base_fex = os.path.join(WORK, "base-fex.json")
with open(base_fex, "w") as f:
    json.dump({"Config": {"TSOEnabled": "1"}, "ThunksDB": {"Vulkan": 1, "GL": 1}}, f)
launch.BASE_FEX_CONFIG = __import__("pathlib").Path(base_fex)
profiles = {"default": {"config": {"Multiblock": "0"}}}


def fex_result(settings):
    env = {}
    launch.apply_fex(settings, "620", profiles, env)
    with open(env["FEX_APP_CONFIG"]) as f:
        return env["FEX_APP_CONFIG"], json.load(f)


config_path, plain = fex_result({"fexProfile": "default"})
check("config lands in test cache dir", config_path.startswith(WORK + "/armada-fex/"))
_, with_perf = fex_result({"fexProfile": "default", "cores": "big", "nice": -5,
                           "gamescopeRr": True, "scheduler": "lavd",
                           "env": {"X": "1"}, "wineTopology": False})
check("FEX config unaffected by perf keys", plain == with_perf)
check("FEX config content sane", plain["Config"]["Multiblock"] == "0")

# --- armada-game-launch: explicit affinity reset ----------------------------
saved = os.sched_getaffinity(0)
try:
    restricted = set(list(saved)[:2]) if len(saved) > 2 else saved
    os.sched_setaffinity(0, restricted)
    os.environ.pop("WINE_CPU_TOPOLOGY", None)
    launch.apply_perf({}, None)  # session socket warning on stderr is fine
    check("wrapper resets inherited mask", os.sched_getaffinity(0) == set(ap.online_cpus()))
    check("no topology without cores", "WINE_CPU_TOPOLOGY" not in os.environ)
    launch.apply_perf({"cores": "7,3-6"}, None)
    check("ordered topology derived", os.environ.get("WINE_CPU_TOPOLOGY") == "5:7,3,4,5,6")
    check("cores mask applied", os.sched_getaffinity(0) == {3, 4, 5, 6, 7})
    os.environ.pop("WINE_CPU_TOPOLOGY", None)
    launch.apply_perf({"cores": "big", "scheduler": "cosmos"}, None)
    check("cosmos skips hard mask", os.sched_getaffinity(0) == set(ap.online_cpus()))
    # a malformed env name must not abort the rest of the launch path
    os.sched_setaffinity(0, restricted)
    os.environ.pop("GOODVAR", None)
    launch.apply_perf({"env": {"BAD=NAME": "x", "GOODVAR": "1"}, "cores": "7,3-6"}, None)
    check("bad env entry contained", os.environ.get("GOODVAR") == "1")
    check("launch path survives bad env", os.sched_getaffinity(0) == {3, 4, 5, 6, 7})
    os.environ.pop("GOODVAR", None)
    os.environ.pop("WINE_CPU_TOPOLOGY", None)
finally:
    os.sched_setaffinity(0, saved)

# --- device-env: topology emission + empty-override semantics ---------------
device_env_script = os.path.join(ROOT, "system_files/usr/libexec/armada/device-env")
devices_dir = os.path.join(ROOT, "system_files/usr/lib/armada/devices")

def run_device_env(model, extra_env=None):
    env = dict(os.environ, ARMADA_DEVICE_DIR=devices_dir, ARMADA_MODEL=model)
    env.update(extra_env or {})
    out = subprocess.check_output(["bash", device_env_script], env=env, text=True)
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)

odin3 = run_device_env("AYN Odin 3")
check("device-env SM8750 big", odin3.get("ARMADA_BIG_CORES") == "0-7")
check("device-env SM8750 prime", odin3.get("ARMADA_PRIME_CORES") == "6-7")
check("device-env SM8750 irq unrestricted", odin3.get("ARMADA_IRQ_CORES") == "''")
thor = run_device_env("AYN Thor")
check("device-env SM8550 irq littles", thor.get("ARMADA_IRQ_CORES") == "0-2")
thor_override = run_device_env("AYN Thor", {"ARMADA_IRQ_CORES": ""})
check("device-env explicit-empty override honored",
      thor_override.get("ARMADA_IRQ_CORES") == "''")
pocket_ds = run_device_env("AYANEO Pocket DS")
check("device-env Pocket DS enables sync suspend",
      pocket_ds.get("ARMADA_SYNC_SUSPEND") == "1")

# --- armada-powerd: config parsing ------------------------------------------
powerd = load_script("armada-powerd")
factory = os.path.join(ROOT, "system_files/usr/share/armada/power-profiles.conf")
powerd.FACTORY_CONFIG_FILE = powerd.Path(factory)
powerd.CONFIG_FILE = powerd.Path(os.path.join(WORK, "no-such-etc.conf"))
power = powerd.ArmadaPower.__new__(powerd.ArmadaPower)
parsed = power.parse_config()
(default_profile, underclocks, fan_curves, profile_config, fan_config,
 suspend_config, system_config) = parsed
check("factory default profile", default_profile == "balanced")
check("factory has 3 fan curves", len(fan_curves) == 3)
check("profiles keep governor", profile_config["performance"]["cpu_governor"] == "performance")
check("no [system] -> irq auto", system_config["irq_cores"] == "auto")
check("underclock tables parsed", "SM8550" in underclocks and "SM8750" in underclocks)

etc = os.path.join(WORK, "etc-power.conf")
with open(etc, "w") as f:
    f.write("[system]\nirq_cores=0-2\n")
powerd.CONFIG_FILE = powerd.Path(etc)
check("[system] override parsed", power.parse_config()[6]["irq_cores"] == "0-2")

power.system_config = {"irq_cores": "auto"}
power.env = {"ARMADA_IRQ_CORES": "0-2"}
check("irq auto mask", power.irq_mask() == 0b111)
power.env = {"ARMADA_IRQ_CORES": ""}
full_mask = sum(1 << c for c in ALL)
check("irq auto empty = all", power.irq_mask() == full_mask)
power.system_config = {"irq_cores": "garbage!"}
check("irq bad falls back to all", power.irq_mask() == full_mask)

# --- armada-control: PerfManager lifecycle ----------------------------------
control = load_script("armada-control")
ap.TWEAKS_CONFIG = ap.pathlib.Path(os.path.join(WORK, "game-tweaks.json"))
ap.STATE_FILE = ap.pathlib.Path(os.path.join(WORK, "perf-state.json"))
ap.device_env = lambda: dict(ENV)

restart_calls = []
real_control_run = control.run
control.run = lambda command, timeout=20: restart_calls.append(command)
try:
    check("game mode restart action succeeds", control.action_restart_game_mode({}) == {"ok": True})
    check("game mode restart requests sddm restart",
          restart_calls == [["/usr/bin/systemctl", "--no-block", "restart", "sddm.service"]])
finally:
    control.run = real_control_run

with ap.TWEAKS_CONFIG.open("w") as f:
    json.dump({"global": {"gamescopeNice": -5},
               "games": {"620": {"gamescopeRr": True, "scheduler": "cosmos",
                                 "cores": "big", "nice": -4}}}, f)

sel = selectors.DefaultSelector()
manager = control.PerfManager(sel)
state = ap.read_state()
check("refresh writes global layer", state["global"].get("gamescopeNice") == -5)
check("no override at startup", "override" not in state)

child = subprocess.Popen(["sleep", "30"])
try:
    manager.game_launched("620", child.pid)
    state = ap.read_state()
    override = state.get("override", {})
    check("override tracks pid", override.get("pid") == child.pid)
    check("override carries rr", override.get("gamescopeRr") is True)
    check("cosmos domain from cores", override.get("schedulerDomain") == [3, 4, 5, 6, 7])
    check("pidfd armed", manager.pidfd is not None)

    # live tweaks edit rebuilds the override instead of dropping it
    with ap.TWEAKS_CONFIG.open("w") as f:
        json.dump({"global": {"gamescopeNice": -5},
                   "games": {"620": {"gamescopeRr": False, "scheduler": "lavd"}}}, f)
    manager.refresh(keep_override=True)
    override = ap.read_state().get("override", {})
    check("keep_override survives edit", override.get("pid") == child.pid)
    check("override rebuilt from new tweaks",
          override.get("scheduler") == "lavd" and override.get("gamescopeRr") is False)

    # a launch whose layer equals global still tracks the session
    child2 = subprocess.Popen(["sleep", "30"])
    try:
        manager.game_launched(None, child2.pid)
        override = ap.read_state().get("override", {})
        check("plain launch still tracked", override.get("pid") == child2.pid)
    finally:
        child2.terminate()
        child2.wait()
finally:
    child.terminate()
    child.wait()

manager.game_exited()
check("exit restores globals", "override" not in ap.read_state())
check("pidfd released", manager.pidfd is None)

# session pid resolution: a fake Steam reaper ancestor is preferred over
# the direct pid; a plain process falls back to itself
fake_reaper = subprocess.Popen(["bash", "-c", "sleep 30; :", "SteamLaunch", "AppId=620"])
try:
    time.sleep(0.3)
    kids = ap.child_pids(fake_reaper.pid)
    check("fake reaper has a child", bool(kids))
    if kids:
        check("session pid walks up to the reaper",
              manager.steam_session_pid(kids[0], "620") == fake_reaper.pid)
        check("appid mismatch falls back to direct pid",
              manager.steam_session_pid(kids[0], "999") == kids[0])
finally:
    fake_reaper.terminate()
    fake_reaper.wait()
nested_outer = subprocess.Popen([
    "bash", "-c", 'bash -c "sleep 30; :" SteamLaunch AppId=620; :',
    "SteamLaunch", "AppId=620"])
try:
    time.sleep(0.4)
    inner = ap.child_pids(nested_outer.pid)
    grand = ap.child_pids(inner[0]) if inner else []
    check("nested wrappers spawned", bool(inner and grand))
    if inner and grand:
        check("nested wrappers resolve to the OUTERMOST",
              manager.steam_session_pid(grand[0], "620") == nested_outer.pid)
finally:
    nested_outer.terminate()
    nested_outer.wait()

plain = subprocess.Popen(["sleep", "30"])
try:
    check("no reaper ancestor falls back to pid",
          manager.steam_session_pid(plain.pid, "620") == plain.pid)
finally:
    plain.terminate()
    plain.wait()

# stale pidfd event from an earlier generation must not clear a new session
childA = subprocess.Popen(["sleep", "30"])
childB = subprocess.Popen(["sleep", "30"])
try:
    manager.game_launched("620", childA.pid)
    stale_callback = sel.get_key(manager.pidfd).data
    manager.game_launched("620", childB.pid)
    stale_callback()  # old generation: must be ignored
    check("stale pidfd event ignored",
          ap.read_state().get("override", {}).get("pid") == childB.pid)
    sel.get_key(manager.pidfd).data()  # current generation: must clear
    check("current pidfd event clears", "override" not in ap.read_state())
finally:
    childA.terminate(); childA.wait()
    childB.terminate(); childB.wait()

# --- armada-control: socket protocol ----------------------------------------
import socket as socketlib

# absolute request deadline: a drip-feeding client gets cut off
control.CLIENT_TIMEOUT = 1
server, client = socketlib.socketpair()
client.sendall(b"partial request without newline")
start = time.monotonic()
control.serve_client(server, lambda request, conn: {"never": True})
elapsed = time.monotonic() - start
check("stalled client cut off near deadline", 0.5 < elapsed < 3)
reply = json.loads(client.recv(65536).decode().split("\n")[0])
check("stall returns an error", reply.get("ok") is False)
client.close()

# handle_session: peercred pid is the caller (socketpair peer = this process)
control.PERF = manager
server, client = socketlib.socketpair()
child3 = subprocess.Popen(["sleep", "30"])
try:
    result = control.handle_session({"action": "game_launched", "appid": "620"}, server)
    check("session launch applied", result.get("applied") is True)
    check("session override tracks caller pid",
          ap.read_state().get("override", {}).get("pid") == os.getpid())
    try:
        control.handle_session({"action": "bogus"}, server)
        check("unknown session action rejected", False)
    except ValueError:
        pass
    try:
        control.handle_session({"action": "game_launched", "appid": "not-a-number"}, server)
        check("bad appid rejected", False)
    except ValueError:
        pass
finally:
    child3.terminate()
    child3.wait()
    server.close()
    client.close()
manager.game_exited()

# --- armada-powerd: scx state machine ---------------------------------------
class FakeProc:
    def __init__(self, command, **kwargs):
        FakeProc.launched.append(command)
        self.returncode = None
    def poll(self):
        return self.returncode
    def terminate(self):
        self.returncode = 0
    def wait(self, timeout=None):
        return self.returncode
    def kill(self):
        self.returncode = -9

FakeProc.launched = []
real_popen, real_exists = powerd.subprocess.Popen, powerd.os.path.exists
powerd.subprocess.Popen = FakeProc
powerd.os.path.exists = lambda path: True
try:
    scx = powerd.ArmadaPower.__new__(powerd.ArmadaPower)
    scx.scx_child = None
    scx.scx_spec = None
    scx.scx_failed = None
    scx.scx_warned = set()

    scx.enforce_scheduler({"scheduler": "lavd"})
    check("lavd started", FakeProc.launched[-1] == ["/usr/bin/scx_lavd"])
    scx.enforce_scheduler({"scheduler": "lavd"})
    check("same spec not restarted", len(FakeProc.launched) == 1)

    # crash, then a DIFFERENT spec must start immediately (no shared backoff)
    scx.scx_child.returncode = 1
    scx.enforce_scheduler({"scheduler": "cosmos", "schedulerDomain": [3, 4, 5, 6, 7]})
    check("switch after crash starts immediately",
          FakeProc.launched[-1] == ["/usr/bin/scx_cosmos", "--primary-domain", "3-7"])

    # crash cosmos, retrying the SAME spec is backed off
    scx.scx_child.returncode = 1
    scx.enforce_scheduler({"scheduler": "cosmos", "schedulerDomain": [3, 4, 5, 6, 7]})
    check("same failed spec backed off", len(FakeProc.launched) == 2)
    scx.enforce_scheduler({"scheduler": "lavd"})
    check("other spec unaffected by backoff", FakeProc.launched[-1] == ["/usr/bin/scx_lavd"])

    scx.enforce_scheduler({"scheduler": "eevdf"})
    check("eevdf stops scx child", scx.scx_child is None and scx.scx_spec is None)

    # a running scheduler must STOP even when the newly requested spec is
    # backed off: fallback is EEVDF, never a stale different scx
    scx.scx_failed = None
    scx.enforce_scheduler({"scheduler": "lavd"})
    scx.scx_child.returncode = 1
    scx.enforce_scheduler({"scheduler": "cosmos", "schedulerDomain": [3, 4, 5, 6, 7]})
    check("cosmos running after lavd crash", scx.scx_spec is not None)
    scx.enforce_scheduler({"scheduler": "lavd"})  # lavd still backed off
    check("mismatched scheduler stopped during backoff",
          scx.scx_child is None and scx.scx_spec is None)
finally:
    powerd.subprocess.Popen = real_popen
    powerd.os.path.exists = real_exists

# --- armada-powerd: perf_tick never leaks (it runs inside the fan loop) -----
tick = powerd.ArmadaPower.__new__(powerd.ArmadaPower)
tick.scx_child = None
tick.scx_spec = None
tick.scx_failed = None
tick.scx_warned = set()
with ap.STATE_FILE.open("w") as f:
    f.write("{ not json")
tick.perf_tick()  # corrupt state file: read_state -> {}
real_apply = ap.apply_gamescope
ap.apply_gamescope = lambda values: (_ for _ in ()).throw(RuntimeError("boom"))
try:
    tick.perf_tick()  # enforcement raising must not escape into fan_tick
finally:
    ap.apply_gamescope = real_apply
check("perf_tick contains exceptions", True)

# --- plugin: tweaks sanitize keeps the flat perf keys -----------------------
sys.path.insert(0, os.path.join(ROOT, "decky/armada-control/py_modules"))
from armada_control import tweaks as plugin_tweaks

clean = plugin_tweaks.sanitize_tweaks({
    "global": {"gamescopeNice": -5, "cores": "big"},
    "games": {"620": {"nice": 0, "scheduler": "lavd", "env": {"A": "1"}},
              "not-a-number": {"nice": 1}},
})
check("tweaks keeps global perf keys", clean["global"]["cores"] == "big")
check("tweaks keeps per-game perf keys", clean["games"]["620"]["scheduler"] == "lavd")
check("tweaks drops non-numeric appids", "not-a-number" not in clean["games"])
try:
    plugin_tweaks.sanitize_tweaks({"global": {"x": "y" * (300 * 1024)}, "games": {}})
    check("oversize tweaks rejected", False)
except ValueError:
    pass

# --- plugin: power render with editable governor ----------------------------
sys.path.insert(0, os.path.join(ROOT, "decky/armada-control/py_modules"))
from armada_control import power as plugin_power

plugin_power.FACTORY_POWER_CONFIG = plugin_power.Path(factory)
plugin_power.POWER_CONFIG = plugin_power.Path(os.path.join(WORK, "etc-armada-power.conf"))
data = plugin_power.parse_power()
factory_data = plugin_power.parse_power(plugin_power.FACTORY_POWER_CONFIG)
check("governor exposed in parse", data["profiles"]["eco"]["cpu_governor"] == "schedutil")

# untouched config renders no /etc profile sections (factory keeps tracking /usr)
rendered = plugin_power.render_power(data, factory_data)
check("unedited render stays factory-tracking", "[profile.eco]" not in rendered)

# editing only the governor writes the override
data["profiles"]["eco"]["cpu_governor"] = "performance"
rendered = plugin_power.render_power(data, factory_data)
check("edited governor written", "cpu_governor = performance" in rendered)
check("other profiles untouched", "[profile.performance]" not in rendered)

if failures:
    print(f"{len(failures)} check(s) failed", file=sys.stderr)
    sys.exit(1)
print("all perf-settings checks passed")
PYEOF

echo "PASS: perf-settings-test"
