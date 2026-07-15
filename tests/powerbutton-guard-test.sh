#!/usr/bin/env bash

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
fail() { printf 'powerbutton guard test failed at line %s: %s\n' "$1" "$2" >&2; exit 1; }

export ARMADA_RESUME_MARKER="$tmp/last-resume"
export ARMADA_RESUME_GUARD_MS=1500
export ARMADA_RESUME_GUARD_HARD_MS=5000
export ARMADA_UPTIME_FILE="$tmp/uptime"
export ARMADA_BOOT_ID_FILE="$tmp/boot-id"
boot=aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa
printf '%s\n' "$boot" >"$ARMADA_BOOT_ID_FILE"
printf '2147484.123 0.00\n' >"$ARMADA_UPTIME_FILE"
source "$ROOT/system_files/usr/lib/armada/powerbutton-guard"

[[ $(armada_guard_now_ms) == 2147484123 ]] || fail "$LINENO" 'monotonic conversion'

test_now=1000
key_state=released
mock_owner=0
mock_mode=644

stat() {
    if [[ $1 == -c && $2 == '%u %a' && $3 == "$ARMADA_RESUME_MARKER" ]]; then
        printf '%s %s\n' "$mock_owner" "$mock_mode"
        return 0
    fi
    command stat "$@"
}
armada_guard_now_ms() { printf '%s\n' "$test_now"; }
armada_power_key_pressed() {
    case $key_state in
        pressed) return 0 ;;
        released) return 1 ;;
        unknown) return 2 ;;
    esac
}
write_marker() {
    local generation=$1 phase=$2 phase_ms=$3 marker_boot=${4:-$boot}
    printf 'v1 %s %s %s %s 2026-07-14T00:00:00-04:00\n' \
        "$generation" "$marker_boot" "$phase" "$phase_ms" >"$ARMADA_RESUME_MARKER"
}

first=11111111-1111-4111-8111-111111111111
second=22222222-2222-4222-8222-222222222222
third=33333333-3333-4333-8333-333333333333
fourth=44444444-4444-4444-8444-444444444444
fifth=55555555-5555-4555-8555-555555555555
sixth=66666666-6666-4666-8666-666666666666
seventh=77777777-7777-4777-8777-777777777777

# Init caches a marker that predates this daemon but never arms from it. A
# post-hook signal can explicitly force that same marker for a current resume.
write_marker "$first" resumed 900
armada_resume_guard_init
[[ $armada_resume_identity == "${first}:resumed" ]] || fail "$LINENO" 'init identity'
(( armada_resume_guard_active == 0 )) || fail "$LINENO" 'stale startup armed'
armada_resume_guard_refresh 1 || fail "$LINENO" 'forced post signal did not arm'
(( armada_resume_guard_until_ms == 2500 )) || fail "$LINENO" 'forced soft deadline'
(( armada_resume_guard_hard_until_ms == 6000 )) || fail "$LINENO" 'forced hard deadline'

# A normally discovered resumed phase uses absolute deadlines anchored to the
# post marker, so observing it near five seconds cannot extend suppression.
armada_resume_guard_reset
test_now=5900
write_marker "$second" resumed 1000
armada_resume_guard_refresh || fail "$LINENO" 'fresh absolute marker rejected'
(( armada_resume_guard_until_ms == 2500 )) || fail "$LINENO" 'soft deadline extended'
(( armada_resume_guard_hard_until_ms == 6000 )) || fail "$LINENO" 'hard deadline extended'
test_now=6000
if armada_resume_guard_swallow 'Event: code 116 (KEY_POWER), value 1'; then
    fail "$LINENO" 'event swallowed at absolute hard deadline'
fi

# The exact soft boundary still drains a queued wake sequence on a marker seen
# promptly after post.
test_now=3000
write_marker "$third" resumed 3000
armada_resume_guard_refresh || fail "$LINENO" 'prompt resumed phase rejected'
test_now=4500
armada_resume_guard_swallow 'Event: code 116 (KEY_POWER), value 1' \
    || fail "$LINENO" 'soft-boundary press escaped'
armada_resume_guard_swallow 'Event: code 116 (KEY_POWER), value 2' \
    || fail "$LINENO" 'soft-boundary repeat escaped'
armada_resume_guard_swallow 'Event: code 116 (KEY_POWER), value 0' \
    || fail "$LINENO" 'soft-boundary release escaped'
if armada_resume_guard_tick /dev/input/fake; then
    fail "$LINENO" 'released key remained guarded after soft boundary'
