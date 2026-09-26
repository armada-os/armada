#!/usr/bin/env bash
# Local wrapper: run a package's build.sh inside the builder container, the way
# CI runs it as a Containerfile stage. Same contract, documented there.
#
# Usage: ./build-local.sh <package>
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
PKGROOT="${PWD}"
pkg="${1:?usage: build-local.sh <package>}"
[ -d "${pkg}" ] || { echo "unknown package: ${pkg}" >&2; exit 1; }

source ./toolchain.env

platform=linux/aarch64
image="${BUILDER_IMAGE}"
run_args=()
# Optional second phase, run after build.sh with its own podman flags.
phase2=()
phase2_args=()

case "${pkg}" in
    # These cross-build to arm64 from an x86_64 host.
    mesa-android|guestos-android)
        platform=linux/amd64 ;;
    mesa-x86)
        platform=linux/amd64
        source "${pkg}/BASE.env"
        image="${GUEST_BUILDER_IMAGE}" ;;
    # ccache opt-in: CI persists it in a cache mount, dev builds keep it
    # package-local.
    kernel|mesa)
        ccache_dir="${CCACHE_DIR:-${PKGROOT}/${pkg}/.ccache}"
        mkdir -p "${ccache_dir}"
        run_args+=(--volume "${ccache_dir}:/ccache:Z" --env CCACHE_DIR=/ccache) ;;
    # generate.sh gets no network, so its dependencies are baked into the image.
    steam-bootstrap)
        image=localhost/armada-steam-bootstrap-builder
        podman build --build-arg "BUILDER_IMAGE=${BUILDER_IMAGE}" \
            -t "${image}" -f "${pkg}/Containerfile" "${pkg}/"
        phase2=(bash generate.sh)
        phase2_args=(--network none) ;;
esac

if [ "${platform}" = linux/aarch64 ] && [ "$(uname -m)" != aarch64 ]; then
    echo "warning: ${pkg} builds aarch64 under emulation on $(uname -m); expect it to be very slow" >&2
fi

rm -rf "${pkg}/out"
mkdir -p "${pkg}/out"

run() {
    podman run --rm \
        --volume "${PKGROOT}:/src:Z" \
        --volume "${PKGROOT}/${pkg}:/work:Z" \
        --workdir /work \
        --platform "${platform}" \
        "${run_args[@]}" \
        "$@"
}

run "${image}" ./build.sh
if [ "${#phase2[@]}" -gt 0 ]; then
    run "${phase2_args[@]}" "${image}" "${phase2[@]}"
fi

echo "built: ${PKGROOT}/${pkg}/out"
