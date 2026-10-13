#!/usr/bin/bash
set -euxo pipefail

NAME=armada-logos

rm -rf out
mkdir -p out

cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF

dnf -y install --skip-unavailable \
  rpm-build rpmdevtools dnf-plugins-core \
  tar gzip
dnf -y builddep "${NAME}.spec"
rpmdev-setuptree

cp "${NAME}.spec" ~/rpmbuild/SPECS/

spectool -g -R ~/rpmbuild/SPECS/"${NAME}".spec
rpmbuild -bb ~/rpmbuild/SPECS/"${NAME}".spec

cp ~/rpmbuild/RPMS/noarch/*.rpm /work/out/
