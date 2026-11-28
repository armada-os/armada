#!/bin/bash
set -euxo pipefail

# Copy dist from the image build stage, not the source tree.
./install-decky-plugin.sh /ctx/decky/armada-control /packages/decky-dist \
    /usr/share/decky-plugins/armada-control
./install-decky-plugin.sh /ctx/decky/armada-store /packages/decky-store-dist \
    /usr/share/decky-plugins/armada-store
./install-decky-plugin.sh /ctx/decky/armada-emulation /packages/decky-emulation-dist \
    /usr/share/decky-plugins/armada-emulation
# The Store's catalog is also its offline fallback; never ship an empty Store.
test -f /usr/share/decky-plugins/armada-store/catalog-v1.json
chmod 0755 /usr/lib/decky-loader/armada-decky-sync

decky_release="$(
    curl --retry 12 --retry-delay 10 -fsSL \
        https://api.github.com/repos/SteamDeckHomebrew/decky-loader/releases/latest
)"
decky_version="$(jq -r '.tag_name' <<<"${decky_release}")"
decky_url="$(jq -r '.assets[].browser_download_url | select(endswith("PluginLoader-arm64"))' <<<"${decky_release}")"
decky_service_url=https://raw.githubusercontent.com/SteamDeckHomebrew/decky-loader/main/dist/plugin_loader-release.service

[[ -n "${decky_version}" && "${decky_version}" != "null" ]]
[[ -n "${decky_url}" && "${decky_url}" != "null" ]]

install -d -m 0755 /usr/share/decky-loader
curl --retry 12 --retry-delay 10 -fL -o /usr/share/decky-loader/PluginLoader "${decky_url}"
chmod 0755 /usr/share/decky-loader/PluginLoader
printf '%s\n' "${decky_version}" > /usr/share/decky-loader/.loader.version
decky_service_tmp="$(mktemp)"
curl --retry 12 --retry-delay 10 -fsSL "${decky_service_url}" |
    sed 's#${HOMEBREW_FOLDER}#/var/home/armada/homebrew#g' \
        >"${decky_service_tmp}"
install -D -m 0644 "${decky_service_tmp}" /etc/systemd/system/plugin_loader.service
rm -f "${decky_service_tmp}"

systemctl enable armada-decky-sync.service
systemctl enable plugin_loader.service
