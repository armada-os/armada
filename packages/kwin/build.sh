#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

source ./BASE.env

REST="${SRPM#kwin-}"
KWIN_VER="${REST%%-*}"
KWIN_REL="${REST#*-}"
KWIN_REL="${KWIN_REL%.fc*}"
DIST=".fc44.armada"

SUBPKGS="kwin kwin-common kwin-libs"

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
SPEC="$HOME/rpmbuild/SPECS/kwin.spec"

sed -i "s/^Release:.*/Release: ${KWIN_REL}%{?dist}/" "$SPEC"

cp /work/patches/*.patch "$HOME/rpmbuild/SOURCES/"
LAST=$(grep -nE "^(Patch|Source)[0-9]*:" "$SPEC" | tail -1 | cut -d: -f1)
[ -n "$LAST" ] || { echo "ERROR: no Source/Patch line to anchor on"; exit 1; }
sed -i "${LAST}a Patch9001: 0001-input-panel-allow-configuring-output-by-env.patch" "$SPEC"
sed -i "$((LAST + 1))a Patch9002: 0002-x11-windowed-select-touch-events.patch" "$SPEC"

grep -qE "^[[:space:]]*%autosetup" "$SPEC" \
    || { echo "ERROR: kwin.spec does not auto-apply patches; adjust build.sh"; exit 1; }

dnf -y builddep "$SPEC"
rpmbuild -bb --define "dist ${DIST}" "$SPEC"

for p in ${SUBPKGS}; do
    cp "$HOME"/rpmbuild/RPMS/*/"${p}-${KWIN_VER}-${KWIN_REL}${DIST}".*.rpm /work/out/
done
