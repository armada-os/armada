#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

NAME=openabl-updater

rm -rf out
mkdir -p out

cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF

dnf -y install --skip-unavailable \
  rpm-build rpmdevtools dnf-plugins-core systemd-rpm-macros \
  tar gzip
dnf -y builddep "${NAME}.spec"
rpmdev-setuptree

cp "${NAME}.spec" ~/rpmbuild/SPECS/
tar -cvzf ~/rpmbuild/SOURCES/"${NAME}".tar.gz /work/

spectool -g -R ~/rpmbuild/SPECS/"${NAME}".spec
rpmbuild -bb ~/rpmbuild/SPECS/"${NAME}".spec

cp ~/rpmbuild/RPMS/noarch/*.rpm /work/out/
