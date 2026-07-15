#!/usr/bin/env bash

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

while IFS= read -r file; do
    case $(head -n 1 "$file") in
        *bash*) bash -n "$file" ;;
    esac
done < <(find "$ROOT/system_files" "$ROOT/tests" -type f -print)

"$ROOT/tests/powerbutton-guard-test.sh"
"$ROOT/tests/resume-guard-hook-test.sh"
"$ROOT/tests/powerbuttond-replay-test.sh"
"$ROOT/tests/powerbutton-stream-test.sh"
"$ROOT/tests/powerbutton-signal-test.sh"

printf 'wake-guard test suite passed\n'
