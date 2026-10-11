#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

source ./BASE.env

REST="${SRPM#wpa_supplicant-}"
WPA_VER="${REST%%-*}"
WPA_REL="${REST#*-}"
WPA_REL="${WPA_REL%.fc*}"
DIST=".fc44.armada" # sorts above stock .fc44 so dnf upgrades to the armada build

rm -rf out
mkdir -p out

export HOME=/tmp
dnf -y install rpm-build rpmdevtools koji "dnf-command(builddep)" git-core
rpmdev-setuptree
cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF

cd /tmp
koji download-build --arch=src "${SRPM}"
rpm -i "${SRPM}.src.rpm"
SPEC="$HOME/rpmbuild/SPECS/wpa_supplicant.spec"

# Force the stock numeric release so .fc44.armada sorts just above the base
# build, whatever release macro the spec uses.
sed -i "s/^Release:.*/Release:        ${WPA_REL}%{?dist}/" "$SPEC"
sed -i "/^%autochangelog/d" "$SPEC"

cp /work/patches/*.patch "$HOME/rpmbuild/SOURCES/"
LAST=$(grep -nE "^(Patch|Source)[0-9]*:" "$SPEC" | tail -1 | cut -d: -f1)
[ -n "$LAST" ] || { echo "ERROR: no Source/Patch line to anchor on"; exit 1; }
sed -i "${LAST}a Patch9001:       0001-avoid-redundant-6ghz-rescan-after-resume.patch" "$SPEC"
sed -i "$((LAST + 1))a Patch9002:       0002-no-forced-rescan-after-restricted-scan.patch" "$SPEC"

# The patches land only if the spec auto-applies them; assert it so a spec
# change cannot silently drop them (a non-matching patch fails rpmbuild itself).
grep -qE "^[[:space:]]*%(autosetup|autopatch)" "$SPEC" \
    || { echo "ERROR: wpa_supplicant.spec does not auto-apply patches; adjust build.sh"; exit 1; }

dnf -y builddep "$SPEC"
rpmbuild -bb --define "dist ${DIST}" "$SPEC"

# Only the daemon; the -gui subpackage is not installed in the image.
cp "$HOME"/rpmbuild/RPMS/*/"wpa_supplicant-${WPA_VER}-${WPA_REL}${DIST}".*.rpm /work/out/
