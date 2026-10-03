#!/usr/bin/env bash
#
# splash-i18n-test.sh - manual runner for the armada-splash i18n behavior test.
#
# By default (no --run) this prints SKIP and exits 0, so the general test sweep
# never compiles anything. Pass --run to build and execute the C behavior test.
# This mirrors the manual font runner convention.
#
# Usage:
#     splash-i18n-test.sh [--run]
#
# With --run it compiles the test (packages/armada-splash/tests/i18n-test.c)
# together with the real production module
# (packages/armada-splash/src/splash-i18n.c) using:
#
#     cc -std=c11 -Wall -Wextra -Werror
#
# The binary and every fixture live inside the output directory:
#
#     ${SPLASH_I18N_TEST_OUT:-<root>/packages/armada-splash/tests/build}

set -u

script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(cd -- "$script_dir/.." && pwd)

SRC="$ROOT/packages/armada-splash/src"
TEST="$ROOT/packages/armada-splash/tests/i18n-test.c"
header="$SRC/splash-i18n.h"
impl="$SRC/splash-i18n.c"
out_dir="${SPLASH_I18N_TEST_OUT:-$ROOT/packages/armada-splash/tests/build}"
binary="$out_dir/i18n-test"

red() {
    printf '\033[31m%s\033[0m\n' "$1"
}

run=0
for arg in "$@"; do
    case "$arg" in
        --run)
            run=1
            ;;
        -h|--help)
            printf 'usage: %s [--run]\n' "$(basename -- "$0")"
            exit 0
            ;;
        *)
            red "FAIL: unknown argument: $arg"
            exit 2
            ;;
    esac
done

if [ "$run" -ne 1 ]; then
    printf 'SKIP: splash i18n behavior tests (pass --run to build and execute)\n'
    exit 0
fi

# Fail loudly (red) when the production module is not present yet, rather than
# silently skipping: --run means the caller expects a real result.
missing=
[ -f "$header" ] || missing="$missing $header"
[ -f "$impl" ] || missing="$missing $impl"
if [ -n "$missing" ]; then
    red "MISSING PRODUCTION: splash-i18n source not found:$missing"
    printf '  the i18n behavior test needs %s\n' "$header"
    printf '  and %s (added by the next C change)\n' "$impl"
    exit 1
fi

if [ ! -f "$TEST" ]; then
    red "FAIL: test source not found: $TEST"
    exit 1
fi

if ! command -v cc >/dev/null 2>&1; then
    red "FAIL: C compiler 'cc' not found on PATH"
    exit 1
fi

mkdir -p -- "$out_dir"
rc=$?
if [ "$rc" -ne 0 ]; then
    red "FAIL: cannot create output directory: $out_dir"
    exit "$rc"
fi

cc -std=c11 -Wall -Wextra -Werror -I"$SRC" -o "$binary" "$TEST" "$impl"
rc=$?
if [ "$rc" -ne 0 ]; then
    red "FAIL: compilation failed (status $rc)"
    exit "$rc"
fi

"$binary" "$out_dir"
rc=$?
if [ "$rc" -ne 0 ]; then
    red "FAIL: i18n behavior test failed (status $rc)"
    exit "$rc"
fi

printf 'PASS: splash i18n behavior tests\n'
exit 0
