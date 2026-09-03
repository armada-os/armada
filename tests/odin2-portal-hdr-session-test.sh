#!/usr/bin/env bash

# Odin 2 Portal's ICNA3512 panel is a distinct DDIC from Odin 3/Thor's ICNA3520
# (incompatible vendor MIPI commands), so it gets its own gamescope Lua panel
# profile rather than reusing/joining the ICNA3520 one. Steam still owns
# runtime HDR state, so nothing may force ENABLE_GAMESCOPE_HDR.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="$ROOT/system_files/usr/share/gamescope-session-plus/sessions.d/steam"
DEVICES="$ROOT/system_files/usr/lib/armada/devices"
DEVICE_ENV="$ROOT/system_files/usr/libexec/armada/device-env"
PANEL_LUA_ICNA3520="$ROOT/system_files/usr/share/gamescope/scripts/10-armada/ayn.icna3520.oled.lua"
PANEL_LUA_ICNA3512="$ROOT/system_files/usr/share/gamescope/scripts/10-armada/ayn.icna3512.oled.lua"

if grep -Fq 'ENABLE_GAMESCOPE_HDR=' "$SESSION"; then
    printf 'Odin 2 Portal session still force-enables HDR output\n' >&2
    exit 1
fi

if ! grep -Fxq 'ARMADA_HDR_NITS=800' "$DEVICES/ayn-odin-2-portal.conf"; then
    printf 'ayn-odin-2-portal.conf does not advertise ARMADA_HDR_NITS=800\n' >&2
    exit 1
fi

if ! grep -Fxq 'ARMADA_HDR_NITS=0' "$DEVICES/defaults.conf"; then
    printf 'defaults.conf no longer disables HDR by default\n' >&2
    exit 1
fi

if ! grep -Fq 'ARMADA_HDR_NITS' "$DEVICE_ENV"; then
    printf 'device-env does not publish ARMADA_HDR_NITS\n' >&2
    exit 1
fi

if grep -Fq 'ayn-odin-2-portal' "$PANEL_LUA_ICNA3520"; then
    printf 'ICNA3520 panel profile unexpectedly claims ayn-odin-2-portal\n' >&2
    exit 1
fi

for needle in \
    'display.device_id == "ayn-odin-2-portal"' \
    'supported = true' \
    'max_content_light_level = 800'; do
    if ! grep -Fq "$needle" "$PANEL_LUA_ICNA3512"; then
        printf 'ICNA3512 panel profile missing: %s\n' "$needle" >&2
        exit 1
    fi
done

printf 'Odin 2 Portal HDR session policy test passed\n'
