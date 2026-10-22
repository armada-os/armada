#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BACKEND=${ROOT}/system_files/usr/libexec/armada/armada-boot-backend
work=$(mktemp -d)
trap 'rm -rf "${work}"' EXIT
export ESP=${work} CMDLINE=${work}/cmdline
printf 'quiet\n' > "${CMDLINE}"
[ "$("${BACKEND}")" = unknown ]
printf kernel > "${ESP}/KERNEL"
[ "$("${BACKEND}")" = abl ]
mkdir -p "${ESP}/armada" "${ESP}/EFI/BOOT"
printf 'ARMADA_BOOT_BACKEND=efi\nARMADA_BOOT_CONTRACT=1\n' > "${ESP}/armada/backend.conf"
printf loader > "${ESP}/EFI/BOOT/BOOTAA64.EFI"
[ "$("${BACKEND}")" = abl ]
for device in auto qcs8550-ayn-thor; do
    printf 'quiet armada.device=%s ostree=/ostree/boot.0/default/test/0\n' "${device}" > "${CMDLINE}"
    [ "$("${BACKEND}")" = efi ]
done
printf 'quiet other.armada.device=auto\n' > "${CMDLINE}"
[ "$("${BACKEND}")" = abl ]
