#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FINALIZE=${ROOT}/post_process/finalize-armada-image.sh
bash -n "${FINALIZE}"
grep -Fq 'sudo sfdisk --label dos' "${FINALIZE}"
grep -Fq '"${usr}/libexec/armada/armada-efi-update"' "${FINALIZE}"
grep -Fq '"${REPO_ROOT}/efi/adtbloader" "${WORK}/mnt/adtbloader"' "${FINALIZE}"
grep -Fq 'mount -o ro ' "${FINALIZE}"
grep -Fq 'mount -o ro,subvol=root ' "${FINALIZE}"
! grep -Eq 'bootprefix|fstab|EFI.disabled|mkfs|part-type' "${FINALIZE}"
! test -e "${ROOT}/post_process/finalize-efi-image.sh"
bash -n "${ROOT}/efi/adtbloader/describe_android_dt.sh"

recipe=$(sed -n '/^build-armada-image /,/^\[group/p' "${ROOT}/Justfile")
grep -Fq './post_process/make-bootimg.sh output/image/disk.raw' <<< "${recipe}"
grep -Fq './post_process/finalize-armada-image.sh output/image/disk.raw' <<< "${recipe}"
! grep -Eq 'variant|disk-abl|disk-efi|-abl.img|-efi.img' <<< "${recipe}"
grep -Fq 'name: armada-disk-pr${{ github.event.pull_request.number }}' "${ROOT}/.github/workflows/pr.yml"
grep -Fq 'name: armada-disk-image' "${ROOT}/.github/workflows/build-disk.yml"
! grep -Eq 'matrix|disk-image-abl|disk-image-efi' "${ROOT}/.github/workflows/build-disk.yml"
