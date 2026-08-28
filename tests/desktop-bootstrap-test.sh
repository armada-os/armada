#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP="$ROOT/system_files/usr/libexec/armada/desktop-bootstrap"
LIB="$ROOT/system_files/usr/lib/armada/desktop-bootstrap-lib"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

assert_eq() {
    local actual="$1" expected="$2" label="$3"

    if [[ "$actual" != "$expected" ]]; then
        printf '%s: expected %q, got %q\n' "$label" "$expected" "$actual" >&2
        exit 1
    fi
}

assert_file() {
    local path="$1" expected="$2"

    assert_eq "$(<"$path")" "$expected" "$path"
}

set_pocket_ds() {
    ARMADA_DEVICE_ID=ayaneo-pocket-ds
    display_connector=DSI-1
    panel_orientation=left
    ARMADA_SECONDARY_CONNECTOR=DSI-2
    ARMADA_PRIMARY_TOUCHSCREEN='generic ft5x06 (44)'
    ARMADA_SECONDARY_TOUCHSCREEN='bottom_touchscreen'
}

# shellcheck source=/dev/null
source "$LIB"

fresh="$TEST_ROOT/fresh"
mkdir -p "$fresh"
set_pocket_ds
armada_desktop_bootstrap_state "$fresh"
assert_eq "$rotation_complete" 0 'fresh rotation'
assert_eq "$scale_complete" 0 'fresh scale'
assert_eq "$dual_complete" 0 'fresh dual layout'
assert_eq "$rotation_signature" 'v1|ayaneo-pocket-ds|DSI-1|left' 'rotation signature'
assert_eq "$scale_signature" 'v1|ayaneo-pocket-ds|DSI-1|1.5' 'scale signature'
assert_eq "$dual_signature" 'v1|ayaneo-pocket-ds|DSI-1|DSI-2|generic ft5x06 (44)|bottom_touchscreen|left|1.5' 'dual signature'

armada_write_marker "$rotation_done" "$rotation_signature"
armada_write_marker "$scale_done" "$scale_signature"
armada_write_marker "$dual_done" "$dual_signature"
armada_desktop_bootstrap_state "$fresh"
assert_eq "$rotation_complete" 1 'current rotation'
assert_eq "$scale_complete" 1 'current scale'
assert_eq "$dual_complete" 1 'current dual layout'

ARMADA_DEVICE_ID=ayn-odin-2
armada_desktop_bootstrap_state "$fresh"
assert_eq "$rotation_complete" 0 'device change rotation'
assert_eq "$scale_complete" 0 'device change scale'
assert_eq "$dual_complete" 0 'device change dual layout'

set_pocket_ds
panel_orientation=right
armada_desktop_bootstrap_state "$fresh"
assert_eq "$rotation_complete" 0 'orientation change rotation'
assert_eq "$scale_complete" 1 'orientation change scale'
assert_eq "$dual_complete" 0 'orientation change dual layout'

legacy_single="$TEST_ROOT/legacy-single"
mkdir -p "$legacy_single"
touch "$legacy_single/desktop-rotation.done"
touch "$legacy_single/desktop-scale.done"
touch "$legacy_single/desktop-dual-screen.done"
set_pocket_ds
armada_desktop_bootstrap_state "$legacy_single"
assert_eq "$rotation_complete" 0 'single-to-dual rotation'
assert_eq "$scale_complete" 0 'single-to-dual scale'
assert_eq "$dual_complete" 0 'single-to-dual layout'
[[ ! -s "$dual_done" ]]

legacy_thor="$TEST_ROOT/legacy-thor"
mkdir -p "$legacy_thor"
ARMADA_DEVICE_ID=ayn-thor
display_connector=DSI-2
panel_orientation=right
ARMADA_SECONDARY_CONNECTOR=DSI-1
ARMADA_PRIMARY_TOUCHSCREEN=top_touchscreen
ARMADA_SECONDARY_TOUCHSCREEN=bottom_touchscreen
touch "$legacy_thor/desktop-rotation-DSI-2.done"
touch "$legacy_thor/desktop-rotation.done"
touch "$legacy_thor/desktop-scale.done"
touch "$legacy_thor/desktop-dual-screen.done"
armada_desktop_bootstrap_state "$legacy_thor"
assert_eq "$rotation_complete" 1 'legacy Thor rotation'
assert_eq "$scale_complete" 0 'legacy Thor missing scale'
assert_eq "$dual_complete" 1 'legacy Thor dual layout'
assert_file "$rotation_done" "$rotation_signature"
assert_file "$dual_done" "$dual_signature"

