#!/usr/bin/bash
# Phase 1: build the FEX x86 sysroot tarball.
#
# Split out from build.sh so CI caches it as its own layer: expensive, and
# changes far less often than FEX itself. build.sh calls it when absent.
set -euxo pipefail

SYSROOT_VERSION="${SYSROOT_VERSION:-fc44-armada}"
SYSROOT_TARBALL="fex-sysroot-${SYSROOT_VERSION}.tar.gz"

dnf -y install dnf-plugins-core rpmdevtools

bash build-fex-sysroot.sh 44
mv fex-sysroot-fc44-*.tar.gz "${SYSROOT_TARBALL}"
