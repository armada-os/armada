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
require "$units/armada-hud-top.service" 'top HUD cannot outlive a failed gaming session' 'BindsTo=armada-nested-gaming.service'
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
require "$units/armada-hud-bottom.service" 'HUD swap is ordered stop-before-start' 'After=armada-hud-top.service'
require "$units/armada-hud-bottom.service" 'bottom HUD dies with gaming mode' 'PartOf=armada-nested-gaming.service'
require "$units/armada-hud-bottom.service" 'bottom HUD cannot outlive a failed gaming session' 'BindsTo=armada-nested-gaming.service'
require "$units/armada-hud-bottom.service" 'bottom HUD starts only after gaming mode is active' 'After=armada-nested-gaming.service'
require "$units/armada-hud-bottom.service" 'bottom HUD is supervised' 'Restart=always'
require "$libexec/hud-bottom" 'bottom HUD needs the desktop display' '[[ -n ${DISPLAY:-} ]] || exit 1'
require "$libexec/hud-bottom" 'bottom HUD avoids the host compositor' 'unset WAYLAND_DISPLAY'
require "$libexec/hud-bottom" 'bottom HUD uses the static config' 'MANGOHUD_CONFIGFILE=/usr/share/armada/mangohud-bottom.conf'
require "$libexec/hud-bottom" 'bottom HUD runs mangoapp' 'exec mangoapp'
require "${sf}/usr/share/armada/mangohud-bottom.conf" 'bottom HUD shows fps' 'fps'
require "${sf}/usr/share/armada/mangohud-bottom.conf" 'bottom HUD shows the frametime graph' 'frame_timing'
require "${sf}/usr/share/armada/mangohud-bottom.conf" 'bottom HUD shows VRAM usage' 'vram'
forbid "${sf}/usr/share/armada/mangohud-bottom.conf" 'bottom HUD must never start hidden' 'no_display'
require "${sf}/etc/xdg/kwinrulesrc" 'HUD window rule is registered' 'rules=steam-keyboard,armada-hud-bottom'
require "${sf}/etc/xdg/kwinrulesrc" 'HUD window matches the live MangoApp class' 'wmclass=mangoapp overlay window'
require "${sf}/etc/xdg/kwinrulesrc" 'HUD window is pinned to the bottom output index' 'screen=0'
require "${sf}/etc/xdg/kwinrulesrc" 'HUD output placement is forced' 'screenrule=4'
require "${sf}/etc/xdg/kwinrulesrc" 'HUD placement is seeded inside DSI-1' 'position=226,720'
require "${sf}/etc/xdg/kwinrulesrc" 'HUD placement seed is forced' 'positionrule=4'
require "${sf}/etc/xdg/kwinrulesrc" 'HUD window is forced fullscreen' 'fullscreenrule=4'
require "${sf}/etc/xdg/kwinrulesrc" 'HUD window cannot accept focus' 'acceptfocus=false'
require "${sf}/etc/xdg/kwinrulesrc" 'HUD focus rejection is forced' 'acceptfocusrule=2'

# KWin deliberately does not load rules from the global config search path, so
# vendor rules must be merged into the user's rulebook without deleting custom
# rules. Exercise the merge through explicit fixture paths.
kwin_rules_installer="${libexec}/install-kwin-rules"
require "$libexec/desktop-bootstrap" 'vendor KWin rules are installed before gaming starts' '/usr/libexec/armada/install-kwin-rules'
require "$libexec/desktop-bootstrap" 'KWin reloads the merged rules' 'org.kde.KWin.reconfigure'

kwin_rules_tmp=$(mktemp -d)
trap 'rm -rf -- "$kwin_rules_tmp"' EXIT
cat >"${kwin_rules_tmp}/user-rules" <<'EOF'
[General]
count=2
rules=my-custom-rule,armada-hud-bottom

[my-custom-rule]
description=Keep me
wmclass=custom-app

[armada-hud-bottom]
description=Stale vendor rule
wmclass=stale-class
EOF

ARMADA_KWIN_RULES_VENDOR="${sf}/etc/xdg/kwinrulesrc" \
    ARMADA_KWIN_RULES_TARGET="${kwin_rules_tmp}/user-rules" \
    "$kwin_rules_installer"
require "${kwin_rules_tmp}/user-rules" 'custom KWin rules survive the vendor merge' '[my-custom-rule]'
require "${kwin_rules_tmp}/user-rules" 'custom KWin rule data survives the vendor merge' 'wmclass=custom-app'
require "${kwin_rules_tmp}/user-rules" 'HUD rule is installed in the user rulebook' '[armada-hud-bottom]'
forbid "${kwin_rules_tmp}/user-rules" 'stale vendor rule data is replaced' 'wmclass=stale-class'
require "${kwin_rules_tmp}/user-rules" 'merged rule index retains custom and vendor rules' 'rules=my-custom-rule,steam-keyboard,armada-hud-bottom'
require "${kwin_rules_tmp}/user-rules" 'merged rule count is updated' 'count=3'

# A second login must not duplicate rule names or rule sections.
ARMADA_KWIN_RULES_VENDOR="${sf}/etc/xdg/kwinrulesrc" \
    ARMADA_KWIN_RULES_TARGET="${kwin_rules_tmp}/user-rules" \
    "$kwin_rules_installer"
[[ $(grep -Fc 'armada-hud-bottom' "${kwin_rules_tmp}/user-rules") -eq 2 ]] || {
    printf 'violated HUD-toggle contract (user-rules): vendor merge is not idempotent\n' >&2
    exit 1
}

# --- toggle action ---
bash -n "$libexec/hud-toggle"
require "$libexec/hud-toggle" 'toggle is gated on gaming mode' 'is-active armada-nested-gaming.service || exit 0'
require "$libexec/hud-toggle" 'bottom toggles back to top' 'unit=armada-hud-top.service'
require "$libexec/hud-toggle" 'anything else lands on bottom' 'unit=armada-hud-bottom.service'

# --- button listener ---
bash -n "$libexec/hud-toggle-listener"
require "$libexec/hud-toggle-listener" 'listener is inert without a configured button' '[[ -n ${ARMADA_HUD_TOGGLE_BUTTON_DEV:-} && -n ${ARMADA_HUD_TOGGLE_BUTTON_KEY:-} ]] || exit 0'
require "$libexec/hud-toggle-listener" 'listener reads the device by stable path' '/dev/input/by-path/${ARMADA_HUD_TOGGLE_BUTTON_DEV}'
require "$libexec/hud-toggle-listener" 'evtest output is line-buffered' 'stdbuf -oL evtest'
require "$libexec/hud-toggle-listener" 'a press runs the toggle' '/usr/libexec/armada/hud-toggle || true'
require "$units/armada-ayn-button.service" 'listener lives with the session' 'PartOf=graphical-session.target'
require "$units/armada-ayn-button.service" 'clean no-button exit is final' 'Restart=on-failure'
require "$libexec/desktop-bootstrap" 'listener is started at desktop login' 'systemctl --user start armada-ayn-button.service'
