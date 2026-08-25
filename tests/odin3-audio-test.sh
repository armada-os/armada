#!/usr/bin/env bash
set -euo pipefail

readonly root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
complete=1

PYTHONDONTWRITEBYTECODE=1 \
    python3 "$root/tests/odin3-audio-policy-test.py" -v
PYTHONDONTWRITEBYTECODE=1 \
    python3 "$root/tests/odin3-audio-hotplug-test.py" -v
PYTHONDONTWRITEBYTECODE=1 \
    python3 "$root/tests/odin3-audio-steam-sync-test.py" -v
bash "$root/tests/odin3-audio-resume-test.sh"

if command -v spa-json-dump >/dev/null 2>&1; then
    while IFS= read -r fragment; do
        spa-json-dump "$fragment" >/dev/null
    done < <(
        find "$root/system_files/usr/share/armada/audio/odin3" \
            -type f -name '*.conf' -print
    )
else
    printf '%s\n' 'SKIP: spa-json-dump is unavailable; Python structural checks ran'
    complete=0
fi

if command -v luac >/dev/null 2>&1; then
    luac -p \
        "$root/system_files/usr/share/wireplumber/scripts/odin3-speaker-route-unity.lua"
else
    printf '%s\n' 'SKIP: luac is unavailable; Python route-hook checks ran'
    complete=0
fi

case "$(uname -s)" in
    Linux) ;;
    *)
        printf '%s\n' 'SKIP: POSIX symlink integration requires Linux'
        complete=0
        ;;
esac

if (( complete )); then
    printf '%s\n' 'Odin 3 audio production tests passed'
else
    printf '%s\n' \
        'Odin 3 audio portable checks passed; run the skipped checks on Linux before release'
fi