fi

# A held wake key remains guarded until release is proven.
test_now=5000
write_marker "$fourth" resumed 5000
armada_resume_guard_refresh || fail "$LINENO" 'held-key phase rejected'
armada_resume_guard_swallow 'Event: code 116 (KEY_POWER), value 1' \
    || fail "$LINENO" 'held press escaped'
key_state=pressed
test_now=6600
armada_resume_guard_tick /dev/input/fake || fail "$LINENO" 'held key guard ended early'
(( armada_resume_guard_active == 1 )) || fail "$LINENO" 'held guard inactive'
armada_resume_guard_swallow 'Event: code 116 (KEY_POWER), value 0' \
    || fail "$LINENO" 'held release escaped'
key_state=released
if armada_resume_guard_tick /dev/input/fake; then
    fail "$LINENO" 'guard survived proven held-key release'
fi

# Unknown key state cannot extend the hard deadline.
test_now=8000
write_marker "$fifth" resumed 8000
armada_resume_guard_refresh || fail "$LINENO" 'unknown-key phase rejected'
key_state=unknown
test_now=9600
armada_resume_guard_tick /dev/input/fake || fail "$LINENO" 'unknown state ended before hard cap'
test_now=13000
if armada_resume_guard_swallow 'Event: code 116 (KEY_POWER), value 1'; then
    fail "$LINENO" 'unknown state outlived hard cap'
fi

# A new prepared phase remains pending without deadlines across an hour-long
# suspend; its first event on the replacement fd starts the bounded window.
test_now=14000
write_marker "$sixth" prepared 14000
armada_resume_guard_refresh || fail "$LINENO" 'new prepared phase rejected'
(( armada_resume_guard_until_ms == 0 )) || fail "$LINENO" 'prepared timer started early'
test_now=3614000
armada_resume_guard_tick /dev/input/fake || fail "$LINENO" 'prepared phase expired in suspend'
armada_resume_guard_swallow 'Event: code 116 (KEY_POWER), value 1' \
    || fail "$LINENO" 'hour-late wake press escaped'
(( armada_resume_guard_until_ms == 3615500 )) || fail "$LINENO" 'prepared soft deadline'
armada_resume_guard_swallow 'Event: code 116 (KEY_POWER), value 0' \
    || fail "$LINENO" 'hour-late wake release escaped'

# A stale resumed transition for the same active prepared generation remains
# relevant even after a slow parallel post hook.
write_marker "$sixth" resumed 14000
armada_resume_guard_refresh || fail "$LINENO" 'prepared continuation was lost'
[[ $armada_resume_identity == "${sixth}:resumed" ]] || fail "$LINENO" 'resumed identity'
(( armada_resume_guard_until_ms == 3615500 )) || fail "$LINENO" 'continuation deadline'

# A prepared marker already present at daemon restart is cached, not armed.
armada_resume_guard_reset
write_marker "$seventh" prepared 1000
armada_resume_guard_init
[[ $armada_resume_identity == "${seventh}:prepared" ]] || fail "$LINENO" 'prepared cache identity'
(( armada_resume_guard_active == 0 )) || fail "$LINENO" 'abandoned prepared marker armed'

# Invalid ownership, mode, boot ID, extra records/bytes, and symlinks fail closed.
write_marker "$first" resumed 3614000
mock_owner=501
if armada_resume_guard_refresh; then fail "$LINENO" 'non-root marker accepted'; fi
mock_owner=0
mock_mode=600
if armada_resume_guard_refresh; then fail "$LINENO" 'wrong-mode marker accepted'; fi
mock_mode=644
write_marker "$first" resumed 3614000 bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb
if armada_resume_guard_refresh; then fail "$LINENO" 'wrong-boot marker accepted'; fi
write_marker "$first" resumed 3614000
printf ' trailing\n' >>"$ARMADA_RESUME_MARKER"
if armada_resume_guard_refresh; then fail "$LINENO" 'trailing record accepted'; fi
write_marker "$first" resumed 3614000
printf 'unterminated' >>"$ARMADA_RESUME_MARKER"
if armada_resume_guard_refresh; then fail "$LINENO" 'unterminated bytes accepted'; fi
printf 'target\n' >"$tmp/target"
rm -f "$ARMADA_RESUME_MARKER"
ln -s "$tmp/target" "$ARMADA_RESUME_MARKER"
if armada_resume_guard_refresh; then fail "$LINENO" 'symlink marker accepted'; fi

printf 'powerbutton resume-guard tests passed\n'
