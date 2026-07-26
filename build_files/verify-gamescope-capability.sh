#!/bin/bash
set -euo pipefail

readonly gamescope_binary="${1:-/usr/bin/gamescope}"
readonly required_option='--expose-client-sampleable-formats'

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[[ -f "$gamescope_binary" && -x "$gamescope_binary" ]] ||
    fail "packaged Gamescope binary is missing or not executable: $gamescope_binary"

if ! package_owner=$(rpm -qf --queryformat '%{NAME}\n' "$gamescope_binary"); then
    fail "cannot identify the package owning $gamescope_binary"
fi
[[ "$package_owner" == gamescope ]] ||
    fail "unexpected package owns $gamescope_binary: $package_owner"

# Do not execute Gamescope while constructing the image. Nested rootless image
# builds can prohibit execution even when the installed AArch64 binary is valid.
# The production wrapper performs the runtime --help probe on the target device,
# and release validation can verify this exact binary by SHA-256.
LC_ALL=C grep -aFq -- "$required_option" "$gamescope_binary" ||
    fail "packaged Gamescope lacks $required_option"
