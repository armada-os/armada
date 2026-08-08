#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

pocket_ds_conf="$ROOT/system_files/usr/lib/armada/devices/ayaneo-pocket-ds.conf"
setup_dual="$ROOT/system_files/usr/libexec/armada/setup-dual-screen"
session_control="$ROOT/system_files/usr/libexec/armada/session-control"
device_env="$ROOT/system_files/usr/libexec/armada/device-env"

# Pocket DS advertises the lower panel to desktop-bootstrap, while gamescope
# still targets the primary connector through sessions.d/steam.
grep -q '^ARMADA_PRIMARY_CONNECTOR=DSI-1$' "$pocket_ds_conf"
grep -q '^ARMADA_SECONDARY_CONNECTOR=DSI-2$' "$pocket_ds_conf"
grep -q '^ARMADA_PANEL_ORIENTATION=left$' "$pocket_ds_conf"
grep -q "^ARMADA_PRIMARY_TOUCHSCREEN='generic ft5x06 (44)'$" "$pocket_ds_conf"
grep -q "^ARMADA_SECONDARY_TOUCHSCREEN='Goodix Capacitive TouchScreen'$" "$pocket_ds_conf"
grep -q 'ARMADA_SECONDARY_CONNECTOR' "$device_env"
grep -q 'ARMADA_PRIMARY_TOUCHSCREEN' "$device_env"
grep -q 'ARMADA_SECONDARY_TOUCHSCREEN' "$device_env"
grep -q 'ARMADA_PRIMARY_BACKLIGHT' "$device_env"

# Desktop setup must actively re-enable the second output, not just position it.
grep -q 'f"output.{primary}.enable"' "$setup_dual"
grep -q 'f"output.{secondary}.enable"' "$setup_dual"
grep -q 'f"output.{primary}.rotation.{orientation}"' "$setup_dual"
grep -q 'f"output.{secondary}.rotation.{orientation}"' "$setup_dual"
grep -q 'dual_required=1' "$ROOT/system_files/usr/libexec/armada/desktop-bootstrap"
grep -q 'elif /usr/libexec/armada/setup-dual-screen; then' "$ROOT/system_files/usr/libexec/armada/desktop-bootstrap"

# Switching back to game mode should explicitly disable the secondary output
# and inhibit lower touch before leaving Plasma, so Game Mode cannot scan out
# to the lower panel and the lower digitizer cannot steer Steam during handoff.
# Pocket DS live testing showed the visible lower backlight can remain lit even
# with DSI-2 disabled/DPMS Off; that requires a separate kernel/panel power fix
# and is not something this userspace policy test should overclaim.
grep -q 'set_secondary_touchscreen 1' "$session_control"
grep -q 'set_secondary_output disable' "$session_control"
grep -q 'touchscreen-inhibit "${ARMADA_SECONDARY_TOUCHSCREEN}" "${inhibited}"' "$session_control"
grep -q 'kscreen-doctor "output.${ARMADA_SECONDARY_CONNECTOR}.${state}"' "$session_control"

# Game Mode must never enable or lay out the secondary panel. It may only
# inhibit the secondary touchscreen as a belt-and-suspenders guard; screen and
# backlight availability is Desktop-only via desktop-bootstrap/setup-dual-screen.
grep -q 'sudo -n /usr/libexec/armada/touchscreen-inhibit "$ARMADA_SECONDARY_TOUCHSCREEN" 1' "$ROOT/system_files/etc/gamescope-session-plus/sessions.d/steam"
! grep -q 'ARMADA_SECONDARY_CONNECTOR' "$ROOT/system_files/etc/gamescope-session-plus/sessions.d/steam"
! grep -q 'setup-dual-screen' "$ROOT/system_files/etc/gamescope-session-plus/sessions.d/steam"

grep -q 'sudo -n /usr/libexec/armada/touchscreen-inhibit "$ARMADA_SECONDARY_TOUCHSCREEN" 0' "$ROOT/system_files/usr/libexec/armada/desktop-bootstrap"
grep -q 'NOPASSWD: /usr/libexec/armada/touchscreen-inhibit \*' "$ROOT/build_files/50-create-user.sh"

python3 -m py_compile "$setup_dual"
bash -n "$session_control"

printf 'Pocket DS desktop-only dual-screen checks passed\n'
