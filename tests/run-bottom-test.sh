#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_BOTTOM="$ROOT/system_files/usr/bin/armada-run-bottom"
BOTTOM_GAMESCOPE="$ROOT/system_files/usr/libexec/armada/bottom-gamescope"
BOTTOM_READY="$ROOT/system_files/usr/libexec/armada/bottom-gamescope-ready"
BOTTOM_SERVICE="$ROOT/system_files/usr/lib/systemd/user/armada-bottom-screen.service"
GAMESCOPE_SERVICE="$ROOT/system_files/usr/lib/systemd/user/armada-bottom-gamescope.service"
SESSION_DROPIN="$ROOT/system_files/usr/lib/systemd/user/gamescope-session-plus@steam.service.d/30-armada-gamescope.conf"
WAYDROID_INPUT_SETUP="$ROOT/system_files/usr/libexec/armada/waydroid-input-setup"
FAKE_SUSPEND="$ROOT/system_files/usr/libexec/armada/fake-suspend"
LAUNCH_STEAM="$ROOT/system_files/usr/libexec/armada/launch-steam"
tmp="$(mktemp -d)"
socket_pid=

cleanup() {
    [[ -z "$socket_pid" ]] || kill "$socket_pid" 2>/dev/null || true
    rm -rf -- "$tmp"
}
trap cleanup EXIT

device_env="$tmp/device-env"
gamescope="$tmp/gamescope"
lease_socket="$tmp/gamescope-lease.sock"
args_file="$tmp/args"
env_file="$tmp/env"

printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf '\''ARMADA_SECONDARY_CONNECTOR=%q\n'\'' "${TEST_SECONDARY_CONNECTOR-DSI-1}"' \
    'printf '\''ARMADA_SECONDARY_TOUCHSCREEN=%q\n'\'' "${TEST_SECONDARY_TOUCHSCREEN-bottom_touchscreen}"' \
    'printf '\''ARMADA_PANEL_ORIENTATION=%q\n'\'' "${TEST_PANEL_ORIENTATION-right}"' \
    >"$device_env"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf '\''%s\n'\'' "${DISPLAY-unset}" "${WAYLAND_DISPLAY-unset}" "${GAMESCOPE_WAYLAND_DISPLAY-unset}" >"$ENV_FILE"' \
    'printf '\''%s\0'\'' "$@" >"$ARGS_FILE"' \
    >"$gamescope"
chmod +x "$device_env" "$gamescope"

python3 -c 'import socket,sys,time; s=socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); s.listen(); time.sleep(30)' "$lease_socket" &
socket_pid=$!
for _ in {1..50}; do
    [[ -S "$lease_socket" ]] && break
    sleep 0.02
done
[[ -S "$lease_socket" ]]

env \
    DISPLAY=outer-x11 \
    WAYLAND_DISPLAY=outer-wayland \
    GAMESCOPE_WAYLAND_DISPLAY=gamescope-0 \
    ARMADA_DEVICE_ENV="$device_env" \
    ARMADA_GAMESCOPE="$gamescope" \
    GAMESCOPE_LEASE_SOCK="$lease_socket" \
    ARGS_FILE="$args_file" \
    ENV_FILE="$env_file" \
    "$BOTTOM_GAMESCOPE"

mapfile -d '' -t actual <"$args_file"
expected=(
    --backend drm
    --drm-lease-client "$lease_socket"
    --drm-lease-yield
    --expose-wayland
    --force-windows-fullscreen
    --xwayland-count 1
    --default-touch-mode 4
    --force-orientation right
    --force-composition-rotation
    -- /usr/libexec/armada/bottom-gamescope-ready
)
[[ "${#actual[@]}" == "${#expected[@]}" ]]
for i in "${!expected[@]}"; do
    [[ "${actual[$i]}" == "${expected[$i]}" ]]
done
[[ "$(<"$env_file")" == $'unset\nunset\nunset' ]]

if env \
    TEST_SECONDARY_CONNECTOR= \
    ARMADA_DEVICE_ENV="$device_env" \
    ARMADA_GAMESCOPE="$gamescope" \
    GAMESCOPE_LEASE_SOCK="$lease_socket" \
    "$BOTTOM_GAMESCOPE" 2>"$tmp/no-display-device"; then
    echo 'missing secondary display unexpectedly succeeded' >&2
    exit 1
