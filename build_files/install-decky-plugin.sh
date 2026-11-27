#!/bin/bash
# Install a Decky plugin's source and built dist into the image's plugin store.
# Usage: install-decky-plugin.sh <source dir> <dist dir> <destination dir>
set -euo pipefail

src=$1 dist=$2 dest=$3
rm -rf "${dest}"
install -d -m 0755 "${dest}"
cp -a "${src}/plugin.json" "${src}/package.json" "${src}/main.py" "${dest}/"
cp -a "${src}/py_modules" "${dest}/"
[[ ! -f "${src}/catalog.json" ]] || cp -a "${src}/catalog.json" "${dest}/"
[[ ! -d "${src}/templates" ]] || cp -a "${src}/templates" "${dest}/"
cp -a "${dist}" "${dest}/dist"
rm -f "${dest}/dist/"*.map
find "${dest}" -name __pycache__ -type d -prune -exec rm -rf {} +
