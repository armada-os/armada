#!/bin/bash
set -euxo pipefail

source ./BASE.env
source /src/toolchain.env

dnf -y install python3

PROTON_ARCHIVE_NAME="proton-cachyos-${PROTON_VER}-arm64"
PROTON_TAR="${PROTON_ARCHIVE_NAME}.tar.xz"
PROTON_URL="https://github.com/CachyOS/proton-cachyos/releases/download/cachyos-${PROTON_VER}/${PROTON_TAR}"
PROTON_SHA512_URL="https://github.com/CachyOS/proton-cachyos/releases/download/cachyos-${PROTON_VER}/${PROTON_ARCHIVE_NAME}.sha512sum"

curl --retry 12 --retry-delay 10 -fsSL -o "/tmp/${PROTON_TAR}" "${PROTON_URL}"
curl --retry 12 --retry-delay 10 -fsSL -o "/tmp/${PROTON_ARCHIVE_NAME}.sha512sum" "${PROTON_SHA512_URL}"
cd /tmp
sha512sum -c "${PROTON_ARCHIVE_NAME}.sha512sum"

tar -xJf "/tmp/${PROTON_TAR}" -C "/tmp/"

if [[ ! -d "/tmp/${PROTON_ARCHIVE_NAME}" ]]; then
    echo "ERROR: CachyOS Proton archive did not extract ${PROTON_ARCHIVE_NAME}" >&2
    exit 1
fi

mkdir -p /work/out/

mv "/tmp/${PROTON_ARCHIVE_NAME}" "/work/out/${PROTON_TOOL_NAME}"

python3 /work/patch-proton-cachyos-dxvk-probe.py \
    "/work/out/${PROTON_TOOL_NAME}/proton"

python3 /work/set-tool-name.py "${PROTON_TOOL_NAME}" "/work/out"
