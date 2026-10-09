#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

source ./BASE.env

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
cp /work/jupiter-hw-support.spec ~/rpmbuild/SPECS/
sed -i "s/^Version:.*/Version:        ${VERSION}/" ~/rpmbuild/SPECS/jupiter-hw-support.spec
sed -i "s/^%global packagever .*/%global packagever ${PACKAGEVER}/" ~/rpmbuild/SPECS/jupiter-hw-support.spec
cp /work/patches/*.patch ~/rpmbuild/SOURCES/
cp /work/org.armada.jupiter-hw-support.policy ~/rpmbuild/SOURCES/
cp /work/50-armada-jupiter-hw-support.rules ~/rpmbuild/SOURCES/
spectool -g -R ~/rpmbuild/SPECS/jupiter-hw-support.spec
dnf -y builddep ~/rpmbuild/SPECS/jupiter-hw-support.spec
rpmbuild -bb ~/rpmbuild/SPECS/jupiter-hw-support.spec
cp ~/rpmbuild/RPMS/noarch/armada-jupiter-hw-support-*.rpm /work/out/
