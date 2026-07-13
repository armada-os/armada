#!/usr/bin/bash
# Contract tests for the AYN-button HUD toggle (see
# docs/superpowers/specs/2026-07-12-ayn-button-hud-toggle-design.md).
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
sf="${repo_root}/system_files"
devices="${sf}/usr/lib/armada/devices"
libexec="${sf}/usr/libexec/armada"
units="${sf}/usr/lib/systemd/user"

require() {
    local file=$1 contract=$2 literal=$3
    grep -Fq -- "$literal" "$file" || {
        printf 'missing HUD-toggle contract (%s): %s\n' "${file##*/}" "$contract" >&2
        exit 1
    }
}

# --- device configuration ---
require "$devices/defaults.conf" 'button device has a documented default' 'ARMADA_HUD_TOGGLE_BUTTON_DEV='
require "$devices/defaults.conf" 'button key has a documented default' 'ARMADA_HUD_TOGGLE_BUTTON_KEY='
require "$devices/ayn-thor.conf" 'Thor names the AYN button device' 'ARMADA_HUD_TOGGLE_BUTTON_DEV=platform-gpio-keys-event'
require "$devices/ayn-thor.conf" 'Thor names the AYN button key' 'ARMADA_HUD_TOGGLE_BUTTON_KEY=KEY_F24'
require "$libexec/device-env" 'device-env exports the button device' 'ARMADA_HUD_TOGGLE_BUTTON_DEV'
require "$libexec/device-env" 'device-env exports the button key' 'ARMADA_HUD_TOGGLE_BUTTON_KEY'

# --- top HUD unit (Steam-controlled overlay inside nested gamescope) ---
bash -n "$libexec/hud-top"
require "$units/armada-hud-top.service" 'top HUD conflicts with the bottom HUD' 'Conflicts=armada-hud-bottom.service'
require "$units/armada-hud-top.service" 'top HUD dies with gaming mode' 'PartOf=armada-nested-gaming.service'
require "$units/armada-hud-top.service" 'top HUD is supervised' 'Restart=always'
require "$units/armada-hud-top.service" 'top HUD retries forever like the old loop' 'StartLimitIntervalSec=0'
require "$libexec/hud-top" 'top HUD reads the session env file' 'armada-nested-gaming.env'
require "$libexec/hud-top" 'top HUD refuses to run without the nested display' '[[ -n ${DISPLAY:-} && -n ${MANGOHUD_CONFIGFILE:-} ]] || exit 1'
require "$libexec/hud-top" 'top HUD avoids the host compositor' 'unset WAYLAND_DISPLAY'
require "$libexec/hud-top" 'top HUD runs mangoapp' 'exec mangoapp'
