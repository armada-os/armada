#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

assert_contains() {
    local file="$1" needle="$2"
    if ! grep -Fq -- "$needle" "$file"; then
        printf 'missing %s in %s\n' "$needle" "$file" >&2
        exit 1
    fi
}

assert_contains "$ROOT/system_files/usr/lib/armada/devices/defaults.conf" 'ARMADA_VIRTUAL_KEYBOARD_CONNECTOR='
assert_contains "$ROOT/system_files/usr/lib/armada/devices/ayn-thor.conf" 'ARMADA_VIRTUAL_KEYBOARD_CONNECTOR=DSI-1'
assert_contains "$ROOT/system_files/usr/lib/armada/devices/ayn-thor-lite.conf" 'ARMADA_VIRTUAL_KEYBOARD_CONNECTOR=DSI-2'
assert_contains "$ROOT/system_files/usr/libexec/armada/device-env" 'ARMADA_VIRTUAL_KEYBOARD_CONNECTOR'
assert_contains "$ROOT/system_files/usr/libexec/armada/start-plasma" '/usr/libexec/armada/device-env'
assert_contains "$ROOT/system_files/usr/libexec/armada/start-plasma" 'set -a'
assert_contains "$ROOT/Containerfile" 'ARG KWIN_PKG=ghcr.io/armada-os/armada-packages/kwin'
assert_contains "$ROOT/Containerfile" 'FROM ${KWIN_PKG} AS kwin'
assert_contains "$ROOT/Containerfile" '--mount=type=bind,from=kwin,source=/rpms,target=/packages/kwin'
assert_contains "$ROOT/build_files/10-base-packages.sh" '/packages/kwin/kwin-[0-9]*.rpm'
assert_contains "$ROOT/build_files/10-base-packages.sh" '/packages/kwin/kwin-common-[0-9]*.rpm'
assert_contains "$ROOT/build_files/10-base-packages.sh" '/packages/kwin/kwin-libs-[0-9]*.rpm'

printf 'Thor virtual keyboard packaging test passed\n'
