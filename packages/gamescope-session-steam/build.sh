#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

source /src/TERRA.env
source /src/toolchain.env

rm -rf out
mkdir -p out

source /etc/os-release

dnf install -y --nogpgcheck --repofrompath "terra,https://repos.fyralabs.com/terra${VERSION_ID}" terra-release
dnf -y install --skip-unavailable \
    anda anda-srpm-macros

cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF

git clone https://github.com/terrapkg/packages.git /tmp/packages

cd /tmp/packages

git checkout ${TERRA_COMMIT}

PKG=anda/games/gamescope-session-steam
SPEC="${PKG}/gamescope-session-steam.spec"

mapfile -t PATCHES < <(
  find /work/patches \
    -maxdepth 1 \
    -type f \
    -name "[0-9][0-9][0-9][0-9]-*.patch" \
    -printf "%f\n" |
    sort -V
)

INSERT_LINE="$(
  grep -n -m1 "BuildArch:" "${SPEC}" |
    cut -d: -f1
)"

{
  head -n "$((INSERT_LINE - 1))" "${SPEC}"

  if (( ${#PATCHES[@]} > 0 )); then
    printf "Patch:         %s\n" "${PATCHES[@]}"
    printf "\n"
  fi

  tail -n "+${INSERT_LINE}" "${SPEC}"
} >"${SPEC}.tmp"

mv "${SPEC}.tmp" "${SPEC}"

for patch in "${PATCHES[@]}"; do
  install -m0644 "/work/patches/${patch}" "${PKG}/${patch}"
done

TIMESTAMP=$(TZ=UTC date +%m%d%H)

sed -i \
  -e "/^Release:/s/%{?dist}/.${TIMESTAMP}%{?dist}.armada/" \
  -e "/^%build$/i %global build_cflags %{build_cflags} ${ARMADA_MARCH}" \
  -e "/^%build$/i %global build_cxxflags %{build_cxxflags} ${ARMADA_MARCH}" \
  -e "s/^Requires:       steam\>/#Requires:       steam/" \
  -e "s/^%autosetup\>/%autosetup -p1/" \
  "${SPEC}"

# Fail in case spec is invalid
rpmspec -P "${SPEC}" >/dev/null

dnf -y builddep "${SPEC}"
anda build --rpm-builder=rpmbuild "${PKG}/pkg"

cp /tmp/packages/anda-build/rpm/rpms/*.rpm /work/out/
