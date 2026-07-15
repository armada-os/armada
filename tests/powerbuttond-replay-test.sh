#!/usr/bin/env bash

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
fail() { printf 'powerbutton replay failed at line %s: %s\n' "$1" "$2" >&2; exit 1; }
export ARMADA_INPUT_LIB="$ROOT/system_files/usr/lib/armada/input-lib"
export ARMADA_POWERBUTTON_GUARD_LIB="$ROOT/system_files/usr/lib/armada/powerbutton-guard"
source "$ROOT/system_files/usr/libexec/armada/powerbuttond"

test_now=1000
guard_pending=0
armada_resume_guard_active=0
armada_resume_guard_seen_event=0
armada_resume_phase=
actions=()
logs=()
reopen_count=0
refresh_calls=0
force_calls=0
force_accept=1
pdev=/dev/input/fake

log() { logs+=("$*"); }
steam_uri() { actions+=("$1"); }
armada_lid_closed() { return 1; }
armada_guard_now_ms() { printf '%s\n' "$test_now"; }
armada_resume_guard_refresh() {
    local force=${1:-0}
    refresh_calls=$((refresh_calls + 1))
    if [[ $force == 1 ]]; then
        force_calls=$((force_calls + 1))
        (( force_accept == 1 )) || return 1
        armada_resume_guard_active=1
        armada_resume_phase=resumed
        return 0
    fi
    (( guard_pending == 1 )) || return 1
    guard_pending=0
    armada_resume_guard_active=1
    armada_resume_phase=resumed
}
armada_resume_guard_swallow() {
    (( armada_resume_guard_active == 1 )) || return 1
    [[ $1 == *"(KEY_POWER), value "[012]* ]]
}
armada_resume_guard_tick() { return 0; }
powerbutton_reopen_stream() { reopen_count=$((reopen_count + 1)); }

press='Event: code 116 (KEY_POWER), value 1'
repeat='Event: code 116 (KEY_POWER), value 2'
release='Event: code 116 (KEY_POWER), value 0'

# Normal short and long presses retain upstream behavior.
powerbutton_reset_state
powerbutton_handle_line "$press"
test_now=1999
powerbutton_handle_line "$release"
[[ ${actions[*]} == shortpowerpress ]] || fail "$LINENO" 'normal short press'

actions=()
test_now=3000
powerbutton_handle_line "$press"
test_now=4000
powerbutton_handle_timeout
powerbutton_handle_line "$release"
[[ ${actions[*]} == longpowerpress ]] || fail "$LINENO" 'normal long press'
[[ $state == idle ]] || fail "$LINENO" 'long release did not drain'

# Normal idle is blocking/event-driven; only active bounded guards poll.
armada_resume_guard_active=0
refresh_calls=0
powerbutton_handle_timeout
[[ $refresh_calls == 0 ]] || fail "$LINENO" 'idle timeout refreshed marker'
[[ $(powerbutton_next_timeout_ms) == -1 ]] || fail "$LINENO" 'idle did not block'
armada_resume_guard_active=1
armada_resume_phase=resumed
[[ $(powerbutton_next_timeout_ms) == "$GUARD_POLL_MS" ]] || fail "$LINENO" 'resumed guard did not poll'
armada_resume_phase=prepared
armada_resume_guard_seen_event=0
[[ $(powerbutton_next_timeout_ms) == -1 ]] || fail "$LINENO" 'unseen prepared phase polled'
armada_resume_guard_seen_event=1
[[ $(powerbutton_next_timeout_ms) == "$GUARD_POLL_MS" ]] || fail "$LINENO" 'seen prepared phase did not poll'
armada_resume_guard_active=0
armada_resume_phase=
armada_resume_guard_seen_event=0

# A phase discovered with an already-read key-down wins the race and replaces
# the old evtest stream before any remaining backlog can cross.
actions=()
guard_pending=1
reopen_count=0
test_now=5000
powerbutton_handle_line "$press"
[[ $reopen_count == 1 ]] || fail "$LINENO" 'wake phase did not replace stream'
[[ ${#actions[@]} == 0 ]] || fail "$LINENO" 'wake press emitted Steam action'
[[ $state == idle ]] || fail "$LINENO" 'wake press retained held state'

armada_resume_guard_active=0
powerbutton_handle_line "$press"
powerbutton_handle_line "$release"
[[ ${actions[*]} == shortpowerpress ]] || fail "$LINENO" 'fresh post-guard press failed'

# A new phase while held must cancel state before the long deadline.
actions=()
test_now=6000
powerbutton_handle_line "$press"
[[ $state == held ]] || fail "$LINENO" 'test press did not enter held state'
guard_pending=1
test_now=6100
powerbutton_handle_timeout
[[ $state == idle ]] || fail "$LINENO" 'new phase did not cancel held state'
[[ $reopen_count == 2 ]] || fail "$LINENO" 'held-state phase did not replace stream'
test_now=8000
armada_resume_guard_active=0
powerbutton_handle_timeout
[[ ${#actions[@]} == 0 ]] || fail "$LINENO" 'cancelled hold fired long action'

# The post-hook signal forces a blocked daemon to consume even an old resumed
# marker, and does so without any idle poll.
armada_resume_guard_active=0
resume_signal=1
powerbutton_handle_resume_signal
[[ $force_calls == 1 ]] || fail "$LINENO" 'post signal did not force refresh'
[[ $reopen_count == 3 ]] || fail "$LINENO" 'post signal did not replace stream'
(( resume_signal == 0 )) || fail "$LINENO" 'post signal flag not cleared'

# A spurious signal or invalid marker still replaces the descriptor the trap
# closed, so power-button handling cannot die from the recovery mechanism.
force_accept=0
resume_signal=1
powerbutton_handle_resume_signal
[[ $reopen_count == 4 ]] || fail "$LINENO" 'failed forced refresh left stream closed'

printf 'powerbutton replay tests passed\n'
