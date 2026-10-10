#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "${ROOT}/efi/release.env"

[[ ${ARMADA_ADTBLOADER_VERSION} =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
[[ ${ARMADA_ADTBLOADER_SHA256} =~ ^[a-f0-9]{64}$ ]]
[[ ${ARMADA_BOOT_VERSION} =~ ^[0-9]+(\.[0-9]+)*$ ]]
[[ ${ARMADA_BOOT_SHA256} =~ ^[a-f0-9]{64}$ ]]
grep -Fq 'systemd-boot-unsigned' "${ROOT}/build_files/10-base-packages.sh"
grep -Fq 'edk2-ext4' "${ROOT}/build_files/10-base-packages.sh"
grep -Fq 'https://github.com/armada-os/adtbloader/releases/download/${ARMADA_ADTBLOADER_VERSION}/adtbloader.efi' \
    "${ROOT}/build_files/40-vendor-system-files.sh"
grep -Fq '/usr/lib/armada/efi/drivers/adtbloaderaa64.efi' \
    "${ROOT}/build_files/40-vendor-system-files.sh"
grep -Fq '/usr/share/licenses/armada-adtbloader/LICENSE' \
    "${ROOT}/build_files/40-vendor-system-files.sh"
grep -Fq 'https://github.com/armada-os/armada-efi/releases/download/${ARMADA_BOOT_VERSION}/armada-boot-${ARMADA_BOOT_VERSION}.efi' \
    "${ROOT}/build_files/40-vendor-system-files.sh"
grep -Fq '/usr/lib/armada/efi/armada-boot.efi' \
    "${ROOT}/build_files/40-vendor-system-files.sh"
! grep -i 'refind' "${ROOT}/build_files/40-vendor-system-files.sh"
