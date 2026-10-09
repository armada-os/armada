#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

source ./BASE.env

rm -rf out
mkdir -p out

export HOME=/tmp
dnf -y install rpm-build rpmdevtools spectool "dnf-command(builddep)" git-core
rpmdev-setuptree
cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF
cp /work/umtp-responder.spec ~/rpmbuild/SPECS/
sed -i "s/^Version:.*/Version:        ${VERSION}/" ~/rpmbuild/SPECS/umtp-responder.spec
cp /work/patches/*.patch ~/rpmbuild/SOURCES/
spectool -g -R --define "commit ${COMMIT}" ~/rpmbuild/SPECS/umtp-responder.spec
dnf -y builddep --define "commit ${COMMIT}" ~/rpmbuild/SPECS/umtp-responder.spec
rpmbuild -bb --define "commit ${COMMIT}" ~/rpmbuild/SPECS/umtp-responder.spec
cp ~/rpmbuild/RPMS/*/umtp-responder-[0-9]*.armada.*.rpm /work/out/
