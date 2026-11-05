#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

source ./BASE.env

rm -rf out
mkdir -p out

export HOME=/tmp
dnf -y install rpm-build rpmdevtools spectool "dnf-command(builddep)"
rpmdev-setuptree
cat >/etc/rpm/macros.armada <<MACROS
%_buildhost armada-builder
%packager Armada
%vendor Armada
MACROS
cp /work/dtbloader.spec ~/rpmbuild/SPECS/
sed -i "s/^Version:.*/Version:        ${VERSION}/" ~/rpmbuild/SPECS/dtbloader.spec
spectool -g -R ~/rpmbuild/SPECS/dtbloader.spec
echo "${SHA256}  ${HOME}/rpmbuild/SOURCES/dtbloader-${VERSION}.tar.gz" | sha256sum -c -
dnf -y builddep ~/rpmbuild/SPECS/dtbloader.spec
rpmbuild -bb ~/rpmbuild/SPECS/dtbloader.spec
cp ~/rpmbuild/RPMS/*/dtbloader-[0-9]*.armada.*.rpm /work/out/
