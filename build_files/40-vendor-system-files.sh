#!/bin/bash
set -euxo pipefail

cp -a /ctx/system_files/. /
install -Dpm 0755 /packages/extest/libextest.so /usr/lib/extest/libextest.so

# mkbootimg must be present for on-device /KERNEL rebuilds after OTA.
bash /ctx/build_files/fetch-mkbootimg.sh /usr/libexec/armada
chmod 0755 /usr/libexec/armada/mkbootimg.py /usr/libexec/armada/gki/generate_gki_certificate.py

chmod 0755 /usr/libexec/armada/*
chmod 0755 /usr/libexec/os-session-select

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
systemctl enable armada-steamos-manager.service
systemctl --global enable armada-steamos-manager.service
systemctl enable armada-bootimg-sync.service
systemctl enable armada-flatpak-setup.service

# Updates are manual (Steam UI / steamos-update). The base image enables this
# timer, which would auto-pull multi-GB images on metered tethering. Opt in with
# `systemctl unmask --now bootc-fetch-apply-updates.timer`.
systemctl mask bootc-fetch-apply-updates.timer

# systemd-suspend.service is overridden (drop-in) to use s2idle when available,
# falling back to fake-suspend. Mask other sleep ops to keep a single path.
systemctl mask systemd-hibernate.service systemd-hybrid-sleep.service systemd-suspend-then-hibernate.service
