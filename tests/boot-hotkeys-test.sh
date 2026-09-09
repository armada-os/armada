#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOTKEYS="$ROOT/system_files/usr/libexec/armada/armada-boot-hotkeys"
UNIT="$ROOT/system_files/usr/lib/systemd/system/armada-boot-hotkeys.service"
INPUT_LIB="$ROOT/system_files/usr/lib/armada/input-lib"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_file() { [[ -e "$1" ]] || fail "$2: expected $1 to exist"; }
assert_grep() { grep -qF -- "$2" "$1" || fail "$3: expected ${2@Q} in $1"; }
assert_no_grep() { [[ -e "$1" ]] && grep -qF -- "$2" "$1" && fail "$3: unexpected ${2@Q} in $1"; return 0; }

BIN="$WORK/bin"; DEV="$WORK/dev"; SYS="$WORK/sys"
mkdir -p "$BIN" "$DEV" "$SYS"
export WORK

# event0 has no EV_KEY bitmap at all, event1 carries BTN_SELECT (314), and
# event2 carries the neighbouring BTN_START (315): only event1 may be polled.
for n in 0 1 2; do : > "$DEV/event$n"; mkdir -p "$SYS/event$n/device/capabilities"; done
printf '0\n' > "$SYS/event0/device/capabilities/key"
printf '400000000000000 0 0 0 0\n' > "$SYS/event1/device/capabilities/key"
printf '800000000000000 0 0 0 0\n' > "$SYS/event2/device/capabilities/key"

