#!/bin/bash
# Runs inside Valve's Proton SDK image; run.sh starts it. CONTAINER=1 is
# Makefile.in's in-container mode, so no nested container engine is needed.
set -euxo pipefail

source ./BASE.env

SRC=/tmp/proton
OBJ=/tmp/proton-build

rm -rf out "${SRC}" "${OBJ}"
mkdir -p out "${OBJ}"

git init -q "${SRC}"
git -C "${SRC}" remote add origin "${PROTON_REPO}"
git -C "${SRC}" fetch -q --depth=1 origin "refs/tags/${PROTON_TAG}:refs/tags/${PROTON_TAG}"
git -C "${SRC}" checkout -q "${PROTON_COMMIT}"
# Full commit history, no trees: pinned submodule commits need not be branch tips.
git -C "${SRC}" submodule update -q --init --recursive --filter=tree:0 --jobs 8

# The FEX build names itself with git describe, which needs its tags.
git -C "${SRC}/FEX" fetch -q --tags origin
if [[ -n "${FEX_COMMIT}" ]]; then
    git -C "${SRC}/FEX" checkout -q "${FEX_COMMIT}"
    git -C "${SRC}/FEX" submodule update -q --init --recursive --filter=tree:0
fi

# Not a Proton submodule; patches/proton/ adds its build rules.
git init -q "${SRC}/extras/dxvk-sarek"
git -C "${SRC}/extras/dxvk-sarek" remote add origin "${SAREK_REPO}"
git -C "${SRC}/extras/dxvk-sarek" fetch -q --tags --filter=tree:0 origin "${SAREK_COMMIT}"
git -C "${SRC}/extras/dxvk-sarek" checkout -q "${SAREK_COMMIT}"
git -C "${SRC}/extras/dxvk-sarek" submodule update -q --init --recursive --filter=tree:0

for dir in patches/*/; do
    [[ -d "${dir}" ]] || continue
    name="$(basename "${dir}")"
    tree="${SRC}"
    [[ "${name}" == proton ]] || tree="${SRC}/${name}"
    [[ -d "${tree}" ]] || { echo "no tree for patches/${name}" >&2; exit 1; }
    while read -r patch; do
        git -C "${tree}" apply --whitespace=nowarn "/work/${dir}${patch}"
    done < <(find "${dir}" -maxdepth 1 -name '*.patch' -printf '%f\n' | sort -V)
done

# What configure.sh would write, minus its container-engine probe.
cat >"${OBJ}/Makefile" <<EOF
SRCDIR := ${SRC}
BUILD_NAME := ${PROTON_DISPLAY_NAME}
INTERNAL_TOOL_NAME := ${PROTON_TOOL_NAME}
TARGET_ARCH := arm64
include \$(SRCDIR)/Makefile.in
EOF

export CCACHE_DIR=/ccache
export CARGO_HOME=/tmp/cargo
export SOURCE_DATE_EPOCH="$(git -C "${SRC}" log -1 --format=%ct)"

make -C "${OBJ}" CONTAINER=1 BASE_SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH}" -j"$(nproc)" all

DIST="/work/out/${PROTON_TOOL_NAME}"
mv "${OBJ}/dist" "${DIST}"

# Keep Valve's "<timestamp> <name>" shape; protonfixes parses it.
read -r stamp name <"${DIST}/version"
echo "${stamp} ${name}-armada" >"${DIST}/version"

# The arm64ec path is the point of this build; fail rather than ship without it.
for f in libarm64ecfex.dll libwow64fex.dll; do
    test -f "${DIST}/files/lib/wine/aarch64-windows/${f}"
done
test -f "${DIST}/files/lib/wine/aarch64-unix/libarm64ecfex.so"
test -f "${DIST}/files/lib/wine/dxvk-sarek/aarch64-windows/d3d11.dll"
test -f "${DIST}/files/lib/wine/dxvk-sarek/i386-windows/d3d11.dll"
