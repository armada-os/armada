#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

source ./BASE.env
source /src/toolchain.env

SYSROOT_VERSION="${SYSROOT_VERSION:-fc44-armada}"
SYSROOT_TARBALL="fex-sysroot-${SYSROOT_VERSION}.tar.gz"

# The stage copies this in from pkg-fex-sysroot. Dev builds produce it here.
if [ ! -f "${SYSROOT_TARBALL}" ]; then
  SYSROOT_VERSION="${SYSROOT_VERSION}" ./build-sysroot.sh
fi

rm -rf out
mkdir -p out

dnf -y install --skip-unavailable rpm-build rpmdevtools \
    dnf-plugins-core spectool cmake clang lld llvm ninja-build \
    python3 python3-setuptools systemd-rpm-macros catch-devel \
    fmt-devel libepoxy-devel SDL2-devel xxhash-devel git-core \
    cmake-rpm-macros qt6-qtdeclarative-devel \
    alsa-lib-devel libdrm-devel libglvnd-devel libX11-devel \
    libXrandr-devel openssl-devel wayland-devel zlib-devel \
    clang-devel llvm-devel
rpmdev-setuptree
cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF
cp fex-emu.spec ~/rpmbuild/SPECS/
sed -i "/^%build$/i %global build_cflags %{build_cflags} ${ARMADA_MARCH}" ~/rpmbuild/SPECS/fex-emu.spec
sed -i "/^%build$/i %global build_cxxflags %{build_cxxflags} ${ARMADA_MARCH}" ~/rpmbuild/SPECS/fex-emu.spec
cp toolchain_x86_32.cmake toolchain_x86_64.cmake \
   build-fex-sysroot.sh "${SYSROOT_TARBALL}" Config.json \
   ~/rpmbuild/SOURCES/
spectool -g -R --define "commit ${COMMIT}" --define "date ${DATE}" --define "base_version ${BASE_VERSION}" ~/rpmbuild/SPECS/fex-emu.spec
rpmbuild -bb --define "commit ${COMMIT}" --define "date ${DATE}" --define "base_version ${BASE_VERSION}" ~/rpmbuild/SPECS/fex-emu.spec
cp ~/rpmbuild/RPMS/aarch64/*.rpm /work/out/
cp ~/rpmbuild/RPMS/noarch/*.rpm /work/out/ 2>/dev/null || true