legacy_handheld="$TEST_ROOT/legacy-handheld"
mkdir -p "$legacy_handheld"
ARMADA_DEVICE_ID=ayn-odin-2
display_connector=DSI-1
panel_orientation=right
ARMADA_SECONDARY_CONNECTOR=
ARMADA_PRIMARY_TOUCHSCREEN=
ARMADA_SECONDARY_TOUCHSCREEN=
touch "$legacy_handheld/desktop-rotation.done"
touch "$legacy_handheld/desktop-scale.done"
touch "$legacy_handheld/desktop-dual-screen.done"
armada_desktop_bootstrap_state "$legacy_handheld"
assert_eq "$rotation_complete" 1 'legacy single rotation'
assert_eq "$scale_complete" 1 'legacy single scale'
assert_eq "$dual_complete" 1 'legacy single layout'
assert_file "$rotation_done" "$rotation_signature"
assert_file "$scale_done" "$scale_signature"
assert_file "$dual_done" "$dual_signature"

write_error="$TEST_ROOT/write-error"
if armada_write_marker /proc/armada-desktop-marker-test value 2>"$write_error"; then
    echo 'marker write unexpectedly succeeded' >&2
    exit 1
fi
[[ ! -s "$write_error" ]]

stub_bin="$TEST_ROOT/bin"
mkdir -p "$stub_bin"
printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "$stub_bin/dbus-update-activation-environment"
printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "$stub_bin/device-env"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf '\''%s\n'\'' "$*" >> "$KSCREEN_LOG"' \
    'if [[ "$*" == *".rotation."* && "${KSCREEN_FAIL_ROTATION:-0}" == 1 ]]; then exit 1; fi' \
    'exit 0' > "$stub_bin/kscreen-doctor"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf '\''setup\n'\'' >> "$SETUP_LOG"' \
    'exit "${SETUP_FAIL:-0}"' > "$stub_bin/setup-dual-screen"
chmod +x "$stub_bin"/*

run_bootstrap() {
    local config_dir="$1"

    env \
        XDG_SESSION_TYPE=wayland \
        XDG_CONFIG_HOME="$config_dir" \
        HOME="$TEST_ROOT/home" \
        PATH="$stub_bin:/usr/bin:/bin" \
        ARMADA_DEVICE_ENV="$stub_bin/device-env" \
        ARMADA_SETUP_DUAL_SCREEN="$stub_bin/setup-dual-screen" \
        ARMADA_DEVICE_ID=test-dual \
        ARMADA_PRIMARY_CONNECTOR=DSI-1 \
        ARMADA_PANEL_ORIENTATION=left \
        ARMADA_SECONDARY_CONNECTOR=DSI-2 \
        ARMADA_PRIMARY_TOUCHSCREEN= \
        ARMADA_SECONDARY_TOUCHSCREEN= \
        KSCREEN_LOG="$KSCREEN_LOG" \
        SETUP_LOG="$SETUP_LOG" \
        KSCREEN_FAIL_ROTATION="${KSCREEN_FAIL_ROTATION:-0}" \
        "$BOOTSTRAP"
}

e2e_config="$TEST_ROOT/e2e"
e2e_state="$e2e_config/armada"
KSCREEN_LOG="$TEST_ROOT/kscreen.log"
SETUP_LOG="$TEST_ROOT/setup.log"
: > "$KSCREEN_LOG"
: > "$SETUP_LOG"
KSCREEN_FAIL_ROTATION=1 run_bootstrap "$e2e_config"
[[ ! -e "$e2e_state/desktop-rotation.done" ]]
[[ -e "$e2e_state/desktop-scale.done" ]]
[[ ! -e "$e2e_state/desktop-dual-screen.done" ]]
[[ ! -s "$SETUP_LOG" ]]

KSCREEN_FAIL_ROTATION=0 run_bootstrap "$e2e_config"
assert_file "$e2e_state/desktop-rotation.done" 'v1|test-dual|DSI-1|left'
assert_file "$e2e_state/desktop-scale.done" 'v1|test-dual|DSI-1|1.5'
assert_file "$e2e_state/desktop-dual-screen.done" 'v1|test-dual|DSI-1|DSI-2|||left|1.5'
assert_eq "$(wc -l < "$SETUP_LOG")" 1 'dual setup count'
kscreen_calls="$(wc -l < "$KSCREEN_LOG")"
run_bootstrap "$e2e_config"
assert_eq "$(wc -l < "$SETUP_LOG")" 1 'dual setup rerun count'
assert_eq "$(wc -l < "$KSCREEN_LOG")" "$kscreen_calls" 'kscreen no-op rerun'

bash -n "$BOOTSTRAP" "$LIB"

printf 'Desktop bootstrap integration tests passed\n'
