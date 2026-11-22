#!/bin/bash
# Lay out a built Decky plugin as the loader expects it. Used for the image's
# /usr/share/decky-plugins and for remote component payloads.
# usage: install-plugin.sh <plugin> <built dist dir> <dest>
set -euo pipefail

name=$1 dist=$2 dest=$3
src=$(dirname "$(readlink -f "$0")")/$name
install -d -m 0755 "${dest}"
cp -a "${src}/plugin.json" "${src}/package.json" "${src}/main.py" "${dest}/"
cp -a "${src}/py_modules" "${dest}/"
[[ ! -f "${src}/catalog.json" ]] || cp -a "${src}/catalog.json" "${dest}/"
[[ ! -d "${src}/templates" ]] || cp -a "${src}/templates" "${dest}/"
cp -a "${dist}" "${dest}/dist"
rm -f "${dest}/dist/"*.map
find "${dest}" -name __pycache__ -type d -prune -exec rm -rf {} +
