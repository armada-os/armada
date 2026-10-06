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
cp /work/patches/0001-disable-turnip-sparse-sync.patch $HOME/rpmbuild/SOURCES/
sed -i "${LAST}a Patch9001:       0001-disable-turnip-sparse-sync.patch" "$SPEC"
cp /work/patches/0002-add-a830-chip-id.patch $HOME/rpmbuild/SOURCES/
sed -i "/^Patch9001:/a Patch9002:       0002-add-a830-chip-id.patch" "$SPEC"
cp /work/patches/0003-ir3-disable-bindless-ubo-const-lowering.patch $HOME/rpmbuild/SOURCES/
sed -i "/^Patch9002:/a Patch9003:       0003-ir3-disable-bindless-ubo-const-lowering.patch" "$SPEC"
sed -i "/^%build$/i %global build_cflags %{build_cflags} ${ARMADA_MARCH}" "$SPEC"
sed -i "/^%build$/i %global build_cxxflags %{build_cxxflags} ${ARMADA_MARCH}" "$SPEC"

# two-pass: %generate_buildrequires emits a nosrc; install its BRs then build for real
dnf -y builddep "$SPEC"
rpmbuild -bb --define "dist ${DIST}" "$SPEC" || true
NOSRC=$(find "$HOME/rpmbuild/SRPMS" -maxdepth 1 -type f \
    -name "mesa-${MESA_VER}-*${DIST}.buildreqs.nosrc.rpm" -print -quit)
[ -n "$NOSRC" ] && dnf -y builddep "$NOSRC"
rpmbuild -bb --define "dist ${DIST}" "$SPEC"
ccache -s

for p in ${SUBPKGS}; do
    cp $HOME/rpmbuild/RPMS/*/${p}-${MESA_VER}-*${DIST}.*.rpm /work/out/
done

# Calibration-only Turnip for armada-autotune-report. Not in icd.d, so games never load it.
AUTOTUNE_DIR=/usr/lib64/armada/autotune
mkdir -p /tmp/autotune
tar xf "$HOME/rpmbuild/SOURCES/${SOURCE_TARBALL:-mesa-${MESA_VER}.tar.xz}" -C /tmp/autotune --strip-components=1
cd /tmp/autotune
for patch in /work/patches/*.patch /work/patches/autotune/*.patch; do
    patch -p1 <"$patch"
done
CFLAGS="-O2 ${ARMADA_MARCH}" CXXFLAGS="-O2 ${ARMADA_MARCH}" \
    meson setup build --buildtype release --prefix /usr --libdir "${AUTOTUNE_DIR#/usr/}" \
    -Dgallium-drivers= -Dvulkan-drivers=freedreno -Dfreedreno-kmds=msm \
    -Dplatforms= -Dglx=disabled -Degl=disabled -Dgbm=disabled \
    -Dopengl=false -Dllvm=disabled
ninja -C build
mkdir -p /work/out/autotune
install -m 0755 build/src/freedreno/vulkan/libvulkan_freedreno.so /work/out/autotune/
install -m 0644 build/src/freedreno/vulkan/freedreno_icd.aarch64.json /work/out/autotune/freedreno_icd.json
grep -q "\"${AUTOTUNE_DIR}/libvulkan_freedreno.so\"" /work/out/autotune/freedreno_icd.json
