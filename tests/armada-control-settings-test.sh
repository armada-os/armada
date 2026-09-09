#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 - "$ROOT" "$WORK" <<'PYEOF'
import importlib.machinery
import importlib.util
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
work = pathlib.Path(sys.argv[2])
lib = root / "system_files/usr/lib/armada"
sys.path.insert(0, str(lib))
import armada_perf  # noqa: F401

control_path = root / "system_files/usr/libexec/armada/armada-control"
loader = importlib.machinery.SourceFileLoader("armada_control", str(control_path))
spec = importlib.util.spec_from_loader("armada_control", loader)
control = importlib.util.module_from_spec(spec)
loader.exec_module(control)

control.SLEEP_CONFIG = work / "sleep.conf"
control.NM_IGNORE_SLEEP = work / "ignore-sleep"
control.MEM_SLEEP_PATH = work / "mem_sleep"
control.MEM_SLEEP_PATH.write_text("[s2idle] deep\n")
control.BOTTOM_SCREEN_BRIGHTNESS_PATH = work / "bottom-screen-brightness"
control.BACKLIGHT_ROOT = work / "backlight"
secondary_backlight = control.BACKLIGHT_ROOT / "secondary"
secondary_backlight.mkdir(parents=True)
(secondary_backlight / "brightness").write_text("128\n")
(secondary_backlight / "max_brightness").write_text("255\n")


class Result:
    def __init__(self, returncode):
        self.returncode = returncode


unit_state = {"enabled": False, "game_mode": True}
systemctl_calls = []


def fake_session_systemctl(*args, check=True, timeout=30):
    systemctl_calls.append(args)
    if args[:2] == ("is-enabled", "--quiet"):
        return Result(0 if unit_state["enabled"] else 1)
    if args[:2] == ("is-active", "--quiet"):
        return Result(0 if unit_state["game_mode"] else 3)
    if args[0] == "enable":
        unit_state["enabled"] = True
    elif args[0] == "disable":
        unit_state["enabled"] = False
    return Result(0)


control.session_systemctl = fake_session_systemctl
control.device_env = lambda: {
    "ARMADA_SECONDARY_CONNECTOR": "DSI-1",
    "ARMADA_SECONDARY_BACKLIGHT": "secondary",
    "ARMADA_SECONDARY_TOUCHSCREEN": "bottom_touchscreen",
}
assert control.action_get_bottom_screen_enabled({}) == {"enabled": False}
assert control.action_set_bottom_screen_enabled({"enabled": True}) == {"enabled": True}
assert ("enable", control.BOTTOM_SCREEN_SERVICE) in systemctl_calls
assert ("start", control.BOTTOM_SCREEN_SERVICE) in systemctl_calls
assert control.action_set_bottom_screen_enabled({"enabled": False}) == {"enabled": False}
assert ("disable", "--now", control.BOTTOM_SCREEN_SERVICE) in systemctl_calls

unit_state["game_mode"] = False
systemctl_calls.clear()
assert control.action_set_bottom_screen_enabled({"enabled": True}) == {"enabled": True}
assert ("start", control.BOTTOM_SCREEN_SERVICE) not in systemctl_calls
control.action_set_bottom_screen_enabled({"enabled": False})

control.device_env = lambda: {}
try:
    control.action_set_bottom_screen_enabled({"enabled": True})
except RuntimeError:
    pass
else:
    raise AssertionError("unsupported bottom screen was enabled")

try:
    control.action_set_bottom_screen_enabled({"enabled": "yes"})
except ValueError:
    pass
else:
    raise AssertionError("invalid bottom-screen state was accepted")

control.device_env = lambda: {"ARMADA_SECONDARY_BACKLIGHT": "secondary"}
assert control.action_get_bottom_screen_brightness({}) == {
    "supported": True,
    "brightness": 50,
}
assert control.action_set_bottom_screen_brightness({"brightness": 40}) == {"brightness": 40}
assert (secondary_backlight / "brightness").read_text() == "102\n"
assert control.BOTTOM_SCREEN_BRIGHTNESS_PATH.read_text() == "40\n"

# Driver and session changes can reset the backlight; the saved preference wins.
(secondary_backlight / "brightness").write_text("255\n")
control.restore_bottom_screen_brightness()
assert (secondary_backlight / "brightness").read_text() == "102\n"

# Missing and malformed preferences leave the hardware's current value alone.
control.BOTTOM_SCREEN_BRIGHTNESS_PATH.unlink()
(secondary_backlight / "brightness").write_text("128\n")
control.restore_bottom_screen_brightness()
assert (secondary_backlight / "brightness").read_text() == "128\n"
control.BOTTOM_SCREEN_BRIGHTNESS_PATH.write_text("invalid\n")
control.restore_bottom_screen_brightness()
assert (secondary_backlight / "brightness").read_text() == "128\n"