cat > "$BIN/evtest" <<'STUB'
#!/usr/bin/env bash
dev="${@: -3:1}"
printf '%s\n' "$dev" >> "$WORK/queried"
[[ -e "$WORK/pressed" ]] || exit 0
[[ -r "$WORK/pressed-dev" ]] || exit 10
[[ "$dev" == "$(cat "$WORK/pressed-dev")" ]] && exit 10
exit 0
STUB
cat > "$BIN/systemctl" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$WORK/systemctl.log"
[[ "$1" == start ]] && exit 0
[[ "$1" == is-failed ]] && { [[ -e "$WORK/dm-failed" ]] && exit 0; exit 1; }
[[ " $* " == *" display-manager.service "* && -e "$WORK/dm-active" ]] && exit 0
exit 3
STUB
cat > "$BIN/logger" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "${@: -1}" >> "$WORK/log"
STUB
cat > "$WORK/progress" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$WORK/status.log"
STUB
cat > "$WORK/session-control" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$WORK/session.log"
STUB
chmod 0755 "$BIN"/* "$WORK/session-control" "$WORK/progress"

run_hotkeys() {
    rm -f "$WORK/queried" "$WORK/log" "$WORK/session.log" "$WORK/systemctl.log" "$WORK/recovery-mode" "$WORK/status.log"
    PATH="$BIN:$PATH" \
    ARMADA_INPUT_LIB="$INPUT_LIB" \
    ARMADA_INPUT_CLASS="$SYS" \
    ARMADA_INPUT_DEV_DIR="$DEV" \
    ARMADA_SESSION_CONTROL="$WORK/session-control" \
    ARMADA_SPLASH_PROGRESS="$WORK/progress" \
    ARMADA_RECOVERY_MARKER="$WORK/recovery-mode" \
    ARMADA_BOOT_HOTKEY_POLL_MS=10 \
    ARMADA_BOOT_HOTKEY_HOLD_MS=30 \
    ARMADA_BOOT_HOTKEY_MAX=1 \
    ARMADA_SPLASH_CEF_PORT="${CEF_PORT:-1}" \
    bash "$HOTKEYS" > "$WORK/out.log" 2>&1
}

# Only the device that reports the key code is polled.
rm -f "$WORK/pressed" "$WORK/dm-active"
run_hotkeys
[[ -e "$WORK/session.log" ]] && fail "no hold: switched sessions anyway"
[[ -e "$WORK/recovery-mode" ]] && fail "no hold: marked recovery mode anyway"
sort -u "$WORK/queried" > "$WORK/queried.uniq"
[[ "$(cat "$WORK/queried.uniq")" == "$DEV/event1" ]] \
    || fail "device selection: polled $(tr '\n' ' ' < "$WORK/queried.uniq")"

# Held before the display manager is up: write the autologin drop-in only.
: > "$WORK/pressed"
run_hotkeys
assert_grep "$WORK/session.log" "default-desktop" "pre-sddm hold"
assert_grep "$WORK/systemctl.log" "start armada-session-default.service" "waits for the autologin reset"
# The marker is what a desktop recovery tool would key off.
assert_file "$WORK/recovery-mode" "recovery marker written"
assert_grep "$WORK/status.log" "Starting Desktop" "splash announce"
assert_grep "$WORK/log" "holding Desktop Mode" "journal notes the hold"
assert_grep "$WORK/log" "triggering Desktop Mode" "journal notes the trigger"

# Held once the session is running: restart it the way Steam's own switch does.
: > "$WORK/dm-active"
run_hotkeys
assert_grep "$WORK/session.log" "switch-desktop" "post-sddm hold"

# Steam's UI ends the watch, so the button goes back to being Steam's.
python3 -c 'import socket,sys,time
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(("127.0.0.1",0)); s.listen()
print(s.getsockname()[1], flush=True)
time.sleep(20)' > "$WORK/port" &
port_pid=$!
for _ in {1..100}; do [[ -s "$WORK/port" ]] && break; sleep 0.05; done
CEF_PORT="$(cat "$WORK/port")" run_hotkeys
kill "$port_pid" 2>/dev/null || true
[[ -e "$WORK/session.log" ]] && fail "steam up: switched sessions anyway"
[[ -e "$WORK/queried" ]] && fail "steam up: kept polling the volume key"

# Device replacement: the key moves to another node after a successful scan.
# Fails without the periodic rescan, which is the point of the case.
rm -f "$WORK/dm-active" "$WORK/dm-failed" "$WORK/session.log"
printf '%s\n' "$DEV/event2" > "$WORK/pressed-dev"
printf '400000000000000 0 0 0 0\n' > "$SYS/event1/device/capabilities/key"
printf '0\n' > "$SYS/event2/device/capabilities/key"
( sleep 0.3
  printf '0\n' > "$SYS/event1/device/capabilities/key"
  printf '400000000000000 0 0 0 0\n' > "$SYS/event2/device/capabilities/key" ) &
appear_pid=$!
PATH="$BIN:$PATH" \
ARMADA_INPUT_LIB="$INPUT_LIB" ARMADA_INPUT_CLASS="$SYS" ARMADA_INPUT_DEV_DIR="$DEV" \
ARMADA_RECOVERY_MARKER="$WORK/recovery-mode" \
ARMADA_SESSION_CONTROL="$WORK/session-control" \
ARMADA_BOOT_HOTKEY_POLL_MS=10 ARMADA_BOOT_HOTKEY_HOLD_MS=30 \
ARMADA_BOOT_HOTKEY_RESCAN_MS=20 ARMADA_BOOT_HOTKEY_MAX=3 \
ARMADA_SPLASH_CEF_PORT=1 \
    bash "$HOTKEYS" > "$WORK/out.log" 2>&1
wait "$appear_pid" 2>/dev/null || true
assert_grep "$WORK/session.log" "default-desktop" "key moving to another node is rescanned"
rm -f "$WORK/pressed-dev"
printf '400000000000000 0 0 0 0\n' > "$SYS/event1/device/capabilities/key"
printf '800000000000000 0 0 0 0\n' > "$SYS/event2/device/capabilities/key"

# Nothing else retries a failed sddm: session-control resets the failure state
# without starting it.
rm -f "$WORK/dm-active"
: > "$WORK/dm-failed"
run_hotkeys
assert_grep "$WORK/session.log" "default-desktop" "failed sddm still sets autologin"
assert_grep "$WORK/systemctl.log" "start display-manager.service" "failed sddm is started"
rm -f "$WORK/dm-failed"

# Not started yet is the normal case: systemd starts it next, so do not race it.
run_hotkeys
assert_no_grep "$WORK/systemctl.log" "start display-manager.service" "pre-sddm must not start it"

grep -qE '^ *"314:BTN_SELECT:Desktop Mode:action_desktop"' "$HOTKEYS" \
    || fail "the hotkey table entry changed shape"
grep -q 'Before=display-manager.service' "$UNIT" || fail "unit must start before sddm"
grep -q 'ConditionPathExists=!/etc/armada/boot-hotkeys-disabled' "$UNIT" \
    || fail "unit needs an escape hatch"
grep -q 'WantedBy=sysinit.target' "$UNIT" \
    || fail "unit must start with the splash, not at basic.target"
grep -q 'After=.*armada-session-default' "$UNIT" \
    && fail "static ordering after armada-session-default pins the hold onto sddm's start"
grep -q 'systemctl enable armada-boot-hotkeys.service' "$ROOT/build_files/40-vendor-system-files.sh" \
    || fail "armada-boot-hotkeys.service is not enabled in the image"

echo "PASS: boot-hotkeys"
