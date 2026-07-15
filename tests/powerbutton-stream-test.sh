#!/usr/bin/env bash

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'powerbutton_cleanup 2>/dev/null || true; rm -rf -- "$tmp"' EXIT
fail() { printf 'powerbutton stream test failed at line %s: %s\n' "$1" "$2" >&2; exit 1; }
mkfifo "$tmp/block"

export ARMADA_INPUT_LIB="$ROOT/system_files/usr/lib/armada/input-lib"
export ARMADA_POWERBUTTON_GUARD_LIB="$ROOT/system_files/usr/lib/armada/powerbutton-guard"
source "$ROOT/system_files/usr/libexec/armada/powerbuttond"

# The first fake evtest fills its stdout pipe with historical backlog. The
# replacement emits a distinct line and then both processes block without a
# helper child, allowing powerbutton_close_stream to reap them deterministically.
evtest() {
    exec 9<>"$tmp/block"
    if ( set -o noclobber; : >"$tmp/first-started" ) 2>/dev/null; then
        printf 'old-first\nold-backlog-1\nold-backlog-2\n'
    else
        printf 'new-first\n'
    fi
    IFS= read -r -u 9 _
}

pdev=/dev/input/fake
powerbutton_open_stream
old_pid=$power_event_pid
read_power_line -1
[[ $line == old-first ]] || fail "$LINENO" 'did not read original stream'

powerbutton_reopen_stream
[[ $power_event_pid != "$old_pid" ]] || fail "$LINENO" 'stream PID did not change'
if kill -0 "$old_pid" 2>/dev/null; then
    fail "$LINENO" 'old evtest process survived replacement'
fi
read_power_line -1
[[ $line == new-first ]] || fail "$LINENO" "old backlog crossed replacement: $line"

printf 'powerbutton stream replacement tests passed\n'
