#!/bin/bash
set -euxo pipefail

cp -a /ctx/system_files/. /
install -Dpm 0755 /packages/extest/libextest.so /usr/lib/extest/libextest.so

# The source tree carries the qualified EDID as reviewable hexadecimal text. The
# image build materializes the exact 256-byte seed that Gamescope copies into
# the session user's runtime directory before generating its live patched EDID.
python3 - /usr/share/armada/hdr/ayn-odin-3.edid.hex \
    /usr/share/armada/hdr/ayn-odin-3.edid.bin <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
try:
    payload = bytes.fromhex(source.read_text(encoding="ascii"))
except (OSError, UnicodeError, ValueError) as error:
    raise SystemExit(f"ERROR: invalid Odin 3 HDR EDID source: {error}")
if len(payload) != 256:
    raise SystemExit(f"ERROR: Odin 3 HDR EDID is {len(payload)} bytes, expected 256")
target.write_bytes(payload)
PY
echo 'a6ee4ff0c7f43723c093ea2575221a52668e7d610c13738274bf0cef61c96695  /usr/share/armada/hdr/ayn-odin-3.edid.bin' \
    | sha256sum -c -
chmod 0644 /usr/share/armada/hdr/ayn-odin-3.edid.bin
rm -f /usr/share/armada/hdr/ayn-odin-3.edid.hex

# mkbootimg must be present for on-device /KERNEL rebuilds after OTA.
install -Dpm 0755 /ctx/build_files/vendor/mkbootimg/mkbootimg.py /usr/libexec/armada/mkbootimg.py
install -Dpm 0755 /ctx/build_files/vendor/mkbootimg/gki/generate_gki_certificate.py /usr/libexec/armada/gki/generate_gki_certificate.py
sha256sum -c <<'EOF'
37d84b3d162e0bc62e36c1f4e1c63c85ea0caa9f29be023eb2f8efe006ad948c  /usr/libexec/armada/mkbootimg.py
1bb1feec68a13da18d581aa2c631798f86f6bc10b55d587b2dd31446a0f8a203  /usr/libexec/armada/gki/generate_gki_certificate.py
EOF

chmod 0755 /usr/libexec/armada/*
chmod 0755 /usr/libexec/os-session-select

test -x /usr/libexec/armada/hdr-session-finalize
test -x /usr/libexec/armada/gamescope-odin3-hdr
test -f /usr/share/gamescope/scripts/00-armada-session-policy.lua
test -f /usr/share/gamescope/scripts/10-armada/ayn.odin3.oled.lua
test "$(cat /usr/lib/armada/gamescope-hdr-capabilities)" = \
    expose-client-sampleable-formats-v1

sed -i '/const allPanels/,$d' /usr/share/plasma/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js
sed -i '$r /usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/armada-pins.js' /usr/share/plasma/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js

find /etc/NetworkManager/system-connections -name '*.nmconnection' -exec chmod 0600 {} + -exec chown root:root {} + 2>/dev/null || true

systemctl disable getty@tty1.service || true
systemctl disable sshd.service || true
systemctl enable sddm.service
systemctl enable armada-session-default.service
systemctl enable seatd.service
systemctl enable armada-input-calibration.service
systemctl enable armada-controller-type.service
systemctl enable inputplumber.service
systemctl enable armada-device-quirks.service
systemctl enable armada-fixups.service
systemctl enable armada-installer-visibility.service
systemctl enable armada-steamapps.service
systemctl enable armada-powerd.service
systemctl enable armada-control.service
systemctl enable armada-steamos-manager.service
systemctl --global enable armada-steamos-manager.service
systemctl enable armada-bootimg-sync.service
systemctl enable armada-flatpak-setup.service
systemctl enable armada-waydroid-input.path
systemctl disable waydroid-container.service

# Updates are manual (Steam UI / steamos-update). The base image enables this
# timer, which would auto-pull multi-GB images on metered tethering. Opt in with
# `systemctl unmask --now bootc-fetch-apply-updates.timer`.
systemctl mask bootc-fetch-apply-updates.timer

# bootupd targets UEFI bootloaders.
systemctl mask bootloader-update.service

# irqbalance re-spreads IRQs across all cores, overriding Armada's IRQ affinity policy.
systemctl mask irqbalance.service

# Only plain suspend is supported (via the suspend-dispatch drop-in); mask the rest.
systemctl mask systemd-hibernate.service systemd-hybrid-sleep.service systemd-suspend-then-hibernate.service
