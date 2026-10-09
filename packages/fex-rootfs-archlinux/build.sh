#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

source /src/toolchain.env

rm -rf out
mkdir -p out

dnf -y install --skip-unavailable rpmdevtools spectool "dnf-command(builddep)"
dnf -y builddep fex-emu-rootfs-archlinux.spec

rpmdev-setuptree

cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF

cp fex-emu-rootfs-archlinux.spec ~/rpmbuild/SPECS/
cp armada-guestos-mount armada-guestos.service \
   ~/rpmbuild/SOURCES/

spectool -g -R ~/rpmbuild/SPECS/fex-emu-rootfs-archlinux.spec
rpmbuild -bb ~/rpmbuild/SPECS/fex-emu-rootfs-archlinux.spec

cp ~/rpmbuild/RPMS/noarch/*.rpm /work/out/
