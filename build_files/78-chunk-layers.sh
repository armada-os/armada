#!/bin/bash
set -euxo pipefail

# A separate rechunk component keeps a driver bump from invalidating unrelated layers.
python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"turnip")' /usr/share/armada/turnip

# Identify large independently updated components for content-aware layer packing.
python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"steam")' \
    "/var/home/armada/.local/share/Steam"

python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"proton")' \
    "/usr/share/steam/compatibilitytools.d/proton-cachyos-11.0-arm64"

python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"fex-rootfs")' \
    /usr/share/fex-emu/RootFS/ArchLinux.sqsh

python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"lepton")' \
    /usr/share/armada/lepton/guestos-android.erofs

# A separate rechunk component keeps Mesa-only updates from invalidating ArchLinux.sqsh.
python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"fex-mesa")' \
    "/usr/share/fex-emu/RootFS/ArmadaMesa.sqsh"
