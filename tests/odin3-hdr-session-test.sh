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

POCKET_DS_LUA="$ROOT/system_files/usr/share/gamescope/scripts/10-armada/ayaneo.pocket-ds.oled.lua"
SHARED_3512_LUA="$ROOT/system_files/usr/share/gamescope/scripts/10-armada/ayn.icna3512.oled.lua"

if ! grep -Fxq 'ARMADA_HDR_NITS=786' "$DEVICES/ayaneo-pocket-ds.conf"; then
    printf 'ayaneo-pocket-ds.conf does not advertise ARMADA_HDR_NITS=786\n' >&2
    exit 1
fi

for needle in \
    'display.device_id == "ayaneo-pocket-ds"' \
    'supported = true' \
    'max_content_light_level = 786' \
    'max_frame_average_luminance = 393'; do
    if ! grep -Fq "$needle" "$POCKET_DS_LUA"; then
        printf 'Pocket DS panel profile missing: %s\n' "$needle" >&2
        exit 1
    fi
done

# Two profiles scoring the same would make the match order-dependent.
if grep -Fq '"ayaneo-pocket-ds"' "$SHARED_3512_LUA"; then
    printf 'shared ICNA3512 profile still matches the Pocket DS\n' >&2
    exit 1
fi

printf 'Odin 3 HDR session policy test passed\n'
