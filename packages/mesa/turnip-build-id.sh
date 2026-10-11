#!/usr/bin/bash
# Turnip's shader cache identity, from the build's inputs rather than its binary, so
# rebuilding unchanged inputs keeps the caches on users' devices valid.
#
# Usage: turnip-build-id.sh <arch> <toolchain> <source id> [patch...]
set -euxo pipefail

arch="$1" toolchain="$2" source_id="$3"
shift 3
id=$({
    printf '%s\n' "${arch}" "${toolchain}" "${source_id}"
    [ "$#" -eq 0 ] || sha256sum "$@" | cut -d' ' -f1
} | sha256sum | cut -c1-40)
[[ "${id}" =~ ^[0-9a-f]{40}$ ]]
printf '%s\n' "${id}"
