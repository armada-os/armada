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

forbid() {
    local file=$1 contract=$2 literal=$3
    ! grep -Fq -- "$literal" "$file" || {
        printf 'violated HUD-toggle contract (%s): %s\n' "${file##*/}" "$contract" >&2
        exit 1
    }
}

# --- bottom HUD unit (full stats on the desktop's bottom screen) ---
bash -n "$libexec/hud-bottom"
require "$units/armada-hud-bottom.service" 'bottom HUD conflicts with the top HUD' 'Conflicts=armada-hud-top.service'
require "$units/armada-hud-bottom.service" 'bottom HUD dies with gaming mode' 'PartOf=armada-nested-gaming.service'
require "$units/armada-hud-bottom.service" 'bottom HUD is supervised' 'Restart=always'
require "$libexec/hud-bottom" 'bottom HUD needs the desktop display' '[[ -n ${DISPLAY:-} ]] || exit 1'
require "$libexec/hud-bottom" 'bottom HUD avoids the host compositor' 'unset WAYLAND_DISPLAY'
require "$libexec/hud-bottom" 'bottom HUD uses the static config' 'MANGOHUD_CONFIGFILE=/usr/share/armada/mangohud-bottom.conf'
require "$libexec/hud-bottom" 'bottom HUD runs mangoapp' 'exec mangoapp'
require "${sf}/usr/share/armada/mangohud-bottom.conf" 'bottom HUD shows fps' 'fps'
require "${sf}/usr/share/armada/mangohud-bottom.conf" 'bottom HUD shows the frametime graph' 'frame_timing'
forbid "${sf}/usr/share/armada/mangohud-bottom.conf" 'bottom HUD must never start hidden' 'no_display'
require "${sf}/etc/xdg/kwinrulesrc" 'HUD window rule is registered' 'rules=steam-keyboard,armada-hud-bottom'
require "${sf}/etc/xdg/kwinrulesrc" 'HUD window is matched by class' 'wmclass=mangoapp'
require "${sf}/etc/xdg/kwinrulesrc" 'HUD window is forced fullscreen' 'fullscreenrule=2'

# --- toggle action ---
bash -n "$libexec/hud-toggle"
require "$libexec/hud-toggle" 'toggle is gated on gaming mode' 'is-active armada-nested-gaming.service || exit 0'
require "$libexec/hud-toggle" 'bottom toggles back to top' 'unit=armada-hud-top.service'
require "$libexec/hud-toggle" 'anything else lands on bottom' 'unit=armada-hud-bottom.service'
