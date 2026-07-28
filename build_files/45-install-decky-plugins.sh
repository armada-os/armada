#!/bin/bash
set -euxo pipefail

install -d -m 0755 /usr/share/decky-plugins/armada-control
# Copy dist from the image build stage, not the source tree.
src=/ctx/decky/armada-control
cp -a "${src}/plugin.json" "${src}/package.json" "${src}/main.py" /usr/share/decky-plugins/armada-control/
cp -a "${src}/py_modules" /usr/share/decky-plugins/armada-control/
cp -a /packages/decky-dist /usr/share/decky-plugins/armada-control/dist
rm -f /usr/share/decky-plugins/armada-control/dist/*.map
find /usr/share/decky-plugins/armada-control -name __pycache__ -type d -prune -exec rm -rf {} +
chmod 0755 /usr/lib/decky-loader/armada-decky-sync

lsfg_version=0.12.5
lsfg_url=https://github.com/xXJSONDeruloXx/decky-lsfg-vk/releases/download/v${lsfg_version}/Decky.LSFG-VK.zip
lsfg_sha256=13b8c8de5744a4fcf300e85971cb0c110f0734cb2db508c8de6309bbf8298a07
lsfg_archive="$(mktemp)"
lsfg_extract="$(mktemp -d)"

curl --retry 3 --retry-delay 2 -fL -o "${lsfg_archive}" "${lsfg_url}"
printf '%s  %s\n' "${lsfg_sha256}" "${lsfg_archive}" | sha256sum -c -
unzip -q "${lsfg_archive}" -d "${lsfg_extract}"

lsfg_src="${lsfg_extract}/Decky LSFG-VK"
patch --directory="${lsfg_src}" --strip=1 \
    < /ctx/decky/decky-lsfg-vk/patches/0001-Adapt-Decky-LSFG-VK-for-Armada.patch
sed -i 's/Decky LSFG-VK/Decky LSFG-VK (Armada)/g' "${lsfg_src}/dist/index.js"
install -d -m 0755 /usr/share/decky-plugins/decky-lsfg-vk
cp -a "${lsfg_src}/." /usr/share/decky-plugins/decky-lsfg-vk/
install -m 0755 /packages/lsfg-vk/liblsfg-vk.so \
    /usr/share/decky-plugins/decky-lsfg-vk/bin/liblsfg-vk-arm64.so
rm -rf "${lsfg_extract}"
rm -f "${lsfg_archive}"

decky_release="$(
    curl --retry 3 --retry-delay 2 -fsSL \
        https://api.github.com/repos/SteamDeckHomebrew/decky-loader/releases |
        jq -r 'first(.[])'
)"
decky_version="$(jq -r '.tag_name' <<<"${decky_release}")"
decky_url="$(jq -r '.assets[].browser_download_url | select(endswith("PluginLoader"))' <<<"${decky_release}")"
decky_service_url=https://raw.githubusercontent.com/SteamDeckHomebrew/decky-loader/main/dist/plugin_loader-prerelease.service

[[ -n "${decky_version}" && "${decky_version}" != "null" ]]
[[ -n "${decky_url}" && "${decky_url}" != "null" ]]

install -d -m 0755 /usr/share/decky-loader
curl --retry 3 --retry-delay 2 -fL -o /usr/share/decky-loader/PluginLoader "${decky_url}"
chmod 0755 /usr/share/decky-loader/PluginLoader
printf '%s\n' "${decky_version}" > /usr/share/decky-loader/.loader.version
decky_service_tmp="$(mktemp)"
curl --retry 3 --retry-delay 2 -fsSL "${decky_service_url}" |
    sed 's#${HOMEBREW_FOLDER}#/var/home/armada/homebrew#g' \
        >"${decky_service_tmp}"
install -D -m 0644 "${decky_service_tmp}" /etc/systemd/system/plugin_loader.service
rm -f "${decky_service_tmp}"

systemctl enable armada-decky-sync.service
systemctl enable plugin_loader.service
