#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/system_files/usr/lib/systemd/system-sleep/45-armada-rgb"
[[ -x "$HOOK" ]]
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT

rgb="$tmp/armada-rgb"
calls="$tmp/calls"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf '\''%s\n'\'' "$*" >>"$CALLS"' \
    'exit "${RGB_STATUS:-0}"' \
    >"$rgb"
chmod +x "$rgb"

run_hook() {
    rm -f -- "$calls"
    env ARMADA_RGB="$rgb" CALLS="$calls" bash "$HOOK" "$@" 2>"$tmp/hook.log"
}

run_hook pre suspend
[[ "$(<"$calls")" == sleep ]]

run_hook post suspend
[[ "$(<"$calls")" == wake ]]

run_hook pre hibernate
[[ ! -e "$calls" ]]
run_hook post hibernate
[[ ! -e "$calls" ]]

RGB_STATUS=1 run_hook pre suspend
[[ "$(<"$calls")" == sleep ]]
grep -q 'armada-rgb sleep failed' "$tmp/hook.log"
RGB_STATUS=1 run_hook post suspend
[[ "$(<"$calls")" == wake ]]
grep -q 'armada-rgb wake failed' "$tmp/hook.log"

bash -n "$HOOK"
printf 'rgb sleep hook test passed\n'
