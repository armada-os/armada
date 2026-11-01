#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

source ./BASE.env

REST="${SRPM#plasma-mobile-}"
PLASMA_MOBILE_VER="${REST%%-*}"
PLASMA_MOBILE_REL="${REST#*-}"
PLASMA_MOBILE_REL="${PLASMA_MOBILE_REL%.fc*}"
DIST=".fc44.armada"

rm -rf out
mkdir -p out

export HOME=/tmp
dnf -y install rpm-build rpmdevtools koji "dnf-command(builddep)"
rpmdev-setuptree
cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF

cd /tmp
koji download-build --arch=src "${SRPM}"
rpm -i "${SRPM}.src.rpm"
SPEC="$HOME/rpmbuild/SPECS/plasma-mobile.spec"

sed -i "s/^Release:.*/Release: ${PLASMA_MOBILE_REL}%{?dist}/" "$SPEC"

dnf -y builddep "$SPEC"
rpmbuild -bb --define "dist ${DIST}" "$SPEC"

cp "$HOME"/rpmbuild/RPMS/*/plasma-mobile-"${PLASMA_MOBILE_VER}-${PLASMA_MOBILE_REL}${DIST}".*.rpm /work/out/
cp "$HOME"/rpmbuild/RPMS/*/plasma-lookandfeel-fedora-mobile-"${PLASMA_MOBILE_VER}-${PLASMA_MOBILE_REL}${DIST}".*.rpm /work/out/
