#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

source ./BASE.env
source /src/toolchain.env

rm -rf out
mkdir -p out

export HOME=/tmp
dnf -y install rpm-build rpmdevtools spectool "dnf-command(builddep)"
rpmdev-setuptree
cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF
cp /work/mangohud.spec ~/rpmbuild/SPECS/
sed -i "s/^Version:.*/Version:        ${VERSION}/" ~/rpmbuild/SPECS/mangohud.spec
sed -i "/^%build$/i %global build_cflags %{build_cflags} ${ARMADA_MARCH}" ~/rpmbuild/SPECS/mangohud.spec
sed -i "/^%build$/i %global build_cxxflags %{build_cxxflags} ${ARMADA_MARCH}" ~/rpmbuild/SPECS/mangohud.spec
cp /work/patches/*.patch ~/rpmbuild/SOURCES/
# fetch the upstream tarball
spectool -g -R ~/rpmbuild/SPECS/mangohud.spec
dnf -y builddep ~/rpmbuild/SPECS/mangohud.spec
# meson downloads subprojects from the wraps (__meson_wrap_mode=default + network)
rpmbuild -bb ~/rpmbuild/SPECS/mangohud.spec
cp ~/rpmbuild/RPMS/*/mangohud-[0-9]*.armada.*.rpm /work/out/