secondary_backlight_4096 = control.BACKLIGHT_ROOT / "secondary-4096"
secondary_backlight_4096.mkdir()
(secondary_backlight_4096 / "brightness").write_text("4096\n")
(secondary_backlight_4096 / "max_brightness").write_text("4096\n")
control.device_env = lambda: {"ARMADA_SECONDARY_BACKLIGHT": "secondary-4096"}
assert control.action_set_bottom_screen_brightness({"brightness": 25}) == {"brightness": 25}
assert (secondary_backlight_4096 / "brightness").read_text() == "1024\n"
assert control.BOTTOM_SCREEN_BRIGHTNESS_PATH.read_text() == "25\n"

for invalid in (True, "40", -1, 101):
    try:
        control.action_set_bottom_screen_brightness({"brightness": invalid})
    except ValueError:
        pass
    else:
        raise AssertionError("invalid bottom-screen brightness was accepted")

control.device_env = lambda: {}
assert control.action_get_bottom_screen_brightness({}) == {
    "supported": False,
    "brightness": 0,
}
try:
    control.action_set_bottom_screen_brightness({"brightness": 50})
except RuntimeError:
    pass
else:
    raise AssertionError("unsupported bottom-screen brightness was changed")

plugin_lib = root / "decky/armada-control/py_modules"
sys.path.insert(0, str(plugin_lib))
from armada_control import system as plugin_system

def fake_plugin_call(action, **payload):
    if action == "get_bottom_screen_brightness":
        return {"supported": True, "brightness": 50}
    if action == "set_bottom_screen_brightness":
        return {"brightness": int(payload["brightness"])}
    return {"enabled": action == "get_bottom_screen_enabled" or bool(payload.get("enabled"))}


plugin_system.call = fake_plugin_call
assert plugin_system.bottom_screen_enabled()
assert plugin_system.set_bottom_screen_enabled(True)
assert plugin_system.bottom_screen_brightness() == 50
assert plugin_system.set_bottom_screen_brightness(40) == 40

plugin_system.MEM_SLEEP_PATH = control.MEM_SLEEP_PATH
assert plugin_system.sleep_modes() == [
    {"data": "s2idle", "label": "Native"},
    {"data": "fake", "label": "Fake"},
]

control.SLEEP_CONFIG.write_text("future_sleep_setting=keep\n")
control.NM_IGNORE_SLEEP.touch()
assert control.action_set_sleep_mode({"value": "s2idle"}) == {"value": "s2idle"}
assert control.MEM_SLEEP_PATH.read_text() == "s2idle\n"
assert control.SLEEP_CONFIG.read_text() == (
    "future_sleep_setting=keep\nsuspend_mode=s2idle\n"
)
assert not control.NM_IGNORE_SLEEP.exists()

assert control.action_set_sleep_mode({"value": "fake"}) == {"value": "fake"}
assert control.SLEEP_CONFIG.read_text() == (
    "future_sleep_setting=keep\nsuspend_mode=fake\n"
)
assert control.NM_IGNORE_SLEEP.exists()

control.MEM_SLEEP_PATH.write_text("[s2idle] deep\n")
try:
    control.action_set_sleep_mode({"value": "deep"})
except RuntimeError:
    pass
else:
    raise AssertionError("retired deep sleep setting was accepted")

control.MEM_SLEEP_PATH.write_text("[deep]\n")
assert plugin_system.sleep_modes() == [{"data": "fake", "label": "Fake"}]
try:
    control.action_set_sleep_mode({"value": "s2idle"})
except RuntimeError:
    pass
else:
    raise AssertionError("unavailable s2idle sleep setting was accepted")
PYEOF

grep -Fq 'After=armada-device-quirks.service inputplumber.service armada-powerd.service' \
    "$ROOT/system_files/usr/lib/systemd/system/armada-control.service"

DEVICE_ENV="$ROOT/system_files/usr/libexec/armada/device-env"
DEVICE_QUIRKS="$ROOT/system_files/usr/libexec/armada/device-quirks"
DISPATCH="$ROOT/system_files/usr/libexec/armada/suspend-dispatch"

device_env() {
    env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
        ARMADA_MODEL="$1" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
        ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
        "$DEVICE_ENV" | grep -x "ARMADA_SUSPEND_MODE=$2" >/dev/null
}

env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="AYN Thor" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-env" |
    grep -Fx 'ARMADA_SECONDARY_BACKLIGHT=ae94000.dsi.0' >/dev/null
env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="AYANEO Pocket DS" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-env" |
    grep -Fx 'ARMADA_SECONDARY_BACKLIGHT=sy7758-backlight' >/dev/null

printf '[s2idle] deep\n' >"$WORK/mem_sleep"
printf 'suspend_mode=s2idle\n' >"$WORK/sleep.conf"
device_env "AYN Odin 2" s2idle

