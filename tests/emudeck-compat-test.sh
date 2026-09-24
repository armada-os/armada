#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_PACKAGES="$ROOT/build_files/10-base-packages.sh"
CLEANUP="$ROOT/build_files/70-cleanup.sh"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

# These concrete Fedora packages satisfy EmuDeck's Fedora dependency names:
# newt, python, lsb_release, fuse-libs, and SDL2.
for package in newt python-unversioned-command lsb_release fuse-libs sdl2-compat; do
    grep -Eq "^[[:space:]]+${package}( [\\\\]|; do)$" "$BASE_PACKAGES" ||
        fail "$package is not installed in the base image"
    grep -Eq "^[[:space:]]+${package}( [\\\\]|; do)$" "$CLEANUP" ||
        fail "$package is not protected by the post-cleanup package check"
done

grep -Fqx 'ln -sf libz.so.1 /usr/lib64/libz.so' "$BASE_PACKAGES" ||
    fail 'the AppImage libz.so compatibility link is missing'

printf 'EmuDeck compatibility test passed\n'
