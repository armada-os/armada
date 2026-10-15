#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
# ccache at /ccache: a cache mount in the stage, a bind mount locally.
set -euxo pipefail

source ./BASE.env
source /src/toolchain.env

SRPM_NVR="$SRPM"
SRPM_VER="${SRPM_NVR#mesa-}"
SRPM_VER="${SRPM_VER%%-*}"
MESA_VER="${VERSION:-${SRPM_VER}}"
SOURCE_URL="${SOURCE_URL:-}"
SOURCE_SHA256="${SOURCE_SHA256:-}"
SOURCE_TARBALL="${SOURCE_URL##*/}"

# The pinned Rawhide SRPM supplies Fedora's packaging; SOURCE_URL can replace its
# Mesa source for prereleases. Packages target the fedora:44 runtime ABI.
DIST=".fc44.armada"
SUBPKGS="mesa-filesystem mesa-libgbm mesa-dri-drivers mesa-vulkan-drivers mesa-libGL mesa-libEGL"

export CCACHE_DIR="${CCACHE_DIR:-/ccache}"
export CCACHE_MAXSIZE=2G
mkdir -p "${CCACHE_DIR}"

rm -rf out
mkdir -p out

export HOME=/tmp
dnf -y install rpm-build rpmdevtools koji 'dnf-command(builddep)' ccache curl
export PATH=/usr/lib64/ccache:$PATH CC=gcc CXX=g++
ccache -z
rpmdev-setuptree
cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF
cd /tmp
koji download-build --arch=src "${SRPM_NVR}"
rpm -i "${SRPM_NVR}.src.rpm"
SPEC=$HOME/rpmbuild/SPECS/mesa.spec

sed -i "s/^Version:.*/Version:        ${MESA_VER}/" "$SPEC"
sed -i 's/^Release:.*%autorelease.*/Release:        1%{?dist}/' "$SPEC"
sed -i '/^%autochangelog/d' "$SPEC"

if [ -n "${SOURCE_URL}" ]; then
    [ -n "${SOURCE_SHA256}" ] || { echo 'ERROR: SOURCE_SHA256 is required with SOURCE_URL'; exit 1; }
    curl --fail --location --retry 3 "${SOURCE_URL}" \
        --output "$HOME/rpmbuild/SOURCES/${SOURCE_TARBALL}"
    printf '%s  %s\n' "${SOURCE_SHA256}" \
        "$HOME/rpmbuild/SOURCES/${SOURCE_TARBALL}" | \
        sha256sum --check --status --strict
fi

LAST=$(grep -nE '^(Patch|Source)[0-9]*:' "$SPEC" | tail -1 | cut -d: -f1)
[ -n "$LAST" ] || { echo 'ERROR: no Source/Patch line to anchor the patch on'; exit 1; }
n=9000
for patch in /work/patches/*.patch; do
    n=$((n + 1))
    cp "$patch" $HOME/rpmbuild/SOURCES/
    sed -i "${LAST}a Patch${n}:       ${patch##*/}" "$SPEC"
    LAST=$((LAST + 1))
done
sed -i "/^%build$/i %global build_cflags %{build_cflags} ${ARMADA_MARCH}" "$SPEC"
sed -i "/^%build$/i %global build_cxxflags %{build_cxxflags} ${ARMADA_MARCH}" "$SPEC"

# two-pass: %generate_buildrequires emits a nosrc; install its BRs then build for real
dnf -y builddep "$SPEC"

# The SRPM adds the spec's own patches and options. No compiler version: it changes unprompted.
TOOLCHAIN_ID="${BUILDER_IMAGE} ${ARMADA_MARCH}"
stable_source=$(/work/turnip-build-id.sh source "${SRPM_NVR}" "${SOURCE_SHA256}" /work/patches/*.patch)
stable_id=$(/work/turnip-build-id.sh aarch64 "${TOOLCHAIN_ID}" "${stable_source}")
sed -i "/^%meson \\\\$/a \\  -Dtu-build-id=${stable_id} \\\\" "$SPEC"
grep -q -- "-Dtu-build-id=${stable_id}" "$SPEC"
rpmbuild -bb --define "dist ${DIST}" "$SPEC" || true
NOSRC=$(find "$HOME/rpmbuild/SRPMS" -maxdepth 1 -type f \
    -name "mesa-${MESA_VER}-*${DIST}.buildreqs.nosrc.rpm" -print -quit)
[ -n "$NOSRC" ] && dnf -y builddep "$NOSRC"
rpmbuild -bb --define "dist ${DIST}" "$SPEC"
ccache -s

for p in ${SUBPKGS}; do
    cp $HOME/rpmbuild/RPMS/*/${p}-${MESA_VER}-*${DIST}.*.rpm /work/out/
done

TURNIP_DIR=/usr/share/armada/turnip
build_ids="${stable_id}"
turnip_meson=(--buildtype release --prefix /usr
    -Dgallium-drivers= -Dvulkan-drivers=freedreno -Dfreedreno-kmds=msm
    -Dplatforms=x11,wayland -Dglx=disabled -Degl=disabled -Dgbm=disabled
    -Dopengl=false -Dllvm=disabled)
for variant in /work/variants/*/; do
    id=$(basename "$variant")
    src=/tmp/turnip-$id
    /work/prepare-variant.sh "$id" "$src"
    source_id=$(cat "$src/source-id")
    variant_id=$(/work/turnip-build-id.sh aarch64 "${TOOLCHAIN_ID} -O2 ${turnip_meson[*]}" "${source_id}")
    build_ids+=$'\n'"${variant_id}"
    CFLAGS="-O2 ${ARMADA_MARCH}" CXXFLAGS="-O2 ${ARMADA_MARCH}" \
        meson setup "$src/build" "$src" "${turnip_meson[@]}" -Dtu-build-id="${variant_id}"
    ninja -C "$src/build"
    out=/work/out/turnip/$id
    install -D -m 0755 "$src/build/src/freedreno/vulkan/libvulkan_freedreno.so" "$out/aarch64/libvulkan_freedreno.so"
    sed -E "s|\"library_path\": *\"[^\"]*\"|\"library_path\": \"${TURNIP_DIR}/${id}/aarch64/libvulkan_freedreno.so\"|" \
        "$src/build/src/freedreno/vulkan/freedreno_icd.aarch64.json" >"$out/icd.aarch64.json"
    grep -q "\"${TURNIP_DIR}/${id}/aarch64/libvulkan_freedreno.so\"" "$out/icd.aarch64.json"
    install -m 0644 "$src/variant.json" "$out/variant.json"
done
mkdir -p /work/out/turnip/stable
printf '{"label": "Stable", "version": "%s"}\n' "${MESA_VER}" >/work/out/turnip/stable/variant.json

# Two drivers sharing an identity would share a shader cache.
[ -z "$(sort <<<"${build_ids}" | uniq -d)" ]
