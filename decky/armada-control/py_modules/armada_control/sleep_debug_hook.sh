#!/usr/bin/bash
set -uo pipefail

command=${ARMADA_SLEEP_DEBUG_COMMAND:-/usr/bin/armada-sleep-debug}
run_dir=${ARMADA_SLEEP_DEBUG_RUN_ROOT:-/run}/armada/sleep-debug
report_dir=${ARMADA_SLEEP_DEBUG_REPORT_DIR:-/var/home/armada/Documents/sleep-logs}
cycle=${2:-${INVOCATION_ID:-}}
[[ $cycle =~ ^[a-f0-9]{32}$ ]] || exit 0

case "${1:-}" in
    prepare)
        eval "$("${ARMADA_SLEEP_DEBUG_DEVICE_ENV:-/usr/libexec/armada/device-env}" 2>/dev/null)" || exit 0
        [[ ${ARMADA_SUSPEND_MODE:-fake} == s2idle ]] || exit 0
        timeout --kill-after=1s 8s "$command" begin "$cycle" --trace
        ;;
    collect)
        [[ -f $run_dir/$cycle/attempt.json ]] || exit 0
        timeout --kill-after=1s 8s "$command" finish "$cycle" || true
        timeout --kill-after=1s 3s "$command" stop-trace "$cycle" || true
        env_args=()
        while IFS= read -r name; do
            env_args+=("--setenv=$name=${!name}")
        done < <(compgen -e ARMADA_SLEEP_DEBUG_)
        [[ ! -v ARMADA_SESSION_USER ]] || env_args+=("--setenv=ARMADA_SESSION_USER=$ARMADA_SESSION_USER")
        exec "${ARMADA_SLEEP_DEBUG_SYSTEMD_RUN:-/usr/bin/systemd-run}" --quiet --no-block --collect \
            "${env_args[@]}" \
            /usr/bin/bash "$0" collect-report "$cycle"
        ;;
    collect-report)
        umask 077
        report=$run_dir/$cycle/report.txt
        "$command" report "$cycle" >"$report" 2>"$run_dir/$cycle/formatter.stderr" ||
            echo 'report_incomplete=collector failed; partial output retained' >>"$report"
        [[ -s $report ]] || exit 1
        owner=${ARMADA_SESSION_USER:-armada}
        parent=$(dirname -- "$report_dir")
        if [[ ! -d $parent ]]; then
            install -d -o "$owner" -g "$owner" -m 0755 -- "$parent" || exit 1
        fi
        mkdir -p -- "$report_dir" || exit 1
        chown "$owner:$owner" "$report_dir" || exit 1
        timestamp=$(date +%Y%m%d-%H%M%S)
        dest=$report_dir/armada-sleep-debug-auto-$timestamp-$cycle.txt
        install -o "$owner" -g "$owner" -m 0600 "$report" "$dest" || exit 1
        touch "$run_dir/$cycle/exported"
        mapfile -t old_reports < <(
            find "$report_dir" -maxdepth 1 -type f -name 'armada-sleep-debug-auto-*.txt' -printf '%f\n' |
                sort -r | tail -n +11
        )
        for old_report in "${old_reports[@]}"; do
            rm -f -- "$report_dir/$old_report"
        done
        ;;
    *) exit 2 ;;
esac
