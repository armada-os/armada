#!/usr/bin/env bash

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
fail() { printf 'powerbutton signal test failed at line %s: %s\n' "$1" "$2" >&2; exit 1; }
mkfifo "$tmp/block"

export ARMADA_INPUT_LIB="$ROOT/system_files/usr/lib/armada/input-lib"
export ARMADA_POWERBUTTON_GUARD_LIB="$ROOT/system_files/usr/lib/armada/powerbutton-guard"
source "$ROOT/system_files/usr/libexec/armada/powerbuttond"

forced=0
powerbutton_refresh_guard() {
    [[ ${1:-0} == 1 ]] || return 1
    forced=$((forced + 1))
}
trap powerbutton_note_resume_signal USR1
exec 3<>"$tmp/block"

( sleep 0.1; kill -USR1 "$$" ) &
sender=$!
read_result=0
read_power_line -1 || read_result=$?
wait "$sender"
(( resume_signal == 1 )) || fail "$LINENO" 'USR1 did not set resume flag'
(( read_result != 0 )) || fail "$LINENO" 'USR1 did not interrupt blocking read'
powerbutton_handle_resume_signal
(( forced == 1 )) || fail "$LINENO" 'signal handler did not force refresh'
(( resume_signal == 0 )) || fail "$LINENO" 'signal handler did not clear flag'

printf 'powerbutton signal tests passed\n'
