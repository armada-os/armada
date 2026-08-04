#!/bin/bash
set -euxo pipefail

cp -a /ctx/system_files/. /
install -Dpm 0755 /packages/extest/libextest.so /usr/lib/extest/libextest.so

cp -a /packages/mesa-android/waydroid/vendor /usr/share/armada/waydroid/

# Status text font for armada-splash (falls back to its embedded bitmap font
# if this link dangles).
splash_font="$(rpm -ql google-noto-sans-vf-fonts | grep -m1 '\.ttf$')"
[ -n "${splash_font}" ]
ln -sf "${splash_font}" /usr/share/armada/splash/font.ttf

# mkbootimg must be present for on-device /KERNEL rebuilds after OTA.
install -Dpm 0755 /ctx/build_files/vendor/mkbootimg/mkbootimg.py /usr/libexec/armada/mkbootimg.py
install -Dpm 0755 /ctx/build_files/vendor/mkbootimg/gki/generate_gki_certificate.py /usr/libexec/armada/gki/generate_gki_certificate.py
sha256sum -c <<'EOF'
37d84b3d162e0bc62e36c1f4e1c63c85ea0caa9f29be023eb2f8efe006ad948c  /usr/libexec/armada/mkbootimg.py
1bb1feec68a13da18d581aa2c631798f86f6bc10b55d587b2dd31446a0f8a203  /usr/libexec/armada/gki/generate_gki_certificate.py
EOF

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
systemctl enable armada-touchscreen-trackpad.service
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
systemctl enable armada-splash-stall.service
systemctl enable armada-splash-early.service
systemctl enable armada-splash-reboot-screen.service
systemctl enable armada-splash-poweroff-screen.service

# logind's "reboot implies set-wall-message" annotation lets Steam re-enable
# the reboot wall past the deny rule; the pre-check fails loud on a reformat.
login1_policy=/usr/share/polkit-1/actions/org.freedesktop.login1.policy
if ! grep -q 'imply.*set-wall-message' "${login1_policy}"; then
    echo "ERROR: expected set-wall-message imply annotation not found in ${login1_policy}"
    exit 1
fi
sed -i '/imply.*set-wall-message/d' "${login1_policy}"

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

# systemd-backlight restores a stale (often near-dark) level mid-boot, fighting
# the splash's fixed 50% default; Steam persists the user's brightness itself.
systemctl mask systemd-backlight@.service
