#!/bin/bash
set -euxo pipefail

# Someone needs to comment what this is and why it exists
mkdir -p /usr/share/armada
cp -a /packages/mesa/turnip /usr/share/armada/turnip

# Is this still needed? If so, can we make it an rpm. This is messy
install -Dpm 0755 /packages/extest/libextest.so /usr/lib/extest/libextest.so

# Patched mesa for waydroid, fixes SM8750 display problems
mkdir -p /usr/share/armada/waydroid
cp -a /packages/mesa-android/waydroid/vendor /usr/share/armada/waydroid/


# Mesa squashfs file for fex-emu
install -Dm0644 /packages/mesa-x86/ArmadaMesa.sqsh "/usr/share/fex-emu/RootFS/ArmadaMesa.sqsh"


# protontricks needs winetricks, fedora's version needs wine-common
# which is not provided for arm64, use the github version directly instead
WINETRICKS_VER="20260125"
WINETRICKS_SHA256="431f82fc74000e6c864409f1d8fb495d696c03928808e3e8acffc45179312a7b"
curl --retry 3 --retry-delay 2 -fsSL -o /usr/bin/winetricks \
    "https://raw.githubusercontent.com/Winetricks/winetricks/${WINETRICKS_VER}/src/winetricks"
echo "${WINETRICKS_SHA256}  /usr/bin/winetricks" | sha256sum -c -
chmod 0755 /usr/bin/winetricks

pkgs=(
    # Patched NetworkManager: /etc/NetworkManager/ignore-sleep keeps wifi up across fake-suspend.
    /packages/networkmanager/*.rpm
    /packages/wpa_supplicant/*.rpm


    # Boot splash for Armada, runs all the way from initramfs into gamescope
    /packages/armada-splash/*.rpm

    # RGB support package for handhelds
    /packages/armada-rgb/*.rpm

    # Patched KWin lets devices pin Plasma's virtual keyboard to a configured output.
    /packages/kwin/kwin-[0-9]*.rpm
    /packages/kwin/kwin-common-[0-9]*.rpm
    /packages/kwin/kwin-libs-[0-9]*.rpm

    # Carry Plasma Mobile's input-region crash fix until Fedora backports it.
    /packages/plasma-mobile/plasma-mobile-[0-9]*.rpm
    /packages/plasma-mobile/plasma-lookandfeel-fedora-mobile-[0-9]*.rpm

    # PowerDevil's KWin backend treats 0 as safe; reserve 5% for internal panels.
    /packages/powerdevil/powerdevil-*.fc44.armada.*.rpm

    # scx_cosmos/scx_lavd for the Armada Control scheduler setting; without the
    # binaries armada-powerd reports the scheduler choice as unavailable.
    /packages/scx-scheds/scx-scheds-[0-9]*.rpm

    # MTP support
    /packages/umtp-responder/umtp-responder-*.rpm

    # Patched Turnip includes the Mesa #14656 VM_BIND fix.
    /packages/mesa/mesa-*.fc44.armada.*.rpm

    # Patched mangohud: Adreno GPU load/clock/temp for mainline drm/msm (msm_dpu).
    /packages/mangohud/mangohud-*.fc44.armada.*.rpm

    # Patched InputPlumber: dpad signed-axis fix
    /packages/inputplumber/inputplumber-*.rpm

    # FEX Emu for emulating x86_64 applications
    /packages/fex/fex-emu-*.rpm
    /packages/fex-rootfs-archlinux/*.rpm

    # FIXME: drop when protontricks is in arm64 flathub
    /packages/protontricks/protontricks-[0-9]*.rpm
)

dnf5 -y install --setopt=install_weak_deps=False "${pkgs[@]}"