fi
grep -q 'device has no secondary display' "$tmp/no-display-device"

if env \
    ARMADA_DEVICE_ENV="$device_env" \
    ARMADA_GAMESCOPE="$gamescope" \
    GAMESCOPE_LEASE_SOCK="$tmp/missing.sock" \
    "$BOTTOM_GAMESCOPE" 2>"$tmp/no-socket"; then
    echo 'missing lease socket unexpectedly succeeded' >&2
    exit 1
fi
grep -q 'DRM lease socket is unavailable' "$tmp/no-socket"

# The probe must not need the lease or start anything.
rm -f "$args_file"
env \
    ARMADA_DEVICE_ENV="$device_env" \
    ARMADA_GAMESCOPE="$gamescope" \
    GAMESCOPE_LEASE_SOCK="$tmp/missing.sock" \
    ARGS_FILE="$args_file" \
    ENV_FILE="$env_file" \
    "$BOTTOM_GAMESCOPE" --supported
[[ ! -e "$args_file" ]]
if env \
    TEST_SECONDARY_CONNECTOR= \
    ARMADA_DEVICE_ENV="$device_env" \
    ARMADA_GAMESCOPE="$gamescope" \
    "$BOTTOM_GAMESCOPE" --supported 2>/dev/null; then
    echo 'single-screen device unexpectedly supported' >&2
    exit 1
fi

mkdir -p "$tmp/bin" "$tmp/runtime"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf '\''%s\n'\'' "$*" >"$XDG_RUNTIME_DIR/sleep-args"' \
    >"$tmp/bin/sleep"
chmod +x "$tmp/bin/sleep"
# Stands in for gamescope's environment before it set anything for its children.
env -i PATH="$tmp/bin:$PATH" XDG_RUNTIME_DIR="$tmp/runtime" KEPT=same CHANGED=old REMOVED=gamescope /usr/bin/sleep 30 &
gamescope_pid=$!
env -i \
    PATH="$tmp/bin:$PATH" \
    XDG_RUNTIME_DIR="$tmp/runtime" \
    ARMADA_BOTTOM_GAMESCOPE_PID="$gamescope_pid" \
    KEPT=same \
    CHANGED=new \
    XDG_SESSION_TYPE=wayland \
    SPACED='a b' \
    DISPLAY=:2 \
    WAYLAND_DISPLAY=gamescope-1 \
    GAMESCOPE_WAYLAND_DISPLAY=gamescope-1 \
    "$BOTTOM_READY"
kill "$gamescope_pid"
[[ "$(readlink "$tmp/runtime/gamescope-secondary")" == gamescope-1 ]]
bottom_env="$tmp/runtime/armada-bottom-env"
for line in 'unset REMOVED' CHANGED=new XDG_SESSION_TYPE=wayland 'SPACED=a\ b' DISPLAY=:2; do
    grep -Fxq "$line" "$bottom_env"
done
if grep -q '^KEPT=' "$bottom_env"; then
    echo 'bottom env repeats a variable gamescope did not set' >&2
    exit 1
fi
[[ "$(tail -n 2 "$bottom_env")" == $'WAYLAND_DISPLAY=gamescope-secondary\nGAMESCOPE_WAYLAND_DISPLAY=gamescope-secondary' ]]
[[ "$(<"$tmp/runtime/sleep-args")" == infinity ]]

client_env="$tmp/client-env"
env \
    XDG_RUNTIME_DIR="$tmp/runtime" \
    DISPLAY=outer-x11 \
    WAYLAND_DISPLAY=outer-wayland \
    GAMESCOPE_WAYLAND_DISPLAY=gamescope-0 \
    REMOVED=caller \
    CHANGED=caller \
    "$RUN_BOTTOM" -- bash -c 'printf "%s\n" "$DISPLAY" "$WAYLAND_DISPLAY" "$GAMESCOPE_WAYLAND_DISPLAY" "${REMOVED-unset}" "$CHANGED" "$1"' _ arg >"$client_env"
[[ "$(<"$client_env")" == $':2\ngamescope-secondary\ngamescope-secondary\nunset\nnew\narg' ]]

# Without the bottom gamescope a client must not fall through to an inherited display.
if env XDG_RUNTIME_DIR="$tmp/empty-runtime" DISPLAY=outer-x11 \
    "$RUN_BOTTOM" -- true 2>"$tmp/no-bottom"; then
    echo 'client started without the bottom gamescope' >&2
    exit 1
