#!/usr/bin/env bash
# Exercises fresh-lid-close power-key wake gating with fake input/sysfs state.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/system_files/usr/lib/systemd/system-sleep/50-armada-powerbutton-suspend"
[[ -x "$HOOK" ]]
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT

input_class="$tmp/sys/class/input"
pwrkey="$tmp/sys/devices/platform/soc/pon:pwrkey"
wakeup="$pwrkey/power/wakeup"
user_runtime_dir="$tmp/run/user"
marker="$user_runtime_dir/armada-powerbuttond/lid-close-ms"
state_file="$tmp/run/armada/powerkey-wakeup-lid-gated"

mkdir -p "$input_class/event0" "$pwrkey/input/input0/capabilities" "$pwrkey/power" \
    "$(dirname "$marker")"
ln -s "$pwrkey/input/input0" "$input_class/event0/device"
printf 'pmic_pwrkey\n' >"$pwrkey/input/input0/name"
printf '0\n' >"$pwrkey/input/input0/capabilities/sw"
printf 'enabled\n' >"$wakeup"

input_lib="$tmp/input-lib"
printf '%s\n' \
    'armada_lid_closed() { [[ "${ARMADA_TEST_LID_CLOSED:-0}" == 1 ]]; }' \
    >"$input_lib"

run_hook() {
    local env_args=(
        "ARMADA_INPUT_CLASS_DIR=$input_class"
        "ARMADA_RUN_DIR=$tmp/run/armada"
        "ARMADA_INPUT_LIB=$input_lib"
        "ARMADA_SYSFS_ROOT=$tmp/sys"
        "ARMADA_USER_RUNTIME_DIR=$user_runtime_dir"
        "ARMADA_SESSION_USER=$(id -un)"
        "ARMADA_NOW_MS=100000"
        "ARMADA_TEST_LID_CLOSED=${ARMADA_TEST_LID_CLOSED:-0}"
    )
    if [[ "${ARMADA_TEST_DEFAULT_MARKER:-0}" != 1 ]]; then
        env_args+=("ARMADA_LID_CLOSE_MARKER=$marker")
    fi
    env "${env_args[@]}" bash "$HOOK" "$@" 2>"$tmp/hook.log"
}

# No fresh close event: fail open even if the switch claims closed.
ARMADA_TEST_LID_CLOSED=1 run_hook pre suspend
[[ "$(<"$wakeup")" == enabled && ! -e "$state_file" ]]

# The daemon and root hook independently derive the same default marker path.
printf '95000\n' >"$marker"
ARMADA_TEST_DEFAULT_MARKER=1 ARMADA_TEST_LID_CLOSED=1 run_hook pre suspend
[[ "$(<"$wakeup")" == disabled && ! -e "$marker" ]]
run_hook post suspend
[[ "$(<"$wakeup")" == enabled && ! -e "$state_file" ]]

printf '80000\n' >"$marker"
ARMADA_TEST_LID_CLOSED=1 run_hook pre suspend
[[ "$(<"$wakeup")" == enabled && ! -e "$state_file" ]]

printf 'invalid\n' >"$marker"
ARMADA_TEST_LID_CLOSED=1 run_hook pre suspend
[[ "$(<"$wakeup")" == enabled && ! -e "$state_file" ]]

printf '100001\n' >"$marker"
ARMADA_TEST_LID_CLOSED=1 run_hook pre suspend
[[ "$(<"$wakeup")" == enabled && ! -e "$state_file" ]]

# A fresh event is insufficient if the lid no longer reads closed.
printf '95000\n' >"$marker"
ARMADA_TEST_LID_CLOSED=0 run_hook pre suspend
[[ "$(<"$wakeup")" == enabled && -e "$marker" ]]

# Fresh close plus closed state gates wake, consumes the marker, then restores.
ARMADA_TEST_LID_CLOSED=1 run_hook pre suspend
[[ "$(<"$wakeup")" == disabled ]]
[[ "$(<"$state_file")" == "$wakeup" && ! -e "$marker" ]]
run_hook post suspend
[[ "$(<"$wakeup")" == enabled && ! -e "$state_file" ]]

# Never disable an aggregate input node that also exposes SW_LID.
printf 'Power Button\n' >"$pwrkey/input/input0/name"
printf '1\n' >"$pwrkey/input/input0/capabilities/sw"
printf '95000\n' >"$marker"
ARMADA_TEST_LID_CLOSED=1 run_hook pre suspend
[[ "$(<"$wakeup")" == enabled && ! -e "$state_file" && -e "$marker" ]]
printf 'pmic_pwrkey\n' >"$pwrkey/input/input0/name"
printf '0\n' >"$pwrkey/input/input0/capabilities/sw"

# The older PM8941 driver used by Flip 2 follows the same path.
printf 'pm8941_pwrkey\n' >"$pwrkey/input/input0/name"
printf '95000\n' >"$marker"
ARMADA_TEST_LID_CLOSED=1 run_hook pre suspend
[[ "$(<"$wakeup")" == disabled && ! -e "$marker" ]]
run_hook post suspend
[[ "$(<"$wakeup")" == enabled && ! -e "$state_file" ]]

# Preserve an administrator's pre-existing disabled policy.
printf 'disabled\n' >"$wakeup"
printf '95000\n' >"$marker"
ARMADA_TEST_LID_CLOSED=1 run_hook pre suspend
[[ "$(<"$wakeup")" == disabled && ! -e "$state_file" ]]

# A state file can restore only a wakeup control beneath the expected sysfs.
invalid_wakeup="$tmp/not-sys/power/wakeup"
mkdir -p "$(dirname "$invalid_wakeup")"
printf 'disabled\n' >"$invalid_wakeup"
printf '%s\n' "$invalid_wakeup" >"$state_file"
run_hook pre suspend
[[ "$(<"$invalid_wakeup")" == disabled && -e "$state_file" ]]
rm -f -- "$state_file"

# Recover stale state before evaluating a later suspend.
printf '%s\n' "$wakeup" >"$state_file"
rm -f -- "$marker"
run_hook pre suspend
[[ "$(<"$wakeup")" == enabled && ! -e "$state_file" ]]

# Ignore unrelated sleep operations.
printf '95000\n' >"$marker"
ARMADA_TEST_LID_CLOSED=1 run_hook pre hibernate
[[ "$(<"$wakeup")" == enabled && ! -e "$state_file" ]]

printf 'power-button suspend test passed\n'
