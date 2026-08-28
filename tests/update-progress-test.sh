#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PROGRESS="$ROOT/system_files/usr/libexec/armada/update-progress"

actual="$({
    printf '%s\n' 'not json'
    printf '%s\n' \
        '{"type":"ProgressBytes","task":"pulling","bytesCached":3476762393,"bytes":8193,"bytesTotal":2704335789}' \
        '{"type":"ProgressBytes","task":"pulling","bytesCached":3476762393,"bytes":1352167895,"bytesTotal":2704335789}' \
        '{"type":"ProgressBytes","task":"pulling","bytesCached":3476762393,"bytes":2704335789,"bytesTotal":2704335789}' \
        '{"type":"ProgressBytes","task":"fetching","bytes":2704335789,"bytesTotal":2704335789}' \
        '{"type":"ProgressSteps","task":"importing","steps":0,"stepsTotal":1}' \
        '{"type":"ProgressSteps","task":"importing","steps":1,"stepsTotal":1}' \
        '{"type":"ProgressSteps","task":"staging","steps":0,"stepsTotal":3}' \
        '{"type":"ProgressSteps","task":"staging","steps":1,"stepsTotal":3}' \
        '{"type":"ProgressSteps","task":"staging","steps":2,"stepsTotal":3}' \
        '{"type":"ProgressSteps","task":"staging","steps":3,"stepsTotal":3}'
} | "$PROGRESS")"

expected=$'0%\n30%\n60%\n80%\n86%\n93%\n100%'
if [[ "$actual" != "$expected" ]]; then
    diff -u <(printf '%s\n' "$expected") <(printf '%s\n' "$actual")
    exit 1
fi

cached="$({
    printf '%s\n' \
        '{"type":"ProgressBytes","task":"pulling","bytes":0,"bytesTotal":0}' \
        '{"type":"ProgressSteps","task":"importing","steps":1,"stepsTotal":1}' \
        '{"type":"ProgressSteps","task":"staging","steps":3,"stepsTotal":3}'
} | "$PROGRESS")"

if [[ "$cached" != $'60%\n80%\n100%' ]]; then
    diff -u <(printf '%s\n' $'60%\n80%\n100%') <(printf '%s\n' "$cached")
    exit 1
fi

printf 'update progress test passed\n'
