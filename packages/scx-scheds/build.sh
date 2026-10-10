#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

source /src/TERRA.env
source ./BASE.env

rm -rf out
mkdir -p out

source /etc/os-release

dnf install -y --nogpgcheck --repofrompath "terra,https://repos.fyralabs.com/terra${VERSION_ID}" terra-release
dnf -y install --skip-unavailable \
    anda anda-srpm-macros
dnf -y install mold

cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF

git clone https://github.com/terrapkg/packages.git /tmp/packages

cd /tmp/packages

git checkout ${TERRA_COMMIT}

PKG=anda/system/scx-scheds/stable
SPEC="${PKG}/scx-scheds.spec"

VERSION="$(sed -n 's/^Version:[[:space:]]*//p' "${SPEC}")"
[[ "${STEAMOS_TAG}" == "v${VERSION}.linux."* ]] || {
  echo "ERROR: ${STEAMOS_TAG} is not a SteamOS build of scx ${VERSION}"
  exit 1
}

# vendor/ is unused: the spec's cargo prep discards .cargo and fetches from Cargo.lock
curl -fL --retry 3 -o /tmp/steamos-scx.src.tar.gz "${STEAMOS_SRC_URL}"
echo "${STEAMOS_SRC_SHA256}  /tmp/steamos-scx.src.tar.gz" | sha256sum -c -
tar -xzf /tmp/steamos-scx.src.tar.gz -C /tmp scx-scheds/scx
[ "$(git --git-dir=/tmp/scx-scheds/scx rev-parse "${STEAMOS_TAG}^{commit}")" = "${STEAMOS_COMMIT}" ]
git --git-dir=/tmp/scx-scheds/scx archive --prefix="scx-${VERSION}/" "${STEAMOS_TAG}" ':!vendor' |
  gzip -1 >"${PKG}/scx-steamos.tar.gz"
rm -rf /tmp/scx-scheds /tmp/steamos-scx.src.tar.gz

# scx_nitosis, like scx_mitosis, has a ktstr-tests feature that forces a static libelf build
sed -i \
  -e "/^Release:/s/%{?dist}/.${STEAMOS_TAG#v*.linux.}%{?dist}.armada/" \
  -e "s/^Source0:.*/Source0:        scx-steamos.tar.gz/" \
  -e "/--exclude scx_mitosis/i\\     --exclude scx_nitosis \\\\" \
  "${SPEC}"

grep -q '^Release:.*armada' "${SPEC}" || {
  echo "ERROR: failed to add Armada release suffix to scx-scheds spec"
  grep '^Release:' "${SPEC}"
  exit 1
}
grep -q -- '--exclude scx_nitosis' "${SPEC}" || {
  echo "ERROR: scx-scheds spec no longer excludes scx_mitosis; adjust build.sh"
  exit 1
}

rpmspec -P "${SPEC}" >/dev/null

dnf -y builddep "${SPEC}"
anda build --rpm-builder=rpmbuild "${PKG}/pkg"

cp /tmp/packages/anda-build/rpm/rpms/scx-scheds-[0-9]*.rpm /work/out/
