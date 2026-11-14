#!/usr/bin/env bash
set -euxo pipefail

source /src/toolchain.env

name=armada-autohdr
rm -rf out
mkdir -p out

dnf -y install rpm-build dnf-plugins-core tar gzip
dnf -y builddep "$name.spec"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
tar -C /work -czf "$work/SOURCES/$name.tar.gz" \
    CMakeLists.txt armada-autohdr.pc.in include src tests README.md

rpmbuild -bb \
    --define "_topdir $work" \
    --define "armada_march ${ARMADA_MARCH}" \
    "$name.spec"
cp "$work"/RPMS/*/*.rpm out/
