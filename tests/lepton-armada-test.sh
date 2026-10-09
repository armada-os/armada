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
printf '%s\n' \
    '--- a/liblepton/mounting.sh' \
    '+++ b/liblepton/mounting.sh' \
    '@@ -1,2 +1,3 @@' \
    ' first' \
    '+added' \
    ' second' \
    >"$tool_dir/launcher.patch"

# Steam's Lepton install.
lepton="$tmp/home/.local/share/Steam/steamapps/common/Lepton"
mkdir -p "$lepton/liblepton" "$lepton/images/rootfs" "$lepton/images/rootfs_overlay/system" "$lepton/sysbake"
printf 'first\nsecond\n' >"$lepton/liblepton/mounting.sh"
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
[[ "$(<"$derived/liblepton/mounting.sh")" == $'first\nadded\nsecond' ]]
[[ "$(<"$lepton/liblepton/mounting.sh")" == $'first\nsecond' ]]
[[ "$(<"$derived/images/rootfs_overlay/system/valve")" == 'valve file' ]]
[[ "$(<"$derived/images/rootfs_overlay/vendor/lib64/display.so")" == 'patched library' ]]
[[ ! -e "$lepton/images/rootfs_overlay/vendor" ]]
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
[[ "$(<"$derived/liblepton/mounting.sh")" == $'first\nadded\nsecond' ]]

# A launcher the patch no longer fits must not run unpatched.
printf 'changed upstream\n' >"$lepton/liblepton/mounting.sh"
printf 'v3\n' >"$lepton/version.txt"
rm -f "$tmp/result"
if run run >/dev/null 2>"$tmp/no-apply"; then
    echo 'unpatched launcher was run' >&2
    exit 1
fi
grep -q 'patches do not apply to Lepton v3' "$tmp/no-apply"
[[ ! -e "$tmp/result" ]]

rm -rf "$lepton"
if run run 2>"$tmp/no-lepton"; then
    echo 'ran without Lepton installed' >&2
    exit 1
fi
grep -q 'is not installed' "$tmp/no-lepton"

bash -n "$WRAPPER"
printf 'lepton-armada tests passed\n'
