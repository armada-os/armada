#!/bin/bash
set -euxo pipefail

cd /ctx/build_files

./05-configure-dnf.sh
./10-base-packages.sh
./20-install-kernel.sh
./30-install-steam-session.sh
./40-vendor-system-files.sh
./45-install-decky-plugins.sh
./50-create-user.sh
./55-generate-initramfs.sh
./60-set-default-target.sh
./70-cleanup.sh
./75-restore-build-dnf.sh
./80-finalize-update-state.sh
