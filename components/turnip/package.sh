#!/bin/bash
# Turn built Turnip variants (packages/mesa/build.sh's out/turnip) into one remote payload:
# one <id>/ per variant, ICD manifests pointing at where armada-components installs them.
# usage: package.sh <out/turnip> <payload dir> <variant>...
set -euo pipefail

src=$1 dest=$2
shift 2
(( $# )) || { echo "usage: $0 <out/turnip> <payload dir> <variant>..." >&2; exit 2; }
installed=/var/lib/armada/components/turnip/current

rm -rf "$dest"
for id in "$@"; do
    [[ "$id" != stable ]] || { echo "stable always comes from the image" >&2; exit 1; }
    lib=$src/$id/aarch64/libvulkan_freedreno.so
    [[ -f "$lib" && -f "$src/$id/icd.aarch64.json" && -f "$src/$id/variant.json" ]] \
        || { echo "$src/$id is not a built variant" >&2; exit 1; }
    install -D -m 0755 "$lib" "$dest/$id/aarch64/libvulkan_freedreno.so"
    install -m 0644 "$src/$id/variant.json" "$dest/$id/variant.json"
    sed -E "s|\"library_path\": *\"[^\"]*\"|\"library_path\": \"$installed/$id/aarch64/libvulkan_freedreno.so\"|" \
        "$src/$id/icd.aarch64.json" >"$dest/$id/icd.aarch64.json"
    grep -q "\"$installed/$id/aarch64/libvulkan_freedreno.so\"" "$dest/$id/icd.aarch64.json"
done