printf 'suspend_mode=deep\n' >"$WORK/sleep.conf"
device_env "AYN Odin 2" s2idle

printf 'suspend_mode = s2idle\nsuspend_mode = fake\n' >"$WORK/sleep.conf"
device_env "AYN Odin 2" fake

printf 'suspend_mode = fake' >"$WORK/sleep.conf"
device_env "AYN Odin 2" fake

rm -f "$WORK/sleep.conf"
device_env "AYN Odin 2" s2idle
device_env "Retroid Pocket 5" s2idle
device_env "AYN Odin 3" s2idle

printf '[deep]\n' >"$WORK/mem_sleep"
printf 'suspend_mode=s2idle\n' >"$WORK/sleep.conf"
device_env "Retroid Pocket 5" fake

printf 'suspend_mode=deep\n' >"$WORK/sleep.conf"
device_env "AYN Odin 2" fake

: >"$WORK/mem_sleep"
rm -f "$WORK/sleep.conf"
device_env "Retroid Pocket 5" fake

# Boot-time quirks reapply the saved mode and NetworkManager policy.
printf '[s2idle] deep\n' >"$WORK/mem_sleep"
printf 'future_sleep_setting=keep\nsuspend_mode=deep\n' >"$WORK/sleep.conf"
touch "$WORK/ignore-sleep"
env ARMADA_DEVICE_ENV="$DEVICE_ENV" \
    ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="AYN Odin 2" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    ARMADA_NM_IGNORE_SLEEP="$WORK/ignore-sleep" \
    "$DEVICE_QUIRKS" >/dev/null
grep -x 's2idle' "$WORK/mem_sleep" >/dev/null
[[ "$(cat "$WORK/sleep.conf")" == "future_sleep_setting=keep
suspend_mode=s2idle" ]]
[[ ! -e "$WORK/ignore-sleep" ]]

printf '[s2idle] deep\n' >"$WORK/mem_sleep"
printf 'suspend_mode=fake\n' >"$WORK/sleep.conf"
env ARMADA_DEVICE_ENV="$DEVICE_ENV" \
    ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="AYN Odin 2" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    ARMADA_NM_IGNORE_SLEEP="$WORK/ignore-sleep" \
    "$DEVICE_QUIRKS" >/dev/null
grep -Fx '[s2idle] deep' "$WORK/mem_sleep" >/dev/null
[[ -e "$WORK/ignore-sleep" ]]

printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf "ARMADA_SUSPEND_MODE=%s\\n" "$TEST_SLEEP_MODE"' \
    >"$WORK/device-env"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf "%s\\n" "$*" >"$TEST_SLEEP_CALL"' \
    >"$WORK/systemd-sleep"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf "%s\\n" "$*" >"$TEST_FAKE_SLEEP_CALL"' \
    >"$WORK/fake-suspend"
chmod +x "$WORK/device-env" "$WORK/systemd-sleep" "$WORK/fake-suspend"

dispatch() {
    rm -f "$WORK/sleep-call" "$WORK/fake-sleep-call"
    env TEST_SLEEP_MODE="$1" TEST_SLEEP_CALL="$WORK/sleep-call" \
        TEST_FAKE_SLEEP_CALL="$WORK/fake-sleep-call" \
        ARMADA_DEVICE_ENV="$WORK/device-env" \
        ARMADA_FAKE_SUSPEND="$WORK/fake-suspend" \
        ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
        ARMADA_SYSTEMD_SLEEP="$WORK/systemd-sleep" \
        "$DISPATCH" 2>/dev/null
}

printf '[s2idle] deep\n' >"$WORK/mem_sleep"
dispatch s2idle
grep -x 's2idle' "$WORK/mem_sleep" >/dev/null
grep -x 'suspend' "$WORK/sleep-call" >/dev/null

printf '[s2idle] deep\n' >"$WORK/mem_sleep"
dispatch deep
grep -x 'sleep' "$WORK/fake-sleep-call" >/dev/null
[[ ! -e "$WORK/sleep-call" ]]

printf '[deep]\n' >"$WORK/mem_sleep"
dispatch s2idle
grep -x 'sleep' "$WORK/fake-sleep-call" >/dev/null
[[ ! -e "$WORK/sleep-call" ]]

# A device-env that resolves nothing must not reach real suspend.
printf '%s\n' '#!/usr/bin/env bash' 'exit 1' >"$WORK/device-env"
chmod +x "$WORK/device-env"
printf '[s2idle] deep\n' >"$WORK/mem_sleep"
dispatch s2idle
grep -x 'sleep' "$WORK/fake-sleep-call" >/dev/null
[[ ! -e "$WORK/sleep-call" ]]

echo "Armada Control settings tests passed"
