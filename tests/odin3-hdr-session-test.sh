#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="$ROOT/system_files/usr/share/gamescope-session-plus/sessions.d/steam"

if grep -Fq 'ENABLE_GAMESCOPE_HDR=' "$SESSION"; then
    printf 'Odin 3 session still force-enables HDR output\n' >&2
    exit 1
fi

for assignment in \
    'GAMESCOPE_INTERNAL_DEVICE_ID="$ARMADA_DEVICE_ID"' \
    'GAMESCOPE_EXPOSE_CLIENT_SAMPLEABLE_FORMATS=1' \
    'GAMESCOPE_HDR_ITM_TARGET_NITS=650'; do
    if ! grep -Fq "$assignment" "$SESSION"; then
        printf 'missing Odin 3 HDR session assignment: %s\n' "$assignment" >&2
        exit 1
    fi
done

printf 'Odin 3 HDR session policy test passed\n'
