#!/bin/bash
set -euxo pipefail

source /work/BASE.env
HOME_DIR=/work/work/home
STEAM="${HOME_DIR}/.local/share/Steam"

# The Steam tree: staged into the image's /var/home at build time, and the one
# copy that repairs and resets restore from.
rm -rf "${HOME_DIR}"
mkdir -p "${STEAM%/*}"
python3 /work/unpack.py /work/work/feed "${STEAM_CLIENT_CHANNEL}" "${STEAM_CLIENT_VERSION}" "${STEAM}"

printf '%s\n' "${STEAM_CLIENT_VERSION}" > /work/out/version
cp /work/BASE.env /work/out/BASE.env
tar --sort=name --owner=1000 --group=1000 --numeric-owner \
    -C "${HOME_DIR}" -cf - . | zstd -T0 -3 -o /work/out/steam-bootstrap.tar.zst.tmp -f
mv /work/out/steam-bootstrap.tar.zst.tmp /work/out/steam-bootstrap.tar.zst
(cd /work/out && sha256sum steam-bootstrap.tar.zst > steam-bootstrap.tar.zst.sha256)

# The launcher and installer scripts.
cat >/etc/rpm/macros.armada <<EOT
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOT
rpmdev-setuptree
cp steam.spec ~/rpmbuild/SPECS/
tar -czf ~/rpmbuild/SOURCES/steam.tar.gz -C / --exclude=work/work --exclude=work/out work
rpmbuild -bb --define "steam_version ${STEAM_CLIENT_VERSION}" ~/rpmbuild/SPECS/steam.spec
cp ~/rpmbuild/RPMS/noarch/*.rpm /work/out/
