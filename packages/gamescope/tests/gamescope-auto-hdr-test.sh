#!/usr/bin/env bash
set -euo pipefail

if (( $# < 1 )); then
    echo "Usage: $0 <patched-gamescope-source> [Catch2 arguments]" >&2
    exit 2
fi

gamescope_dir=$(realpath -- "$1")
shift
tests_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_dir=$(mktemp -d)
trap 'rm -rf -- "$build_dir"' EXIT

# Use Gamescope's test dependencies and the installed AutoHDR library.
dependencies=$("${PKG_CONFIG:-pkg-config}" --cflags --libs catch2-with-main glm armada-autohdr)
read -r -a dependency_flags <<< "$dependencies"
read -r -a compiler_flags <<< "${CXXFLAGS:--O2}"

"${CXX:-c++}" -std=c++20 "${compiler_flags[@]}" \
    -I "$gamescope_dir/src" "$tests_dir/gamescope-auto-hdr-test.cpp" \
    "${dependency_flags[@]}" -o "$build_dir/auto-hdr-test"
"$build_dir/auto-hdr-test" "$@"
