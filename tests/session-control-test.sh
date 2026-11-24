#!/usr/bin/env bash
# The per-boot autologin reset keeps Steam's "Switch to Desktop Mode on startup".
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CONTROL="$ROOT/system_files/usr/libexec/armada/session-control"
UNIT="$ROOT/system_files/usr/lib/systemd/system/armada-session-default.service"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT

mkdir "$tmp/bin" "$tmp/sddm"
printf '#!/usr/bin/env bash\nexit 0\n' >"$tmp/bin/systemctl"
chmod 0755 "$tmp/bin/systemctl"
state="$tmp/state.toml"
conf="$tmp/sddm/zz-holo-autologin.conf"

boot_session() {
    PATH="$tmp/bin:$PATH" \
        ARMADA_STEAMOS_MANAGER_STATE="$state" \
        ARMADA_SDDM_CONF_DIR="$tmp/sddm" \
        ARMADA_PLASMA_SESSION_LIB="$ROOT/system_files/usr/lib/armada/plasma-session-lib" \
        bash "$CONTROL" default-boot
    sed -n 's/^Session=//p' "$conf"
}

expect() {
    local got
    got="$(boot_session)"
    [[ "$got" == "$1" ]] || { printf '%s: expected %s, got %s\n' "$2" "$1" "$got" >&2; exit 1; }
}

expect gamescope-session-steam.desktop "no steamos-manager state"
printf '[session_manager]\ndefault_login_mode = "Game"\ndesktop_session = "armada-plasma.desktop"\n' >"$state"
expect gamescope-session-steam.desktop "game login mode"
printf '[session_manager]\ndefault_login_mode = "Desktop"\ndesktop_session = "armada-plasma.desktop"\n' >"$state"
expect armada-plasma.desktop "desktop login mode"
printf '[session_manager]\ndefault_login_mode = "Desktop"\ndesktop_session = "armada-plasma-mobile.desktop"\n' >"$state"
expect armada-plasma-mobile.desktop "desktop login mode, mobile shell"

: >"$tmp/sddm/zz-steamos-autologin.conf"
boot_session >/dev/null
[[ ! -e "$tmp/sddm/zz-steamos-autologin.conf" ]] || { echo "legacy autologin config kept" >&2; exit 1; }

grep -qx 'ExecStart=/usr/libexec/armada/session-control default-boot' "$UNIT"
echo "session-control tests passed"
