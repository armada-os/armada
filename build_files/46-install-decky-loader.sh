#!/bin/bash
set -euxo pipefail

: "${DECKY_VERSION:?DECKY_VERSION must be resolved before the build}"
: "${DECKY_SHA256:?DECKY_SHA256 must be resolved before the build}"
: "${DECKY_SERVICE_SHA256:?DECKY_SERVICE_SHA256 must be resolved before the build}"

DECKY_URL="https://github.com/SteamDeckHomebrew/decky-loader/releases/download/${DECKY_VERSION}/PluginLoader"
DECKY_SERVICE_URL=https://raw.githubusercontent.com/SteamDeckHomebrew/decky-loader/main/dist/plugin_loader-prerelease.service

install -d -m 0755 /usr/share/decky-loader
curl --retry 12 --retry-delay 10 -fL -o /usr/share/decky-loader/PluginLoader "${DECKY_URL}"
printf '%s  %s\n' "${DECKY_SHA256}" /usr/share/decky-loader/PluginLoader | sha256sum -c -
chmod 0755 /usr/share/decky-loader/PluginLoader
printf '%s\n' "${DECKY_VERSION}" > /usr/share/decky-loader/.loader.version

decky_service_tmp="$(mktemp)"
curl --retry 12 --retry-delay 10 -fsSL -o "${decky_service_tmp}" "${DECKY_SERVICE_URL}"
printf '%s  %s\n' "${DECKY_SERVICE_SHA256}" "${decky_service_tmp}" | sha256sum -c -
sed -i 's#${HOMEBREW_FOLDER}#/var/home/armada/homebrew#g' "${decky_service_tmp}"
install -D -m 0644 "${decky_service_tmp}" /etc/systemd/system/plugin_loader.service
rm -f "${decky_service_tmp}"
