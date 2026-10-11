#!/usr/bin/bash
set -euxo pipefail

here="$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")"
id="${1:?usage: prepare-variant.sh <id> <dest>}"
dest="${2:?usage: prepare-variant.sh <id> <dest>}"
variant="${here}/variants/${id}"

[[ "${id}" =~ ^[a-z0-9][a-z0-9-]*$ && "${id}" != stable ]] || { echo "ERROR: bad variant id: ${id}" >&2; exit 1; }

source "${here}/BASE.env"
base_url="${SOURCE_URL:-}"
base_sha256="${SOURCE_SHA256:-}"
unset SOURCE_URL SOURCE_SHA256 BASE_PATCHES LABEL
unset BASED_ON
source "${variant}/VARIANT.env"
if [ -n "${BASED_ON:-}" ]; then
    source "${here}/variants/${BASED_ON}/VARIANT.env"
    source "${variant}/VARIANT.env"
fi
[ -n "${LABEL:-}" ] || { echo "ERROR: ${id}: VARIANT.env needs LABEL" >&2; exit 1; }
if [ -n "${SOURCE_URL:-}${SOURCE_SHA256:-}" ]; then
    [ -n "${SOURCE_URL:-}" ] && [ -n "${SOURCE_SHA256:-}" ] || { echo "ERROR: ${id}: SOURCE_URL and SOURCE_SHA256 go together" >&2; exit 1; }
else
    SOURCE_URL="${base_url}"
    SOURCE_SHA256="${base_sha256}"
fi
[ -n "${SOURCE_URL}" ] || { echo "ERROR: ${id}: no Mesa source" >&2; exit 1; }

if [ -z "${BASE_PATCHES+x}" ]; then
    patches=("${here}"/patches/*.patch)
else
    patches=()
    for name in ${BASE_PATCHES}; do
        patches+=("${here}/patches/${name}")
    done
fi
shopt -s nullglob
patches+=("${variant}"/patches/*.patch)
shopt -u nullglob

tarball="$(mktemp)"
trap 'rm -f "${tarball}"' EXIT
curl --fail --location --retry 3 "${SOURCE_URL}" --output "${tarball}"
printf '%s  %s\n' "${SOURCE_SHA256}" "${tarball}" | sha256sum --check --status --strict

rm -rf "${dest}"
mkdir -p "${dest}"
tar xf "${tarball}" -C "${dest}" --strip-components=1
for patch in "${patches[@]}"; do
    patch -d "${dest}" -p1 --forward --no-backup-if-mismatch <"${patch}"
done

"${here}/turnip-build-id.sh" source - "${SOURCE_SHA256}" "${patches[@]}" >"${dest}/source-id"
printf '{"label": "%s", "version": "%s"}\n' "${LABEL}" "$(tr -d '[:space:]' <"${dest}/VERSION")" >"${dest}/variant.json"
