#!/bin/bash
# Install a Decky plugin's source and built dist into the image's plugin store.
# Usage: install-decky-plugin.sh <source dir> <dist dir> <destination dir>
set -euo pipefail

src=$1 dist=$2 dest=$3
rm -rf "${dest}"
install -d -m 0755 "${dest}"
cp -a "${src}/plugin.json" "${src}/package.json" "${src}/main.py" "${dest}/"
cp -a "${src}/py_modules" "${dest}/"
# The shared engine, for plugins that import it.
if grep -rqs armada_apps "${src}/main.py" "${src}/py_modules"; then
    cp -a "${src}/../shared/armada-apps/py_modules/armada_apps" "${dest}/py_modules/"
fi
for catalog in "${src}"/catalog.json "${src}"/catalog-v*.json; do
    [[ ! -f "${catalog}" ]] || cp -a "${catalog}" "${dest}/"
done
[[ ! -d "${src}/icons" ]] || cp -a "${src}/icons" "${dest}/"
[[ ! -d "${src}/templates" ]] || cp -a "${src}/templates" "${dest}/"
cp -a "${dist}" "${dest}/dist"
rm -f "${dest}/dist/"*.map
find "${dest}" -name __pycache__ -type d -prune -exec rm -rf {} +
