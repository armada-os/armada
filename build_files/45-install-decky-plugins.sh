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

# Decky Loader runs natively on python3; the upstream x86-64 binary is only a fallback.
# shellcheck source=/dev/null
source /ctx/decky/loader/loader.env
decky_version="${DECKY_LOADER_VERSION}"
decky_repo=SteamDeckHomebrew/decky-loader
decky_backend=/usr/share/decky-loader/backend
decky_service_url="https://raw.githubusercontent.com/${decky_repo}/${decky_version}/dist/plugin_loader-prerelease.service"

[[ "${decky_version}" == v* ]]

install -d -m 0755 "${decky_backend}"
cp -a /packages/decky-loader-backend/. "${decky_backend}/"
for decky_patch in /ctx/decky/loader/*.patch; do
    git -C "${decky_backend}" apply --verbose "${decky_patch}"
done

# aiohttp-jinja2 isn't packaged in Fedora.
aiohttp_jinja2_wheel=/tmp/aiohttp_jinja2-1.6-py3-none-any.whl
curl --retry 12 --retry-delay 10 -fL -o "${aiohttp_jinja2_wheel}" \
    https://files.pythonhosted.org/packages/eb/90/65238d4246307195411b87a07d03539049819b022c01bcc773826f600138/aiohttp_jinja2-1.6-py3-none-any.whl
sha256sum -c - <<<"0df405ee6ad1b58e5a068a105407dc7dcc1704544c559f1938babde954f945c7  ${aiohttp_jinja2_wheel}"
python3 -m zipfile -e "${aiohttp_jinja2_wheel}" "${decky_backend}"
rm -f "${aiohttp_jinja2_wheel}"

# get_loader_version() reads the installed distribution's version.
decky_dist_info="${decky_backend}/decky_loader-${decky_version#v}.dist-info"
decky_dist_info="${decky_dist_info//-pre/_pre}"
install -d -m 0755 "${decky_dist_info}"
printf 'Metadata-Version: 2.1\nName: decky-loader\nVersion: %s\n' "${decky_version#v}" \
    >"${decky_dist_info}/METADATA"
python3 -m compileall -q "${decky_backend}"

install -m 0755 /ctx/decky/loader/PluginLoader /usr/share/decky-loader/PluginLoader
curl --retry 12 --retry-delay 10 -fL -o /usr/share/decky-loader/PluginLoader.x86_64 \
    "https://github.com/${decky_repo}/releases/download/${decky_version}/PluginLoader"
chmod 0755 /usr/share/decky-loader/PluginLoader.x86_64
touch /usr/share/decky-loader/.native
printf '%s\n' "${decky_version}" > /usr/share/decky-loader/.loader.version
decky_service_tmp="$(mktemp)"
curl --retry 12 --retry-delay 10 -fsSL "${decky_service_url}" |
    sed 's#${HOMEBREW_FOLDER}#/var/home/armada/homebrew#g' \
        >"${decky_service_tmp}"
install -D -m 0644 "${decky_service_tmp}" /etc/systemd/system/plugin_loader.service
rm -f "${decky_service_tmp}"

systemctl enable armada-decky-sync.service
systemctl enable plugin_loader.service
