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
    {"data": "fake", "label": "Fake"},
    {"data": "s2idle", "label": "s2idle"},
    {"data": "deep", "label": "Deep"},
]

control.SLEEP_CONFIG.write_text("future_sleep_setting=keep\n")
control.NM_IGNORE_SLEEP.touch()
assert control.action_set_sleep_mode({"value": "s2idle"}) == {"value": "s2idle"}
assert control.MEM_SLEEP_PATH.read_text() == "s2idle\n"
assert control.SLEEP_CONFIG.read_text() == (
    "future_sleep_setting=keep\nsuspend_mode=s2idle\n"
)
assert not control.NM_IGNORE_SLEEP.exists()

control.MEM_SLEEP_PATH.write_text("[s2idle] deep\n")
assert control.action_set_sleep_mode({"value": "deep"}) == {"value": "deep"}
assert control.MEM_SLEEP_PATH.read_text() == "deep\n"
assert control.SLEEP_CONFIG.read_text() == (
    "future_sleep_setting=keep\nsuspend_mode=deep\n"
)
assert not control.NM_IGNORE_SLEEP.exists()

assert control.action_set_sleep_mode({"value": "fake"}) == {"value": "fake"}
assert control.SLEEP_CONFIG.read_text() == (
    "future_sleep_setting=keep\nsuspend_mode=fake\n"
)
assert control.NM_IGNORE_SLEEP.exists()

control.MEM_SLEEP_PATH.write_text("[s2idle]\n")
assert plugin_system.sleep_modes() == [
    {"data": "fake", "label": "Fake"},
    {"data": "s2idle", "label": "s2idle"},
]
try:
    control.action_set_sleep_mode({"value": "deep"})
except RuntimeError:
    pass
else:
    raise AssertionError("unavailable deep sleep setting was accepted")
PYEOF

printf '[s2idle] deep\n' >"$WORK/mem_sleep"
printf 'suspend_mode=s2idle\n' >"$WORK/sleep.conf"
env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="AYN Odin 2" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-env" |
    grep -x 'ARMADA_SUSPEND_MODE=s2idle' >/dev/null

printf 'suspend_mode=deep\n' >"$WORK/sleep.conf"
env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="AYN Odin 2" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-env" |
    grep -x 'ARMADA_SUSPEND_MODE=deep' >/dev/null

printf 'suspend_mode = fake\nsuspend_mode = deep\n' >"$WORK/sleep.conf"
env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="AYN Odin 2" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-env" |
    grep -x 'ARMADA_SUSPEND_MODE=deep' >/dev/null

printf 'suspend_mode = deep' >"$WORK/sleep.conf"
env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="AYN Odin 2" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-env" |
    grep -x 'ARMADA_SUSPEND_MODE=deep' >/dev/null

printf '[s2idle]\n' >"$WORK/mem_sleep"
env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="Retroid Pocket 5" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-env" |
    grep -x 'ARMADA_SUSPEND_MODE=s2idle' >/dev/null

printf '[deep]\n' >"$WORK/mem_sleep"
printf 'suspend_mode=s2idle\n' >"$WORK/sleep.conf"
env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="Retroid Pocket 5" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-env" |
    grep -x 'ARMADA_SUSPEND_MODE=deep' >/dev/null

printf '[s2idle]\n' >"$WORK/mem_sleep"
printf 'suspend_mode=deep\n' >"$WORK/sleep.conf"
env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="AYN Odin 2" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-env" |
    grep -x 'ARMADA_SUSPEND_MODE=fake' >/dev/null

: >"$WORK/mem_sleep"
env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="Retroid Pocket 5" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-env" |
    grep -x 'ARMADA_SUSPEND_MODE=fake' >/dev/null

rm -f "$WORK/sleep.conf"
printf '[s2idle] deep\n' >"$WORK/mem_sleep"
env ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="AYN Odin 3" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-env" |
    grep -x 'ARMADA_SUSPEND_MODE=s2idle' >/dev/null

# Boot-time quirks reapply a saved native mode and NetworkManager policy.
printf '[s2idle] deep\n' >"$WORK/mem_sleep"
printf 'suspend_mode=s2idle\n' >"$WORK/sleep.conf"
touch "$WORK/ignore-sleep"
env ARMADA_DEVICE_ENV="$ROOT/system_files/usr/libexec/armada/device-env" \
    ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="AYN Odin 2" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    ARMADA_NM_IGNORE_SLEEP="$WORK/ignore-sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-quirks"
grep -x 's2idle' "$WORK/mem_sleep" >/dev/null
[[ ! -e "$WORK/ignore-sleep" ]]

printf '[s2idle] deep\n' >"$WORK/mem_sleep"
printf 'suspend_mode=fake\n' >"$WORK/sleep.conf"
env ARMADA_DEVICE_ENV="$ROOT/system_files/usr/libexec/armada/device-env" \
    ARMADA_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices" \
    ARMADA_MODEL="AYN Odin 2" ARMADA_SLEEP_CONFIG="$WORK/sleep.conf" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    ARMADA_NM_IGNORE_SLEEP="$WORK/ignore-sleep" \
    "$ROOT/system_files/usr/libexec/armada/device-quirks"
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

printf '[s2idle] deep\n' >"$WORK/mem_sleep"
env TEST_SLEEP_MODE=deep TEST_SLEEP_CALL="$WORK/sleep-call" \
    ARMADA_DEVICE_ENV="$WORK/device-env" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    ARMADA_SYSTEMD_SLEEP="$WORK/systemd-sleep" \
    "$ROOT/system_files/usr/libexec/armada/suspend-dispatch"
grep -x 'deep' "$WORK/mem_sleep" >/dev/null
grep -x 'suspend' "$WORK/sleep-call" >/dev/null

printf '[s2idle]\n' >"$WORK/mem_sleep"
rm -f "$WORK/fake-sleep-call"
env TEST_SLEEP_MODE=deep TEST_SLEEP_CALL="$WORK/sleep-call" \
    TEST_FAKE_SLEEP_CALL="$WORK/fake-sleep-call" \
    ARMADA_DEVICE_ENV="$WORK/device-env" \
    ARMADA_FAKE_SUSPEND="$WORK/fake-suspend" \
    ARMADA_MEM_SLEEP_PATH="$WORK/mem_sleep" \
    ARMADA_SYSTEMD_SLEEP="$WORK/systemd-sleep" \
    "$ROOT/system_files/usr/libexec/armada/suspend-dispatch" 2>/dev/null
grep -x 'sleep' "$WORK/fake-sleep-call" >/dev/null

echo "Armada Control settings tests passed"
