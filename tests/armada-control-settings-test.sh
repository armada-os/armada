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

plugin_lib = root / "decky/armada-control/py_modules"
sys.path.insert(0, str(plugin_lib))
from armada_control import system as plugin_system

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

DEVICE_ENV="$ROOT/system_files/usr/libexec/armada/device-env"
DEVICE_QUIRKS="$ROOT/system_files/usr/libexec/armada/device-quirks"
DISPATCH="$ROOT/system_files/usr/libexec/armada/suspend-dispatch"

device_env() {
    env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
        ARMADA_MODEL="$1" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
        ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
        "$DEVICE_ENV" | grep -x "ARMADA_SUSPEND_MODE=$2" >/dev/null
}

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
