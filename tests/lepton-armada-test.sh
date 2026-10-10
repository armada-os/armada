#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WRAPPER="$ROOT/packages/lepton/files/lepton-armada"
tmp="$(mktemp -d)"
socket_pid=

cleanup() {
    [[ -z "$socket_pid" ]] || kill "$socket_pid" 2>/dev/null || true
    rm -rf -- "$tmp"
}
trap cleanup EXIT

# The tool directory as the image lays it out.
tool_dir="$tmp/tooldir"
mkdir -p "$tool_dir/overlay/vendor/lib64"
cp "$WRAPPER" "$tool_dir/lepton"
printf 'patched library\n' >"$tool_dir/overlay/vendor/lib64/display.so"
cp "$ROOT/packages/lepton/files/liblepton-armada.sh" "$tool_dir/liblepton.sh"

# Steam's Lepton install.
lepton="$tmp/home/.local/share/Steam/steamapps/common/Lepton"
mkdir -p "$lepton/liblepton" "$lepton/images/rootfs" "$lepton/sysbake" \
    "$lepton/images/rootfs_overlay/system/bin" "$lepton/images/rootfs_overlay/vendor/bin"
# Enough of Valve's library for the wrappers to load around.
printf '%s\n' \
    'ADB=adb' \
    'APP_DIR="${STEAM_COMPAT_INSTALL_PATH:-/foo}"' \
    'APP_PATH=' \
    'function println() { echo "$@"; }' \
    'function adb_port() { echo 5555; }' \
    'function get_apk_path() { [[ -n "$APP_PATH" ]] || APP_PATH="$(compgen -G "$APP_DIR/*.apk")"; printf %s "$APP_PATH"; }' \
    'function extract_app_hash() { echo one-apk; }' \
    'function clear_baked_app_data() { echo "cleared: $1"; }' \
    'function app_workdir() { echo "$WORK/app_workdir"; }' \
    'function data_workdir() { echo "$WORK/data_workdir"; }' \
    'function prepare_baked_data_for_removal() { echo "cleared everything"; }' \
    'function remove_prefix() { prepare_baked_data_for_removal; }' \
    >"$lepton/liblepton/liblepton.sh"
printf '%s\n' \
    '    APP_PATH=$(pm path "$package")' \
    '    APP_PATH="$(cmd_real package path ${APP_ID})"' \
    '    # the pm path after installing' \
    '    mv "${APP_PATH}"/* /data/steam_app/' \
    >"$lepton/images/rootfs_overlay/system/bin/cmd"
printf '%s\n' 'APP_PATH="$(pm path ${APP_ID} | sed "s/^package://g")";' \
    >"$lepton/images/rootfs_overlay/vendor/bin/fix_obb_symlink.sh"
printf 'v1\n' >"$lepton/version.txt"
printf 'v1\n' >"$lepton/images/version.txt"
printf 'valve file\n' >"$lepton/images/rootfs_overlay/system/valve"
: >"$lepton/sysbake.xattrs"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf '\''%s\n'\'' "$*" "${ARMADA_EXT_WAYLAND_DISPLAY-unset}" >"$RESULT"' \
    >"$lepton/lepton"
chmod +x "$lepton/lepton"

derived="$tmp/data/lepton-armada/tool"
run() {
    env HOME="$tmp/home" XDG_DATA_HOME="$tmp/data" XDG_RUNTIME_DIR="$tmp/run" RESULT="$tmp/result" \
        "$tool_dir/lepton" "$@"
}
mkdir -p "$tmp/run"

