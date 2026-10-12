#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCH="$ROOT/system_files/usr/libexec/armada/armada-mod-launch"
tmp="$(mktemp -d "${TMPDIR:-/var/tmp}/armada-mod-test.XXXXXX")"

cleanup() {
    chmod -R u+rwx "$tmp" 2>/dev/null || true
    rm -rf -- "$tmp"
}
trap cleanup EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

export ARMADA_MODS_HOME="$tmp/home"
export XDG_CACHE_HOME="$tmp/cache"
export XDG_RUNTIME_DIR="$tmp/runtime"
game="$tmp/library/steamapps/common/Game"
mkdir -p "$game/Data" "$XDG_RUNTIME_DIR"
echo original >"$game/Data/core.txt"

launch() {
    SteamAppId=9 STEAM_COMPAT_INSTALL_PATH="$game" "$LAUNCH" "$@" 2>"$tmp/stderr"
}

# env and launch_args need no mount; a failing hook leaves only its mod out
mods="$ARMADA_MODS_HOME/mods"
mkdir -p "$mods/fix" "$mods/broken/hooks"
echo '{"id":"fix","version":"1","name":"Fix","steam_appids":[9],"env":{"FIX_DATA":"{data}"},"launch_args":["-windowed"]}' >"$mods/fix/mod.json"
echo '{"id":"broken","version":"1","name":"Broken","steam_appids":[9],"hooks":{"before_launch":"hooks/fail"},"env":{"BROKEN":"1"}}' >"$mods/broken/mod.json"
printf '#!/bin/sh\nexit 3\n' >"$mods/broken/hooks/fail"
chmod +x "$mods/broken/hooks/fail"
out="$(launch sh -c 'echo "$1 ${FIX_DATA##*/} ${BROKEN-unset}"; echo saved >"$0/save.dat"' "$game")"
[[ "$out" == "-windowed fix unset" ]] || fail "env or launch_args not applied: $out"
[[ -f "$game/save.dat" ]] || fail "game write lost without an overlay"
grep -q "broken left out" "$tmp/stderr" || fail "failing hook not reported"
[[ ! -e "$tmp/library/steamapps/common/.armada-mods-9" ]] || fail "mounted without files to overlay"
rm -rf "$mods/fix" "$mods/broken" "$game/save.dat"

probe="$tmp/probe"
mkdir -p "$probe/lower" "$probe/upper" "$probe/work"
if ! bwrap --dev-bind / / --overlay-src "$probe/lower" --overlay "$probe/upper" "$probe/work" "$probe/upper" true 2>/dev/null; then
    echo "armada-mod-test: no unprivileged overlay here, mount cases skipped"
    exit 0
fi

# files appear in the game folder; the game's writes reach the install and the mod's do not
mkdir -p "$mods/files/overlay/Data" "$mods/files/overlay/Loader" "$mods/files/hooks"
echo '{"id":"files","version":"1","name":"Files","steam_appids":[9],"hooks":{"before_launch":"hooks/patch"}}' >"$mods/files/mod.json"
echo added >"$mods/files/overlay/Data/added.txt"
echo loader >"$mods/files/overlay/Loader/loader.cfg"
printf '%s\n' '#!/bin/sh' 'mkdir -p "$ARMADA_MOD_DATA_DIR/overlay/Data"' \
    'sed s/original/patched/ "$ARMADA_MOD_GAME_DIR/Data/core.txt" >"$ARMADA_MOD_DATA_DIR/overlay/Data/core.txt"' >"$mods/files/hooks/patch"
chmod +x "$mods/files/hooks/patch"
out="$(launch sh -c 'cd "$0"; cat Data/core.txt Data/added.txt; echo saved >save.dat; echo log >Loader/log.txt; rm Data/added.txt 2>/dev/null || echo refused' "$game")"
[[ "$out" == $'patched\nadded\nrefused' ]] || fail "overlay view wrong: $out"
[[ "$(cat "$game/Data/core.txt")" == original ]] || fail "game file changed in the install"
[[ -f "$game/save.dat" ]] || fail "game write did not reach the install"
[[ ! -e "$game/Data/added.txt" && ! -e "$game/Loader" ]] || fail "mod files reached the install"
[[ -f "$mods/files/overlay/Loader/log.txt" ]] || fail "write into a mod folder not kept in the mod"

for _ in $(seq 1 50); do
    [[ -e "$tmp/library/steamapps/common/.armada-mods-9" ]] || break
    sleep 0.2
done
[[ ! -e "$tmp/library/steamapps/common/.armada-mods-9" ]] || fail "overlay work directory left behind"
if command -v getfattr >/dev/null; then
    [[ -z "$(getfattr -R -d -m user.overlay "$game" 2>/dev/null)" ]] || fail "overlay attributes left on the game folder"
fi

echo "armada-mod-test: ok"
