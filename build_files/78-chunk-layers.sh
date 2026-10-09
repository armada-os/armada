#!/bin/bash
set -euxo pipefail

# A separate rechunk component keeps a driver bump from invalidating unrelated layers.
python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"turnip")' /usr/share/armada/turnip

# Identify large independently updated components for content-aware layer packing.
python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"steam")' \
    "/var/home/armada/.local/share/Steam"

python3 -c 'import os,sys; os.setxattr(sys.argv[1],"user.component",b"proton")' \
    "/usr/share/steam/compatibilitytools.d/proton-cachyos-11.0-arm64"
