#!/bin/bash
# Manual build on an aarch64 host with podman. Sources, objects and ccache go
# under SCRATCH (default ./.scratch); budget about 60 GB. The tool lands in
# ./out/<PROTON_TOOL_NAME>.
set -euo pipefail
cd "$(dirname "$0")"
source ./BASE.env

[[ "$(uname -m)" == aarch64 ]] || { echo "needs an aarch64 host" >&2; exit 1; }

SCRATCH="${SCRATCH:-${PWD}/.scratch}"
mkdir -p "${SCRATCH}/tmp" "${SCRATCH}/ccache"

podman run --rm \
    --volume "${PWD}:/work:Z" \
    --volume "${SCRATCH}/tmp:/tmp:Z" \
    --volume "${SCRATCH}/ccache:/ccache:Z" \
    --workdir /work \
    "${PROTON_SDK_IMAGE}" ./build.sh
