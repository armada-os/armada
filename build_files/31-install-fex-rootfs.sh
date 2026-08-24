#!/bin/bash
set -euxo pipefail

: "${ARCH_ROOTFS_URL:?ARCH_ROOTFS_URL must be resolved before the build}"
: "${ARCH_ROOTFS_XXH64:?ARCH_ROOTFS_XXH64 must be resolved before the build}"

mkdir -p /usr/share/fex-emu/RootFS
rootfs=/usr/share/fex-emu/RootFS/ArchLinux.sqsh
curl --retry 3 --retry-delay 2 -fsSL -o "${rootfs}" "${ARCH_ROOTFS_URL}"
printf '%s  %s\n' "${ARCH_ROOTFS_XXH64}" "${rootfs}" | xxhsum -c -

# Steam's FEX compat tool needs the manifest the rootfs ships; a bump to a
# rootfs without one would otherwise fail only at x86 game launch.
unsquashfs -cat "${rootfs}" graphics_provider.json | python3 -m json.tool >/dev/null

# Mountpoint for the rootfs at the path Steam's FEX compat tool hardcodes.
mkdir -p /usr/share/guestos/fex-mesa

cat > /usr/share/fex-emu/Config.json <<'EOF'
{
  "Config": {
    "RootFS": "/usr/share/guestos/fex-mesa",
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
    "drm": 1,
    "WaylandClient": 1,
    "asound": 1
  }
}
EOF

python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"fex-rootfs")' \
    /usr/share/fex-emu/RootFS
