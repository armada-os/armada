#!/usr/bin/env bash

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
fail() { printf 'resume hook test failed at line %s: %s\n' "$1" "$2" >&2; exit 1; }

export ARMADA_RESUME_RUNTIME_DIR="$tmp/run"
export ARMADA_RESUME_MARKER="$tmp/run/last-resume"
export ARMADA_RESUME_UUID_FILE="$tmp/uuid"
export ARMADA_RESUME_BOOT_ID_FILE="$tmp/boot-id"
export ARMADA_RESUME_UPTIME_FILE="$tmp/uptime"

first=11111111-1111-4111-8111-111111111111
second=22222222-2222-4222-8222-222222222222
boot=aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa
printf '%s\n' "$first" >"$ARMADA_RESUME_UUID_FILE"
printf '%s\n' "$boot" >"$ARMADA_RESUME_BOOT_ID_FILE"
printf '100.000 0.00\n' >"$ARMADA_RESUME_UPTIME_FILE"

source "$ROOT/system_files/usr/lib/systemd/system-sleep/50-armada-resume-guard"

# Keep the test unprivileged and portable across the macOS development host.
install() { mkdir -p "${!#}"; chmod 0755 "${!#}"; }
chown() { return 0; }
date() { printf '2026-07-14T00:00:00.000000000-04:00\n'; }
logger() { return 0; }
signal_count=0
signal_powerbuttond() { signal_count=$((signal_count + 1)); }
stat() {
    if [[ $1 == -c && $2 == '%u %a' && $3 == "$ARMADA_RESUME_MARKER" ]]; then
        printf '0 644\n'
        return 0
    fi
    command stat "$@"
}

armada_resume_guard_main pre hibernate
[[ ! -e $ARMADA_RESUME_MARKER ]] || fail "$LINENO" 'non-suspend operation wrote marker'

# The pre phase exists before kernel entry, then post atomically finalizes the
# same generation. This remains ordered even if user.slice freezing is disabled.
armada_resume_guard_main pre suspend
read -r version generation boot_id phase phase_ms timestamp <"$ARMADA_RESUME_MARKER"
[[ $version == v1 && $generation == "$first" && $boot_id == "$boot" ]] \
    || fail "$LINENO" 'invalid prepared identity'
[[ $phase == prepared && $phase_ms == 100000 ]] \
    || fail "$LINENO" 'invalid prepared phase'
(( signal_count == 0 )) || fail "$LINENO" 'pre phase signaled daemon'

printf '200.250 0.00\n' >"$ARMADA_RESUME_UPTIME_FILE"
armada_resume_guard_main post suspend
read -r version generation boot_id phase phase_ms timestamp <"$ARMADA_RESUME_MARKER"
[[ $version == v1 && $generation == "$first" && $boot_id == "$boot" ]] \
    || fail "$LINENO" 'post changed generation'
[[ $phase == resumed && $phase_ms == 200250 ]] \
    || fail "$LINENO" 'invalid resumed phase'
(( signal_count == 1 )) || fail "$LINENO" 'post did not signal daemon once'

# Invalid new pre data fails without replacing the last valid generation.
printf 'invalid\n' >"$ARMADA_RESUME_UUID_FILE"
if armada_resume_guard_main pre suspend; then
    printf 'invalid resume UUID unexpectedly published\n' >&2
    exit 1
fi
read -r _ generation _ phase _ <"$ARMADA_RESUME_MARKER"
[[ $generation == "$first" && $phase == resumed ]] \
    || fail "$LINENO" 'invalid pre replaced valid marker'

# Post remains a useful fallback if the pre hook was absent or failed.
rm -f "$ARMADA_RESUME_MARKER"
printf '%s\n' "$second" >"$ARMADA_RESUME_UUID_FILE"
printf '300.000 0.00\n' >"$ARMADA_RESUME_UPTIME_FILE"
armada_resume_guard_main post suspend
read -r _ generation _ phase phase_ms _ <"$ARMADA_RESUME_MARKER"
[[ $generation == "$second" && $phase == resumed && $phase_ms == 300000 ]] \
    || fail "$LINENO" 'post fallback marker invalid'
(( signal_count == 2 )) || fail "$LINENO" 'post fallback did not signal once'

# PID discovery accepts only the configured user's exact script invocation.
PROC_ROOT="$tmp/proc"
POWERBUTTON_PATH=/usr/libexec/armada/powerbuttond
mkdir -p "$PROC_ROOT/101/fd" "$PROC_ROOT/102" "$PROC_ROOT/103" \
    "$PROC_ROOT/104/fd" "$PROC_ROOT/105"
printf 'Name:\tbash\nPPid:\t1\nUid:\t501\t501\t501\t501\n' >"$PROC_ROOT/101/status"
printf '/bin/bash\0%s\0' "$POWERBUTTON_PATH" >"$PROC_ROOT/101/cmdline"
touch "$PROC_ROOT/101/fd/3"
printf 'Name:\tother\nPPid:\t1\nUid:\t501\t501\t501\t501\n' >"$PROC_ROOT/102/status"
printf '/bin/bash\0/usr/bin/not-powerbuttond\0' >"$PROC_ROOT/102/cmdline"
printf 'Name:\tbash\nPPid:\t1\nUid:\t502\t502\t502\t502\n' >"$PROC_ROOT/103/status"
printf '/bin/bash\0%s\0' "$POWERBUTTON_PATH" >"$PROC_ROOT/103/cmdline"
printf 'Name:\tbash\nPPid:\t101\nUid:\t501\t501\t501\t501\n' >"$PROC_ROOT/104/status"
printf '/bin/bash\0%s\0' "$POWERBUTTON_PATH" >"$PROC_ROOT/104/cmdline"
touch "$PROC_ROOT/104/fd/3"
printf 'Name:\tbash\nPPid:\t1\nUid:\t501\t501\t501\t501\n' >"$PROC_ROOT/105/status"
printf '/bin/bash\0%s\0' "$POWERBUTTON_PATH" >"$PROC_ROOT/105/cmdline"
id() { [[ ${1:-} == -u ]] && printf '501\n'; }
[[ $(powerbuttond_pids) == 101 ]] \
    || fail "$LINENO" 'exact ready powerbutton PID discovery'

printf 'resume-guard hook tests passed\n'
