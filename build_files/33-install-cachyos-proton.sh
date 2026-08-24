#!/bin/bash
set -euxo pipefail

: "${PROTON_VERSION:?PROTON_VERSION must be resolved before the build}"
: "${PROTON_SHA256:?PROTON_SHA256 must be resolved before the build}"

STEAM_HOME=/var/home/armada/.local/share/Steam
PROTON_ARCHIVE_NAME="proton-cachyos-${PROTON_VERSION}-arm64"
PROTON_TAR="${PROTON_ARCHIVE_NAME}.tar.xz"
PROTON_URL="https://github.com/CachyOS/proton-cachyos/releases/download/cachyos-${PROTON_VERSION}/${PROTON_TAR}"
PROTON_TOOL_NAME=proton-cachyos-11.0-arm64

curl --retry 12 --retry-delay 10 -fsSL -o "/tmp/${PROTON_TAR}" "${PROTON_URL}"
printf '%s  %s\n' "${PROTON_SHA256}" "/tmp/${PROTON_TAR}" | sha256sum -c -

# Ship Proton in the image, not the user's /var home: /var is install-only on
# bootc and custom compat tools don't self-update, so a home copy would freeze.
PROTON_DIR=/usr/share/steam/compatibilitytools.d
mkdir -p "${PROTON_DIR}"
tar -xJf "/tmp/${PROTON_TAR}" -C "${PROTON_DIR}/"
if [[ ! -d "${PROTON_DIR}/${PROTON_ARCHIVE_NAME}" ]]; then
    echo "ERROR: CachyOS Proton archive did not extract ${PROTON_ARCHIVE_NAME}" >&2
    exit 1
fi
rm -rf "${PROTON_DIR:?}/${PROTON_TOOL_NAME}"
mv "${PROTON_DIR}/${PROTON_ARCHIVE_NAME}" "${PROTON_DIR}/${PROTON_TOOL_NAME}"
# Missing runtime app makes Steam fall back to Proton 10.
sed -i '/require_tool_appid/d' "${PROTON_DIR}/${PROTON_TOOL_NAME}/toolmanifest.vdf"
python3 /ctx/build_files/patch-proton-cachyos-dxvk-probe.py \
    "${PROTON_DIR}/${PROTON_TOOL_NAME}/proton"
python3 /ctx/build_files/set-steam-default-compat.py \
    "${STEAM_HOME}" "${PROTON_TOOL_NAME}" "${PROTON_DIR}"
rm -f "/tmp/${PROTON_TAR}"

python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"proton")' \
    "${PROTON_DIR}/${PROTON_TOOL_NAME}"

echo "Pre-staged CachyOS Proton ${PROTON_VERSION}"
