#!/bin/bash
set -euxo pipefail

# Copy dist from the image build stage, not the source tree.
install_plugin() {
    local name=$1 dist=$2 src=/ctx/decky/$1 dest=/usr/share/decky-plugins/$1
    install -d -m 0755 "${dest}"
    cp -a "${src}/plugin.json" "${src}/package.json" "${src}/main.py" "${dest}/"
    cp -a "${src}/py_modules" "${dest}/"
    [[ ! -f "${src}/catalog.json" ]] || cp -a "${src}/catalog.json" "${dest}/"
    [[ ! -d "${src}/templates" ]] || cp -a "${src}/templates" "${dest}/"
    cp -a "${dist}" "${dest}/dist"
    rm -f "${dest}/dist/"*.map
    find "${dest}" -name __pycache__ -type d -prune -exec rm -rf {} +
}
install_plugin armada-control /packages/decky-dist
install_plugin armada-store /packages/decky-store-dist
chmod 0755 /usr/lib/decky-loader/armada-decky-sync

decky_release="$(
    curl --retry 12 --retry-delay 10 -fsSL \
        https://api.github.com/repos/SteamDeckHomebrew/decky-loader/releases |
        jq -r 'first(.[])'
)"
decky_version="$(jq -r '.tag_name' <<<"${decky_release}")"
decky_url="$(jq -r '.assets[].browser_download_url | select(endswith("PluginLoader"))' <<<"${decky_release}")"
decky_service_url=https://raw.githubusercontent.com/SteamDeckHomebrew/decky-loader/main/dist/plugin_loader-prerelease.service

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
