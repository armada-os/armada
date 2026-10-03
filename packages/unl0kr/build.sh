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
cp /work/unl0kr.spec ~/rpmbuild/SPECS/
sed -i "s/^Version:.*/Version:        ${VERSION}/" ~/rpmbuild/SPECS/unl0kr.spec
cp /work/patches/*.patch ~/rpmbuild/SOURCES/
spectool -g -R --define "lvgl_commit ${LVGL_COMMIT}" ~/rpmbuild/SPECS/unl0kr.spec
dnf -y builddep --define "lvgl_commit ${LVGL_COMMIT}" ~/rpmbuild/SPECS/unl0kr.spec
rpmbuild -bb --define "lvgl_commit ${LVGL_COMMIT}" ~/rpmbuild/SPECS/unl0kr.spec
cp ~/rpmbuild/RPMS/*/unl0kr-[0-9]*.armada.*.rpm /work/out/