run run -- /some/app.apk
[[ "$(<"$tmp/result")" == $'run -- /some/app.apk\nunset' ]]
cmp -s "$derived/liblepton/liblepton.sh" "$tool_dir/liblepton.sh"
cmp -s "$derived/liblepton/liblepton.valve.sh" "$lepton/liblepton/liblepton.sh"
[[ "$(<"$derived/images/rootfs_overlay/system/bin/cmd")" == \
'    APP_PATH=$(pm path "$package" | grep "/base.apk$" | head -n 1)
    APP_PATH="$(cmd_real package path ${APP_ID} | grep "/base.apk$" | head -n 1)"
    # the pm path after installing
    find /data/steam_app -maxdepth 1 -type f -name '"'*.apk'"' -delete
    mv "${APP_PATH}"/* /data/steam_app/' ]]
[[ "$(<"$derived/images/rootfs_overlay/vendor/bin/fix_obb_symlink.sh")" == \
    'APP_PATH="$(pm path ${APP_ID} | grep "/base.apk$" | head -n 1 | sed "s/^package://g")";' ]]
! grep -q base.apk "$lepton/images/rootfs_overlay/system/bin/cmd"
[[ "$(<"$derived/images/rootfs_overlay/system/valve")" == 'valve file' ]]
[[ "$(<"$derived/images/rootfs_overlay/vendor/lib64/display.so")" == 'patched library' ]]
[[ ! -e "$lepton/images/rootfs_overlay/vendor/lib64" ]]
[[ "$(readlink "$derived/images/rootfs")" == "$lepton/images/rootfs" ]]
[[ "$(readlink "$derived/sysbake")" == "$lepton/sysbake" ]]

# An unchanged tool is reused, not rebuilt.
touch "$derived/marker"
run run
[[ -e "$derived/marker" ]]

# The secondary gamescope's socket is handed to the launcher when it exists.
python3 -c 'import socket,sys,time; s=socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); s.listen(); time.sleep(30)' \
    "$tmp/run/gamescope-secondary" &
socket_pid=$!
for _ in {1..50}; do
    [[ -S "$tmp/run/gamescope-secondary" ]] && break
    sleep 0.02
done
run run
[[ "$(<"$tmp/result")" == $'run\ngamescope-secondary' ]]

# A Lepton update, an image update or a changed tool directory rebuilds the copy.
printf 'v2\n' >"$lepton/version.txt"
run run
[[ ! -e "$derived/marker" ]]
touch "$derived/marker"
printf 'v2\n' >"$lepton/images/version.txt"
run run
[[ ! -e "$derived/marker" ]]
[[ "$(<"$derived/images/version.txt")" == v2 ]]
touch "$derived/marker"
printf 'newer library\n' >"$tool_dir/overlay/vendor/lib64/display.so"
run run
[[ ! -e "$derived/marker" ]]
[[ "$(<"$derived/images/rootfs_overlay/vendor/lib64/display.so")" == 'newer library' ]]

# Simultaneous cold launches all succeed and leave Steam's install alone.
rm -rf "$tmp/data"
pids=()
for n in 1 2 3 4; do
    env HOME="$tmp/home" XDG_DATA_HOME="$tmp/data" XDG_RUNTIME_DIR="$tmp/run" RESULT="$tmp/result-$n" \
        "$tool_dir/lepton" run &
    pids+=("$!")
done
for pid in "${pids[@]}"; do
    wait "$pid"
done
for n in 1 2 3 4; do
    [[ -s "$tmp/result-$n" ]]
done
[[ ! -e "$lepton/images/rootfs/rootfs" && ! -L "$lepton/images/rootfs/rootfs" ]]
cmp -s "$derived/liblepton/liblepton.sh" "$tool_dir/liblepton.sh"

# The wrappers, around the stand-in library and stand-in podman and adb.
mkdir -p "$tmp/bin" "$tmp/app" "$tmp/single"
for command in podman adb; do
    printf '%s\n' '#!/usr/bin/env bash' "echo \"$command \$*\"" >"$tmp/bin/$command"
    chmod +x "$tmp/bin/$command"
done
touch "$tmp/app/base.apk" "$tmp/app/config.apk" "$tmp/app/other.apk" "$tmp/single/game.apk"
printf 'base.apk\nconfig.apk\n' >"$tmp/app/.armada-apks"
hooks() {
    env PATH="$tmp/bin:$PATH" STEAM_COMPAT_INSTALL_PATH="$tmp/app" WORK="$tmp/baked" \
        bash -euo pipefail -c 'source "$1"; shift; "$@"' _ "$derived/liblepton/liblepton.sh" "$@"
}

# Wrappers for functions this library lacks are skipped, and it still loads.
hooks true 2>"$tmp/skipped"
grep -q 'has no setup_mounts' "$tmp/skipped"

# Whatever ports the launcher asks for, only adb is forwarded, on loopback.
[[ "$(hooks podman run --network=pasta:-I,eth0,-t,auto,-u,auto,--no-splice x 2>/dev/null)" == \
    'podman run --network=pasta:-I,eth0,--no-splice,-t,127.0.0.1/5555 x' ]]
[[ "$(hooks podman run --network=pasta:-I,eth0,-t,5555,-t,2337,--no-splice x 2>/dev/null)" == \
    'podman run --network=pasta:-I,eth0,--no-splice,-t,127.0.0.1/5555 x' ]]
[[ "$(hooks podman run --network=none x 2>/dev/null)" == 'podman run --network=none x' ]]
[[ "$(hooks podman ps -a 2>/dev/null)" == 'podman ps -a' ]]
# Network arguments it does not recognise stop the launch.
for arguments in 'x' '--network host x' '--network=pasta:-t,auto -p 5555:5555 x'; do
    # shellcheck disable=SC2086
    if hooks podman run $arguments >"$tmp/refused" 2>&1; then
        echo "container started with: $arguments" >&2
        exit 1
    fi
    grep -q 'refusing to start the container' "$tmp/refused"
done

# A split set installs together and is tracked as one; a lone APK goes through as it came.
[[ "$(hooks get_apk_path 2>/dev/null)" == "$tmp/app/base.apk" ]]
[[ "$(hooks armada_adb -s localhost:5555 install -g "$tmp/app/base.apk" 2>/dev/null)" == \
    "adb -s localhost:5555 install-multiple -g $tmp/app/base.apk $tmp/app/config.apk" ]]
[[ "$(hooks armada_adb -s localhost:5555 install -g "$tmp/single/game.apk" 2>/dev/null)" == \
    "adb -s localhost:5555 install -g $tmp/single/game.apk" ]]
[[ "$(hooks armada_adb kill-server 2>/dev/null)" == 'adb kill-server' ]]
[[ "$(hooks extract_app_hash 2>/dev/null)" != one-apk ]]
[[ "$(hooks extract_app_hash "$tmp/single/game.apk" 2>/dev/null)" == one-apk ]]
printf 'base.apk\nmissing.apk\n' >"$tmp/app/.armada-apks"
! hooks armada_adb install -g "$tmp/app/base.apk" >/dev/null 2>&1

# An early exit keeps the baked app; every other reason still clears it.
[[ "$(hooks clear_baked_app_data 'early exit' 2>/dev/null)" == 'Keeping baked app data after an early exit' ]]
[[ "$(hooks clear_baked_app_data 'app or depot changed' 2>/dev/null)" == 'cleared: app or depot changed' ]]

# Removing the launch prefix takes the overlay work directories and leaves the baked app.
mkdir -p "$tmp/baked/app_workdir" "$tmp/baked/data_workdir" "$tmp/baked/data_overlay"
[[ -z "$(hooks remove_prefix 2>/dev/null)" ]]
[[ ! -e "$tmp/baked/app_workdir" && ! -e "$tmp/baked/data_workdir" && -d "$tmp/baked/data_overlay" ]]
[[ "$(hooks prepare_baked_data_for_removal 2>/dev/null)" == 'cleared everything' ]]

rm -rf "$lepton"
if run run 2>"$tmp/no-lepton"; then
    echo 'ran without Lepton installed' >&2
    exit 1
fi
grep -q 'is not installed' "$tmp/no-lepton"

bash -n "$WRAPPER"
bash -n "$ROOT/packages/lepton/files/liblepton-armada.sh"
printf 'lepton-armada tests passed\n'
