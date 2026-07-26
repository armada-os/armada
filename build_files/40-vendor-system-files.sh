#!/bin/bash
set -euxo pipefail

cp -a /ctx/system_files/. /
install -Dpm 0755 /packages/extest/libextest.so /usr/lib/extest/libextest.so

# mkbootimg must be present for on-device /KERNEL rebuilds after OTA.
install -Dpm 0755 /ctx/build_files/vendor/mkbootimg/mkbootimg.py /usr/libexec/armada/mkbootimg.py
install -Dpm 0755 /ctx/build_files/vendor/mkbootimg/gki/generate_gki_certificate.py /usr/libexec/armada/gki/generate_gki_certificate.py
sha256sum -c <<'EOF'
37d84b3d162e0bc62e36c1f4e1c63c85ea0caa9f29be023eb2f8efe006ad948c  /usr/libexec/armada/mkbootimg.py
1bb1feec68a13da18d581aa2c631798f86f6bc10b55d587b2dd31446a0f8a203  /usr/libexec/armada/gki/generate_gki_certificate.py
EOF

chmod 0755 /usr/libexec/armada/*
chmod 0755 /usr/libexec/os-session-select

test -x /usr/libexec/armada/odin3-audio-setup
test -x /usr/libexec/armada/odin3-audio-default
test -x /usr/libexec/armada/odin3-audio-steam-restore
test -x /usr/libexec/armada/odin3-audio-hotplug
test -f /usr/lib/systemd/system/armada-odin3-audio-setup.service
test -f /usr/lib/systemd/user/armada-odin3-audio-default.service
test -f /usr/lib/systemd/user/armada-odin3-audio-steam-restore.service
test -f /usr/lib/systemd/user/armada-odin3-audio-hotplug.service
test -f /usr/share/armada/audio/odin3/pipewire.conf.d/50-hrir-7_1.conf
test -f /usr/share/armada/audio/odin3/pipewire.conf.d/55-odin3-stereo.conf
test -f /usr/share/armada/audio/odin3/pipewire-pulse.conf.d/10-no-flat.conf
test -f /usr/share/armada/audio/odin3/pipewire-pulse.conf.d/20-odin3-stereo-downmix.conf
test -f /usr/share/armada/audio/odin3/wireplumber.conf.d/51-odin3-audio-names.conf
test -f /usr/share/armada/audio/odin3/wireplumber.conf.d/90-odin3-speaker-route-unity.conf
test -f /usr/share/armada/audio/odin3/hrir/vss_speaker.wav
test "$(
    sha256sum /usr/share/armada/audio/odin3/hrir/vss_speaker.wav |
        cut -d' ' -f1
)" = f88ee26f5af80e73365ea1428cea970eeb383c8dfaa1fb77b0fc5a1efb48a7cb
test -f /usr/share/wireplumber/scripts/odin3-speaker-route-unity.lua

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
systemctl enable armada-odin3-audio-setup.service
systemctl --global enable armada-odin3-audio-default.service
systemctl --global enable armada-odin3-audio-hotplug.service
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
