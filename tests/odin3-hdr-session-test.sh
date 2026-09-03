#!/usr/bin/env bash

# HDR advertisement no longer lives in the session file: a nonzero
# ARMADA_HDR_NITS from the device conf (published by device-env) makes
# gamescope-session export the panel device id, and the gamescope lua
# profile supplies the panel capabilities. Steam owns runtime HDR state,
# so nothing may force ENABLE_GAMESCOPE_HDR.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="$ROOT/system_files/usr/share/gamescope-session-plus/sessions.d/steam"
DEVICES="$ROOT/system_files/usr/lib/armada/devices"
DEVICE_ENV="$ROOT/system_files/usr/libexec/armada/device-env"
PANEL_LUA="$ROOT/system_files/usr/share/gamescope/scripts/10-armada/ayn.icna3520.oled.lua"

if grep -Fq 'ENABLE_GAMESCOPE_HDR=' "$SESSION"; then
    printf 'Odin 3 session still force-enables HDR output\n' >&2
    exit 1
fi

for device in ayn-odin-3 ayn-thor; do
    if ! grep -Fxq 'ARMADA_HDR_NITS=650' "$DEVICES/$device.conf"; then
        printf '%s.conf does not advertise ARMADA_HDR_NITS=650\n' "$device" >&2
        exit 1
    fi
done

if ! grep -Fxq 'ARMADA_HDR_NITS=0' "$DEVICES/defaults.conf"; then
    printf 'defaults.conf no longer disables HDR by default\n' >&2
    exit 1
fi

if ! grep -Fq 'ARMADA_HDR_NITS' "$DEVICE_ENV"; then
    printf 'device-env does not publish ARMADA_HDR_NITS\n' >&2
    exit 1
fi

for needle in \
    'display.device_id == "ayn-odin-3"' \
    'display.device_id == "ayn-thor"' \
    'supported = true' \
    'max_content_light_level = 650'; do
    if ! grep -Fq "$needle" "$PANEL_LUA"; then
        printf 'ICNA3520 panel profile missing: %s\n' "$needle" >&2
        exit 1
    fi
done

printf 'Odin 3 HDR session policy test passed\n'
