#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_BOTTOM="$ROOT/system_files/usr/bin/armada-run-bottom"
BOTTOM_SESSION="$ROOT/system_files/usr/libexec/armada/bottom-screen-session"
BOTTOM_SERVICE="$ROOT/system_files/usr/lib/systemd/user/armada-bottom-screen.service"
WAYDROID_INPUT_PATH="$ROOT/system_files/usr/lib/systemd/system/armada-waydroid-input.path"
WAYDROID_INPUT_SETUP="$ROOT/system_files/usr/libexec/armada/waydroid-input-setup"
FAKE_SUSPEND="$ROOT/system_files/usr/libexec/armada/fake-suspend"
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
    "$RUN_BOTTOM" -- "$BOTTOM_SESSION"

mapfile -d '' -t actual <"$args_file"
expected=(
    --backend drm
    --drm-lease-client "$lease_socket"
    --expose-wayland
    --force-windows-fullscreen
    --xwayland-count 1
    --default-touch-mode 4
    --force-orientation right
    -- "$BOTTOM_SESSION"
)
[[ "${#actual[@]}" == "${#expected[@]}" ]]
for i in "${!expected[@]}"; do
    [[ "${actual[$i]}" == "${expected[$i]}" ]]
done
[[ "$(<"$env_file")" == $'unset\nunset\nunset' ]]

dbus_run_session="$tmp/dbus-run-session"
inner_args="$tmp/inner-args"
inner_env="$tmp/inner-env"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    '[[ "$(readlink "$XDG_CONFIG_HOME/plasmashellrc")" == plasmashellrc.mobile ]] || exit 1' \
    '[[ -f "$XDG_CONFIG_HOME/plasmashellrc.mobile" ]] || exit 1' \
    'printf '\''%s\n'\'' "${XDG_CURRENT_DESKTOP-unset}" "${XDG_CONFIG_DIRS-unset}" "${QT_QPA_PLATFORMTHEME-unset}" "${QT_QUICK_CONTROLS_STYLE-unset}" "${QT_QUICK_CONTROLS_MOBILE-unset}" "${PLASMA_INTEGRATION_USE_PORTAL-unset}" "${PLASMA_PLATFORM-unset}" "${DISABLE_GAMESCOPE_WSI-unset}" "${GAMESCOPE_WAYLAND_DISPLAY-unset}" "${GAMESCOPE_LIMITER_FILE-unset}" >"$INNER_ENV"' \
    'printf '\''%s\0'\'' "$@" >"$INNER_ARGS"' \
    >"$dbus_run_session"
chmod +x "$dbus_run_session"
config_dir="$tmp/config"
mkdir -p "$config_dir"
printf 'saved desktop settings\n' >"$config_dir/plasmashellrc.desktop"
printf 'saved mobile settings\n' >"$config_dir/plasmashellrc.mobile"
ln -s plasmashellrc.desktop "$config_dir/plasmashellrc"
run_bottom_session() {
env \
    DISPLAY=gamescope-1 \
    HOME=/test/home \
    XDG_CONFIG_HOME="$config_dir" \
    XDG_CONFIG_DIRS=/test/config \
    DISABLE_GAMESCOPE_WSI=0 \
    GAMESCOPE_WAYLAND_DISPLAY=gamescope-1 \
    GAMESCOPE_LIMITER_FILE=/test/gamescope-limiter \
    ARMADA_DBUS_RUN_SESSION="$dbus_run_session" \
    ARMADA_KWIN_WAYLAND=/test/kwin_wayland \
    INNER_ARGS="$inner_args" \
    INNER_ENV="$inner_env" \
    "$BOTTOM_SESSION"
}
run_bottom_session
mapfile -d '' -t actual <"$inner_args"
expected=(
    /test/kwin_wayland
    --x11-display gamescope-1
    --fullscreen
    --no-lockscreen
    --exit-with-session '/usr/bin/plasmashell -p org.kde.plasma.mobileshell'
)
[[ "${#actual[@]}" == "${#expected[@]}" ]]
for i in "${!expected[@]}"; do
    [[ "${actual[$i]}" == "${expected[$i]}" ]]
done
[[ "$(<"$inner_env")" == $'KDE\n/test/home/.config/plasma-mobile:/etc/xdg:/test/config\nKDE\norg.kde.breeze\ntrue\n1\nphone:handset\n1\nunset\nunset' ]]
[[ ! " ${actual[*]} " =~ ' --width ' ]]
[[ ! " ${actual[*]} " =~ ' --height ' ]]