fi
grep -q 'bottom screen is not running' "$tmp/no-bottom"

if env XDG_RUNTIME_DIR="$tmp/runtime" "$RUN_BOTTOM" -- 2>"$tmp/no-command"; then
    echo 'empty command unexpectedly succeeded' >&2
    exit 1
fi
grep -q 'no command specified' "$tmp/no-command"

# The main gamescope's socket gets its fixed name from the Steam launcher.
mkdir -p "$tmp/steam/steamrtarm64"
printf '#!/usr/bin/env bash\n' >"$tmp/steam/steamrtarm64/steam"
chmod +x "$tmp/steam/steamrtarm64/steam"
env \
    STEAM_ROOT="$tmp/steam" \
    XDG_RUNTIME_DIR="$tmp/runtime" \
    GAMESCOPE_WAYLAND_DISPLAY=gamescope-0 \
    "$LAUNCH_STEAM"
[[ "$(readlink "$tmp/runtime/gamescope-primary")" == gamescope-0 ]]
# Steam started from a client of another gamescope must not repoint it.
env \
    STEAM_ROOT="$tmp/steam" \
    XDG_RUNTIME_DIR="$tmp/runtime" \
    GAMESCOPE_WAYLAND_DISPLAY=gamescope-secondary \
    "$LAUNCH_STEAM" --desktop
[[ "$(readlink "$tmp/runtime/gamescope-primary")" == gamescope-0 ]]

grep -Fxq 'Wants=armada-bottom-gamescope.service' "$SESSION_DROPIN"
grep -Fxq 'ExecStopPost=/usr/bin/rm -f %t/gamescope-primary' "$SESSION_DROPIN"
grep -Fxq 'PartOf=gamescope-session-plus@steam.service' "$GAMESCOPE_SERVICE"
grep -Fxq 'ExecCondition=/usr/libexec/armada/bottom-gamescope --supported' "$GAMESCOPE_SERVICE"
grep -Fxq 'ExecStart=/usr/libexec/armada/bottom-gamescope' "$GAMESCOPE_SERVICE"
grep -Fxq 'ExecStopPost=/usr/bin/rm -f %t/armada-bottom-env %t/gamescope-secondary' "$GAMESCOPE_SERVICE"
grep -Fxq 'Restart=always' "$GAMESCOPE_SERVICE"

# A gamescope restart must take Plasma with it; KWin outlives a dead X display.
grep -Fxq 'PartOf=armada-bottom-gamescope.service' "$BOTTOM_SERVICE"
grep -Fxq 'WantedBy=gamescope-session-plus@steam.service' "$BOTTOM_SERVICE"
grep -Fxq 'After=armada-bottom-gamescope.service' "$BOTTOM_SERVICE"
grep -Fxq 'ExecStart=/usr/bin/armada-run-bottom -- /usr/libexec/armada/armada-plasma-session bottom' "$BOTTOM_SERVICE"
grep -Fxq 'Restart=always' "$BOTTOM_SERVICE"
grep -Fxq 'ExecStartPre=/usr/bin/touch %t/armada-bottom-screen-active' "$BOTTOM_SERVICE"
grep -Fxq 'ExecStopPost=/usr/bin/rm -f %t/armada-bottom-screen-active' "$BOTTOM_SERVICE"
grep -Fq '/run/user/1000/armada-bottom-screen-active' "$WAYDROID_INPUT_SETUP"
grep -Fq 'each_gamescope gamescopectl drm_sleep_internal_screen 1' "$FAKE_SUSPEND"
grep -Fq 'each_gamescope gamescopectl drm_sleep_internal_screen 0' "$FAKE_SUSPEND"
grep -Fq 'timeout 5 /usr/bin/armada-rgb sleep' "$FAKE_SUSPEND"
grep -Fq 'timeout 5 /usr/bin/armada-rgb wake' "$FAKE_SUSPEND"
grep -A1 '^    display_off ' "$FAKE_SUSPEND" | grep -Fxq '    lights_off'
grep -B1 -Fx '    display_on' "$FAKE_SUSPEND" | grep -Fxq '    lights_on'

bash -n "$RUN_BOTTOM" "$BOTTOM_GAMESCOPE" "$BOTTOM_READY" "$FAKE_SUSPEND"
printf 'bottom-screen session tests passed\n'
