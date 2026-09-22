#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CONTROL="$ROOT/system_files/usr/libexec/armada/session-control"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
BIN="$WORK/bin"
mkdir -p "$BIN"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

cat > "$BIN/systemctl" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$SYSTEMCTL_LOG"
if [[ "$*" == "${FAIL_SYSTEMCTL:-}" ]]; then
    exit 23
fi
STUB
chmod 0755 "$BIN/systemctl"
cat > "$BIN/install" <<'STUB'
#!/usr/bin/env bash
for destination; do :; done
mkdir -p "$destination"
STUB
chmod 0755 "$BIN/install"

run_recovery() {
    local case_root="$1"
    local fail_systemctl="${2:-}"
    local mode="${3:-recover-desktop}"
    mkdir -p "$case_root/etc/armada" "$case_root/etc/sddm.conf.d" "$case_root/var/lib/armada"
    touch "$case_root/var/lib/armada/boot-desktop-once"
    : > "$case_root/systemctl.log"
    : > "$case_root/events.log"

    PATH="$BIN:$PATH" \
    SYSTEMCTL_LOG="$case_root/systemctl.log" \
    FAIL_SYSTEMCTL="$fail_systemctl" \
    TEST_EVENTS="$case_root/events.log" \
        bash -c '
            source "$1"
            test_root="$2"
            DESKTOP_SESSION_CONFIG="$test_root/etc/armada/desktop-session"
            SDDM_CONFIG="$test_root/etc/sddm.conf.d/zz-steamos-autologin.conf"
            RECOVER_OVERRIDE_DIR="$test_root/etc/systemd/system/armada-session-default.service.d"
            RECOVER_OVERRIDE="$RECOVER_OVERRIDE_DIR/recover-desktop.conf"
            RECOVER_OVERRIDE_REMOVE_PATH="$RECOVER_OVERRIDE"
            LEGACY_RECOVERY_MARKER="$test_root/var/lib/armada/boot-desktop-once"
            initialize_plasma_configs() { printf "%s\n" initialize >> "$TEST_EVENTS"; }
            activate_plasma_config() { printf "activate %s\n" "$1" >> "$TEST_EVENTS"; }
            session_control_main "$3"
        ' bash "$CONTROL" "$case_root" "$mode"
}

success="$WORK/success"
run_recovery "$success"
override="$success/etc/systemd/system/armada-session-default.service.d/recover-desktop.conf"
[[ -f "$override" ]] || fail "recovery override was not created"
cat > "$success/expected-override" <<EOF
[Service]
ExecStart=
ExecStart=/usr/libexec/armada/session-control default-desktop
ExecStartPost=-/usr/bin/rm -f $override
EOF
cmp -s "$success/expected-override" "$override" \
    || fail "recovery override does not select and clean up the one-boot Desktop session"
[[ "$(find "${override%/*}" -type f | wc -l | tr -d ' ')" == 1 ]] \
    || fail "atomic override write left a temporary file"
printf '[Autologin]\nSession=armada-plasma.desktop\n' > "$success/expected-sddm"
cmp -s "$success/expected-sddm" "$success/etc/sddm.conf.d/zz-steamos-autologin.conf" \
    || fail "Desktop autologin was not selected"
[[ ! -e "$success/var/lib/armada/boot-desktop-once" ]] \
    || fail "legacy recovery marker was not removed"
printf 'initialize\nactivate desktop\n' > "$success/expected-events"
cmp -s "$success/expected-events" "$success/events.log" \
    || fail "Desktop Plasma configuration was not activated"
printf 'daemon-reload\nreset-failed sddm.service\n--no-block reboot\n' > "$success/expected-systemctl"
cmp -s "$success/expected-systemctl" "$success/systemctl.log" \
    || fail "recovery did not reload systemd and reboot in order"

reload_failure="$WORK/reload-failure"
set +e
run_recovery "$reload_failure" daemon-reload
reload_status=$?
set -e
[[ "$reload_status" == 23 ]] || fail "daemon-reload failure was not propagated"
[[ ! -e "$reload_failure/etc/sddm.conf.d/zz-steamos-autologin.conf" ]] \
    || fail "autologin changed after daemon-reload failed"
! grep -Fq -- '--no-block reboot' "$reload_failure/systemctl.log" \
    || fail "reboot was requested after daemon-reload failed"

reboot_failure="$WORK/reboot-failure"
set +e
run_recovery "$reboot_failure" '--no-block reboot'
reboot_status=$?
set -e
[[ "$reboot_status" == 23 ]] || fail "reboot failure was not propagated"
printf '[Autologin]\nSession=gamescope-session-steam.desktop\n' > "$reboot_failure/expected-sddm"
cmp -s "$reboot_failure/expected-sddm" "$reboot_failure/etc/sddm.conf.d/zz-steamos-autologin.conf" \
    || fail "failed reboot did not keep the current boot in Gaming Mode"
[[ -f "$reboot_failure/etc/systemd/system/armada-session-default.service.d/recover-desktop.conf" ]] \
    || fail "failed reboot discarded the next-boot Desktop override"
! grep -Fq -- '--no-block restart sddm.service' "$reboot_failure/systemctl.log" \
    || fail "reboot failure fell through to the unsafe live compositor handoff"

default_game="$WORK/default-game"
run_recovery "$default_game" '' default-gamemode
printf '[Autologin]\nSession=gamescope-session-steam.desktop\n' > "$default_game/expected-sddm"
cmp -s "$default_game/expected-sddm" "$default_game/etc/sddm.conf.d/zz-steamos-autologin.conf" \
    || fail "default Gaming Mode behavior changed during recovery refactor"
printf 'reset-failed sddm.service\n' > "$default_game/expected-systemctl"
cmp -s "$default_game/expected-systemctl" "$default_game/systemctl.log" \
    || fail "default Gaming Mode unexpectedly restarted the display manager"

mobile_desktop="$WORK/mobile-desktop"
mkdir -p "$mobile_desktop/etc/armada"
printf 'mobile\n' > "$mobile_desktop/etc/armada/desktop-session"
run_recovery "$mobile_desktop" '' default-desktop
printf '[Autologin]\nSession=armada-plasma-mobile.desktop\n' > "$mobile_desktop/expected-sddm"
cmp -s "$mobile_desktop/expected-sddm" "$mobile_desktop/etc/sddm.conf.d/zz-steamos-autologin.conf" \
    || fail "default Desktop Mode no longer honors the mobile Plasma selection"
printf 'initialize\nactivate mobile\n' > "$mobile_desktop/expected-events"
cmp -s "$mobile_desktop/expected-events" "$mobile_desktop/events.log" \
    || fail "mobile Plasma configuration was not activated"

printf 'Session control recovery test passed\n'
