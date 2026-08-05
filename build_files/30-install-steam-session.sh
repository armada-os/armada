#!/bin/bash
set -euxo pipefail

# Patched Turnip includes the Mesa #14656 VM_BIND fix.
dnf5 -y install --setopt=install_weak_deps=False /packages/mesa/mesa-*.fc44.armada.*.rpm

# Patched mangohud: Adreno GPU load/clock/temp for mainline drm/msm (msm_dpu).
dnf5 -y install --setopt=install_weak_deps=False /packages/mangohud/mangohud-*.fc44.armada.*.rpm

dnf5 -y install --setopt=install_weak_deps=False \
    /packages/gamescope/terra-gamescope{,-libs}-[0-9]*.aarch64.rpm \
    vulkan-loader \
    vulkan-tools \
    gamemode \
    gtk2 \
    openal-soft \
    xorg-x11-server-Xwayland \
    xorg-x11-server-Xvfb

# Patched InputPlumber: dpad signed-axis fix
dnf5 -y install --setopt=install_weak_deps=False /packages/inputplumber/inputplumber-*.rpm

# Patched NetworkManager: /etc/NetworkManager/ignore-sleep keeps wifi up across fake-suspend.
dnf5 -y install --setopt=install_weak_deps=False /packages/networkmanager/*.rpm

dnf5 -y install --setopt=install_weak_deps=False /packages/armada-splash/*.rpm

dnf5 -y install --setopt=install_weak_deps=False /packages/jupiter-hw-support/*.rpm

# Avoid gamescope-session-ogui-steam/-powerstation; Terra's aarch64 deps are broken.
dnf5 -y install --setopt=install_weak_deps=False --enable-repo=terra \
    steam-notif-daemon

# Armada's package carries the rotation, startup timeout, and HDR capability
# integration patches for the common session launcher.
dnf5 -y install --setopt=install_weak_deps=False \
    /packages/gamescope-session/gamescope-session-*.rpm

dnf5 -y install --setopt=install_weak_deps=False \
    erofs-fuse \
    erofs-utils \
    fuse-libs \
    lsb_release \
    squashfuse \
    squashfs-tools

dnf5 -y install --setopt=install_weak_deps=False /packages/fex/fex-emu-*.rpm

# Use Arch rootfs for better compatibility with Linux games targeting SteamOS
mkdir -p /usr/share/fex-emu/RootFS
ARCH_ROOTFS_URL="https://rootfs.fex-emu.gg/ArchLinux/2026-01-08/ArchLinux.sqsh"
ARCH_ROOTFS_SHA256="cb059973b7953ad9165845529655189b96f9a174b14a6a149c87ec884b0c5e90"
curl --retry 3 --retry-delay 2 -fsSL -o /usr/share/fex-emu/RootFS/ArchLinux.sqsh "${ARCH_ROOTFS_URL}"
echo "${ARCH_ROOTFS_SHA256}  /usr/share/fex-emu/RootFS/ArchLinux.sqsh" | sha256sum -c -

# /usr/share config stays user-overridable; ~/.fex-emu would mask it.
cat > /usr/share/fex-emu/Config.json <<'EOF'
{
  "Config": {
    "RootFS": "ArchLinux.sqsh",
    "TSOEnabled": "1",
    "X87ReducedPrecision": "1",
    "Multiblock": "0",
    "VectorTSOEnabled": "0",
    "MemcpySetTSOEnabled": "0",
    "HalfBarrierTSOEnabled": "1",
    "ThunkHostLibs": "/usr/lib64/fex-emu/HostThunks",
    "ThunkGuestLibs": "/usr/share/fex-emu/GuestThunks"
  },
  "ThunksDB": {
    "Vulkan": 1,
    "GL": 1,
    "EGL": 1,
    "drm": 1,
    "WaylandClient": 1,
    "asound": 1
  }
}
EOF

# Bypass Terra's i686-only steam dependency; armada launches native ARM Steam.
mkdir -p /tmp/gss-rpm
dnf5 download --enable-repo=terra --destdir=/tmp/gss-rpm gamescope-session-steam
rpm -ivh --nodeps /tmp/gss-rpm/gamescope-session-steam-*.rpm
rm -rf /tmp/gss-rpm

STEAM_BOOTSTRAP_HOME=/var/home/armada
STEAM_HOME="${STEAM_BOOTSTRAP_HOME}/.local/share/Steam"

STEAM_BOOTSTRAP_HOME="${STEAM_BOOTSTRAP_HOME}" bash /ctx/build_files/generate-steam-bootstrap.sh
rm -f /etc/steamos-oobe-image

PROTON_VER="11.0-20260703-slr"
PROTON_ARCHIVE_NAME="proton-cachyos-${PROTON_VER}-arm64"
# Keep this in sync with armada-fixups when changing Proton major/minor lines.
PROTON_TOOL_NAME="proton-cachyos-11.0-arm64"
PROTON_TAR="${PROTON_ARCHIVE_NAME}.tar.xz"
PROTON_URL="https://github.com/CachyOS/proton-cachyos/releases/download/cachyos-${PROTON_VER}/${PROTON_TAR}"
PROTON_SHA512_URL="https://github.com/CachyOS/proton-cachyos/releases/download/cachyos-${PROTON_VER}/${PROTON_ARCHIVE_NAME}.sha512sum"

curl --retry 3 --retry-delay 2 -fsSL -o "/tmp/${PROTON_TAR}" "${PROTON_URL}"
curl --retry 3 --retry-delay 2 -fsSL -o "/tmp/${PROTON_ARCHIVE_NAME}.sha512sum" "${PROTON_SHA512_URL}"
cd /tmp
sha512sum -c "${PROTON_ARCHIVE_NAME}.sha512sum"

# Ship Proton in the image, not the user's /var home: /var is install-only on
# bootc and custom compat tools don't self-update, so a home copy would freeze.
PROTON_DIR="/usr/share/steam/compatibilitytools.d"
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
python3 /ctx/build_files/set-steam-default-compat.py "${STEAM_HOME}" "${PROTON_TOOL_NAME}" "${PROTON_DIR}"
rm -f "/tmp/${PROTON_TAR}" "/tmp/${PROTON_ARCHIVE_NAME}.sha512sum"

# Pin Steam, Proton, and the FEX rootfs to their own rechunk layers (build-chunked-oci reads the
# user.component xattr) so a system_files change doesn't re-pull them every OTA.
python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"steam")' "${STEAM_HOME}"
python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"proton")' "${PROTON_DIR}/${PROTON_TOOL_NAME}"
python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"fex-rootfs")' /usr/share/fex-emu/RootFS

echo "Pre-staged: ARM64 Steam bootstrap + CachyOS Proton 11 ${PROTON_VER}"
