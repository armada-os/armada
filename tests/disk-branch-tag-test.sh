#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "${WORK}"' EXIT

python3 - "${ROOT}/.github/workflows/build-disk.yml" "${WORK}/resolve-tag" <<'PY'
from pathlib import Path
import sys
import textwrap

workflow = Path(sys.argv[1]).read_text()
step = workflow.split('      - name: Resolve container tag\n', 1)[1]
script = textwrap.dedent(step.split('        run: |\n', 1)[1].split('\n\n      - name:', 1)[0])
Path(sys.argv[2]).write_text(script)
PY

run_case() {
    local ref=$1 selected=$2 expected=$3
    local output=${WORK}/output
    rm -f "${output}"
    BUILD_REF="${ref}" SELECTED_TAG="${selected}" GITHUB_OUTPUT="${output}" \
        bash "${WORK}/resolve-tag"
    grep -qx "tag=${expected}" "${output}"
}

run_case refs/heads/main '' testing
run_case refs/heads/staging '' staging
run_case refs/heads/feature-disk '' feature-disk
run_case refs/heads/main custom-build custom-build

for ref in refs/heads/beta refs/tags/v1.0 refs/pull/1/merge; do
    if BUILD_REF="${ref}" SELECTED_TAG='' GITHUB_OUTPUT="${WORK}/output" \
        bash "${WORK}/resolve-tag" >/dev/null 2>&1; then
        echo "Unexpectedly accepted ${ref}" >&2
        exit 1
    fi
done

if BUILD_REF=refs/heads/main SELECTED_TAG='bad/tag' GITHUB_OUTPUT="${WORK}/output" \
    bash "${WORK}/resolve-tag" >/dev/null 2>&1; then
    echo "Unexpectedly accepted an invalid explicit tag" >&2
    exit 1
fi

echo "Disk branch tag tests passed"
