#!/bin/bash
set -euxo pipefail

: "${STEAM_ARM_RUNTIME_SNAPSHOT:?STEAM_ARM_RUNTIME_SNAPSHOT must be resolved before the build}"
: "${STEAM_ARM_MANIFEST_SHA256:?STEAM_ARM_MANIFEST_SHA256 must be resolved before the build}"

STEAM_BOOTSTRAP_HOME=/var/home/armada
STEAM_HOME="${STEAM_BOOTSTRAP_HOME}/.local/share/Steam"

STEAM_BOOTSTRAP_HOME="${STEAM_BOOTSTRAP_HOME}" \
STEAM_ARM_RUNTIME_SNAPSHOT="${STEAM_ARM_RUNTIME_SNAPSHOT}" \
STEAM_ARM_MANIFEST_SHA256="${STEAM_ARM_MANIFEST_SHA256}" \
    bash /ctx/build_files/generate-steam-bootstrap.sh
rm -f /etc/steamos-oobe-image

python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"steam")' "${STEAM_HOME}"
