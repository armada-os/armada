#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINERFILE="$ROOT/Containerfile"
JUSTFILE="$ROOT/Justfile"
WORKFLOW="$ROOT/.github/workflows/build.yml"

grep -Fxq 'ARG ARMADA_SOURCE_DATE_EPOCH' "$CONTAINERFILE"
grep -Fq '[[ "${ARMADA_SOURCE_DATE_EPOCH}" =~ ^[1-9][0-9]*$ ]]' "$CONTAINERFILE"
grep -Fq -- '--source-date-epoch "${ARMADA_SOURCE_DATE_EPOCH}"' "$CONTAINERFILE"
if grep -Fq -- '--source-date-epoch 0' "$CONTAINERFILE"; then
    echo 'Chunkah must not create epoch-zero deployment metadata' >&2
    exit 1
fi

grep -Fq 'ARMADA_SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"' "$JUSTFILE"
grep -Fq '"ARMADA_SOURCE_DATE_EPOCH=${ARMADA_SOURCE_DATE_EPOCH}"' "$JUSTFILE"
grep -Fq 'source_date_epoch=$(git log -1 --format=%ct)' "$WORKFLOW"
grep -Fq 'ARMADA_SOURCE_DATE_EPOCH=${{ steps.version.outputs.source_date_epoch }}' "$WORKFLOW"

printf 'build timestamp test passed\n'
