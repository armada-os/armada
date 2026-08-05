#!/bin/bash
set -euxo pipefail

# Firmware for unrelated hardware.
dnf5 -y remove --no-autoremove \
    amd-gpu-firmware \
    amd-ucode-firmware \
    brcmfmac-firmware \
    cirrus-audio-firmware \
    intel-audio-firmware \
    intel-gpu-firmware \
    mt7xxx-firmware \
    nvidia-gpu-firmware \
    nxpwireless-firmware \
    qcom-wwan-firmware \
    realtek-firmware \
    tiwilink-firmware

rm -f /usr/lib/binfmt.d/qemu-*.conf

# AWS SDK chain from the bootc base.
dnf5 -y remove --no-autoremove \
    python3-boto3 \
    python3-botocore \
    python3-s3transfer

dnf5 -y remove --no-autoremove binutils

for required in qcom-firmware atheros-firmware bootc podman skopeo gamescope-session; do
    rpm -q "$required" >/dev/null || { echo "ERROR: $required got removed"; exit 1; }
done

# armada-splash owns the console; plymouth would fight it for the VT.
if rpm -q plymouth >/dev/null 2>&1; then
    echo "ERROR: plymouth got installed; a dependency dragged it in"
    exit 1
fi

for package in \
    armada-jupiter-hw-support \
    armada-splash \
    fex-emu-utils \
    terra-gamescope \
    terra-gamescope-libs \
    inputplumber \
    mangohud \
    mesa-vulkan-drivers \
    NetworkManager \
    powerdevil; do
    case "$(rpm -q --qf '%{release}' "$package" 2>/dev/null)" in
        *armada*) ;;
        *) echo "ERROR: patched .armada package not installed: $package"; exit 1 ;;
    esac
done

rm -rf \
    /usr/lib/firmware/amdgpu \
    /usr/lib/firmware/amd-ucode \
    /usr/lib/firmware/brcm \
    /usr/lib/firmware/cirrus \
    /usr/lib/firmware/cypress \
    /usr/lib/firmware/intel \
    /usr/lib/firmware/i915 \
    /usr/lib/firmware/iwlwifi-* \
    /usr/lib/firmware/mediatek \
    /usr/lib/firmware/mrvl \
    /usr/lib/firmware/nvidia \
    /usr/lib/firmware/nxp \
    /usr/lib/firmware/rtw89 \
    /usr/lib/firmware/rtl_nic \
    /usr/lib/firmware/ti-connectivity \
    /usr/lib/firmware/xe