# Starting from Desktop or restarting Mobile must preserve both saved configs.
run_bottom_session
[[ "$(<"$config_dir/plasmashellrc.desktop")" == 'saved desktop settings' ]]
[[ "$(<"$config_dir/plasmashellrc.mobile")" == 'saved mobile settings' ]]

# Older installations may still have a regular active desktop config.
config_dir="$tmp/legacy-config"
mkdir -p "$config_dir"
printf 'legacy desktop settings\n' >"$config_dir/plasmashellrc"
run_bottom_session
[[ "$(<"$config_dir/plasmashellrc.desktop")" == 'legacy desktop settings' ]]
[[ ! -s "$config_dir/plasmashellrc.mobile" ]]

# A fresh profile must also be ready before Plasma launches.
config_dir="$tmp/fresh-config"
run_bottom_session
[[ ! -s "$config_dir/plasmashellrc.mobile" ]]

# Refuse ambiguous migration rather than discarding either desktop config.
config_dir="$tmp/conflicting-config"
mkdir -p "$config_dir"
printf 'active settings\n' >"$config_dir/plasmashellrc"
printf 'saved settings\n' >"$config_dir/plasmashellrc.desktop"
if run_bottom_session 2>"$tmp/config-conflict"; then
    echo 'conflicting desktop configs unexpectedly succeeded' >&2
    exit 1
fi
grep -q 'refusing to overwrite' "$tmp/config-conflict"
[[ "$(<"$config_dir/plasmashellrc")" == 'active settings' ]]
[[ "$(<"$config_dir/plasmashellrc.desktop")" == 'saved settings' ]]

if env -u DISPLAY "$BOTTOM_SESSION" 2>"$tmp/no-display"; then
    echo 'bottom session started without DISPLAY' >&2
    exit 1
fi
grep -q 'nested Gamescope did not provide an X11 display' "$tmp/no-display"

if "$RUN_BOTTOM" -- 2>"$tmp/no-command"; then
    echo 'empty command unexpectedly succeeded' >&2
    exit 1
fi
grep -q 'no command specified' "$tmp/no-command"

if env \
    TEST_SECONDARY_CONNECTOR= \
    ARMADA_DEVICE_ENV="$device_env" \
    ARMADA_GAMESCOPE="$gamescope" \
    GAMESCOPE_LEASE_SOCK="$lease_socket" \
    "$RUN_BOTTOM" -- true 2>"$tmp/no-display-device"; then
    echo 'missing secondary display unexpectedly succeeded' >&2
    exit 1
fi
grep -q 'device has no secondary display' "$tmp/no-display-device"

if env \
    ARMADA_DEVICE_ENV="$device_env" \
    ARMADA_GAMESCOPE="$gamescope" \
    GAMESCOPE_LEASE_SOCK="$tmp/missing.sock" \
    "$RUN_BOTTOM" -- true 2>"$tmp/no-socket"; then
    echo 'missing lease socket unexpectedly succeeded' >&2
    exit 1
fi
grep -q 'DRM lease socket is unavailable' "$tmp/no-socket"

grep -Fxq 'PartOf=gamescope-session-plus@steam.service' "$BOTTOM_SERVICE"
grep -Fxq 'WantedBy=gamescope-session-plus@steam.service' "$BOTTOM_SERVICE"
grep -Fxq 'Restart=always' "$BOTTOM_SERVICE"
grep -Fxq 'ExecStartPre=/usr/bin/touch %t/armada-bottom-screen-active' "$BOTTOM_SERVICE"
grep -Fxq 'ExecStopPost=/usr/bin/rm -f %t/armada-bottom-screen-active' "$BOTTOM_SERVICE"
grep -Fxq 'PathChanged=/run/user/1000/armada-bottom-screen-active' "$WAYDROID_INPUT_PATH"
grep -Fq 'each_gamescope gamescopectl drm_sleep_internal_screen 1' "$FAKE_SUSPEND"
grep -Fq 'each_gamescope gamescopectl drm_sleep_internal_screen 0' "$FAKE_SUSPEND"

bash -n "$RUN_BOTTOM" "$BOTTOM_SESSION" "$FAKE_SUSPEND" "$WAYDROID_INPUT_SETUP"
printf 'bottom-screen session tests passed\n'
