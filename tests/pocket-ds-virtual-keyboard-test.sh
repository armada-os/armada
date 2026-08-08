#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
config="$ROOT/system_files/usr/lib/armada/devices/ayaneo-pocket-ds.conf"

grep -q '^ARMADA_VIRTUAL_KEYBOARD_CONNECTOR=DSI-2$' "$config"
printf 'Pocket DS virtual-keyboard connector check passed\n'
