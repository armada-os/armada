#!/usr/bin/env bash
# Prints a package's content hash, used as the tag for its published artifacts.
# The prepare job and the image build both derive it here, so they resolve the
# same image. Hashing Containerfile whole means editing it rebuilds everything.
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
pkg="${1:?usage: package-hash.sh <package>}"
[ -d "${pkg}" ] || { echo "unknown package: ${pkg}" >&2; exit 1; }

paths=("${pkg}" toolchain.env Containerfile scrub-scratch.sh)
case "${pkg}" in
    mesa-x86|mesa-android|guestos-android) paths+=(mesa) ;;
esac

if grep -q '/src/TERRA.env' "${pkg}/build.sh" 2>/dev/null; then
    paths+=(TERRA.env)
fi

# Exclusions for local builds
prune=(-not -path "*/out/*" -not -path "*/.ccache/*"
       -not -path "*/work/*" -not -path "*/target/*")

list_files() {
    for p in "${paths[@]}"; do
        if [ -d "$p" ]; then
            find "$p" -type f "${prune[@]}" -print0
        else
            printf '%s\0' "$p"
        fi
    done | LC_ALL=C sort -z
}

list_links() {
    for p in "${paths[@]}"; do
        if [ -d "$p" ]; then
            find "$p" -type l "${prune[@]}" -printf '%p -> %l\0'
        fi
    done | LC_ALL=C sort -z
}

# Modes and symlink targets too, so a permission or link fix rebuilds.
{
    list_files | xargs -0 sha256sum
    list_files | xargs -0 stat -c '%a %n'
    list_links
} | sha256sum | cut -c1-32
