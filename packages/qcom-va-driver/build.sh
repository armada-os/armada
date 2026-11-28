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
cp /work/qcom-va-driver.spec ~/rpmbuild/SPECS/
sed -i "s/^Version:.*/Version:        ${VERSION}/" ~/rpmbuild/SPECS/qcom-va-driver.spec
spectool -g -R --define "commit ${COMMIT}" ~/rpmbuild/SPECS/qcom-va-driver.spec
dnf -y builddep --define "commit ${COMMIT}" ~/rpmbuild/SPECS/qcom-va-driver.spec
rpmbuild -bb --define "commit ${COMMIT}" ~/rpmbuild/SPECS/qcom-va-driver.spec
cp ~/rpmbuild/RPMS/*/qcom-va-driver-[0-9]*.armada.*.rpm /work/out/
