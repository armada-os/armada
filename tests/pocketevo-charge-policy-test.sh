#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY="$ROOT/system_files/usr/libexec/armada/armada-pocketevo-charge-policy"
CLEANUP="$ROOT/system_files/usr/libexec/armada/armada-pocketevo-charge-cleanup"
UNIT="$ROOT/system_files/usr/lib/systemd/system/armada-pocketevo-charge-policy.service"
BUILD="$ROOT/build_files/40-vendor-system-files.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_eq() { [[ "$1" == "$2" ]] || fail "$3: expected '$2', got '$1'"; }
assert_contains() { grep -Fq -- "$2" "$1" || fail "$3: '$2' not found in $1"; }

PSY="$WORK/power_supply"
STATE="$WORK/state"
BIN="$WORK/bin"
mkdir -p "$BIN"
cat > "$BIN/no-sleep" <<'EOF'
#!/bin/sh
exit 0
EOF
cat > "$BIN/cleanup" <<EOF
#!/bin/sh
exec sh "$CLEANUP"
EOF
chmod +x "$BIN/no-sleep" "$BIN/cleanup"

writev() {
	mkdir -p "$(dirname -- "$1")"
	printf '%s\n' "$2" > "$1"
}

setup_good() {
	rm -rf "$PSY" "$STATE"
	mkdir -p "$PSY/qcom-battmgr-usb" "$PSY/battery" \
		"$PSY/hl7139-master" "$PSY/hl7139-slave" "$STATE"

	writev "$PSY/qcom-battmgr-usb/online" 1
	writev "$PSY/qcom-battmgr-usb/usb_type" 'Unknown SDP [PD_PPS]'
	writev "$PSY/qcom-battmgr-usb/voltage_now" 8800000
	writev "$PSY/qcom-battmgr-usb/current_now" 0
	writev "$PSY/qcom-battmgr-usb/input_current_limit" 3000000

	writev "$PSY/battery/status" Charging
	writev "$PSY/battery/capacity" 50
	writev "$PSY/battery/voltage_now" 4000000
	writev "$PSY/battery/current_now" 4800000
	writev "$PSY/battery/temp" 250
	writev "$PSY/battery/charge_control_start_threshold" 40
	writev "$PSY/battery/charge_control_end_threshold" 90

	for pump in hl7139-master hl7139-slave; do
		writev "$PSY/$pump/online" 0
		writev "$PSY/$pump/present" 1
		writev "$PSY/$pump/health" Good
		writev "$PSY/$pump/voltage_now" 9000000
		writev "$PSY/$pump/voltage_avg" 4000000
		writev "$PSY/$pump/current_now" 1450000
		writev "$PSY/$pump/temp" 350
	done
}

common_env=(
	ARMADA_POWER_SUPPLY_ROOT="$PSY"
	ARMADA_CHARGE_STATE_DIR="$STATE"
	ARMADA_CHARGE_SLEEP_CMD="$BIN/no-sleep"
	ARMADA_CHARGE_CLEANUP="$BIN/cleanup"
	ARMADA_CHARGE_CLEANUP_RETRIES=2
)

run_cleanup() {
	env "${common_env[@]}" sh "$CLEANUP"
}

run_policy() {
	env "${common_env[@]}" "$@" sh "$POLICY"
}

# Explicit opt-in: the image must neither enable the daemon nor allow it to
# start without the persistent owner-created marker.
if grep -q 'systemctl enable armada-pocketevo-charge-policy.service' "$BUILD"; then
	fail 'direct-charge service is enabled by the image'
fi
assert_contains "$UNIT" 'ConditionPathExists=/etc/armada/experimental/pocketevo-direct-charge' 'opt-in marker'
assert_contains "$UNIT" 'ExecStopPost=/usr/libexec/armada/armada-pocketevo-charge-cleanup' 'independent cleanup'
assert_contains "$UNIT" 'Restart=no' 'fault re-arm policy'
assert_contains "$UNIT" 'WatchdogSec=600s' 'daemon watchdog'

# Verified cleanup restores Qualcomm charging only after both readbacks are 0.
setup_good
writev "$PSY/hl7139-master/online" 1
writev "$PSY/hl7139-slave/online" 1
writev "$PSY/qcom-battmgr-usb/input_current_limit" 13000
run_cleanup >/dev/null
assert_eq "$(<"$PSY/hl7139-master/online")" 0 'master cleanup'
assert_eq "$(<"$PSY/hl7139-slave/online")" 0 'slave cleanup'
assert_eq "$(<"$PSY/qcom-battmgr-usb/input_current_limit")" 3000000 'Qualcomm restore'

# An injected pump-disable failure leaves the Qualcomm path inhibited and
# records a persistent visible fault.
setup_good
writev "$PSY/hl7139-master/online" 1
writev "$PSY/hl7139-slave/online" 1
writev "$PSY/qcom-battmgr-usb/input_current_limit" 13000
if env "${common_env[@]}" ARMADA_CHARGE_TEST_STUCK_PUMP=master sh "$CLEANUP" >/dev/null 2>&1; then
	fail 'cleanup accepted unreadable master CHG_EN'
fi
assert_eq "$(<"$PSY/qcom-battmgr-usb/input_current_limit")" 13000 'fail-closed Qualcomm ICL'
assert_contains "$STATE/fault" 'pump shutdown could not be verified' 'cleanup fault state'

# A non-PPS source and firmware-side charging inhibit are rejected before the
# 13 mA handoff vote is written.
setup_good
writev "$PSY/qcom-battmgr-usb/usb_type" 'Unknown [DCP] PD_PPS'
run_policy ARMADA_CHARGE_MAX_IDLE_LOOPS=1 >/dev/null
assert_eq "$(<"$PSY/qcom-battmgr-usb/input_current_limit")" 3000000 'non-PPS preflight'
assert_eq "$(<"$PSY/hl7139-master/online")" 0 'non-PPS master state'

setup_good
writev "$PSY/battery/status" 'Not charging'
run_policy ARMADA_CHARGE_MAX_IDLE_LOOPS=1 >/dev/null
assert_eq "$(<"$PSY/qcom-battmgr-usb/input_current_limit")" 3000000 'charge-inhibit preflight'

setup_good
writev "$PSY/battery/capacity" 80
writev "$PSY/battery/charge_control_end_threshold" 80
run_policy ARMADA_CHARGE_MAX_IDLE_LOOPS=1 >/dev/null
assert_eq "$(<"$PSY/hl7139-slave/online")" 0 'configured endpoint'

# A configured endpoint below the hard-coded 90% ceiling is honored during an
# active session and ends normally rather than becoming a latched fault.
setup_good
writev "$PSY/battery/capacity" 79
writev "$PSY/battery/charge_control_end_threshold" 80
cat > "$BIN/endpoint-hook" <<EOF
#!/bin/sh
printf '80\n' > '$PSY/battery/capacity'
EOF
chmod +x "$BIN/endpoint-hook"
run_policy ARMADA_CHARGE_MAX_EVENTS=1 ARMADA_CHARGE_SAMPLE_HOOK="$BIN/endpoint-hook" >/dev/null
[[ ! -e "$STATE/fault" ]] || fail 'normal endpoint was latched as a fault'
assert_eq "$(<"$PSY/qcom-battmgr-usb/input_current_limit")" 3000000 'endpoint Qualcomm restore'

# Initial PPS requests are quantized to the kernel-enforced 20 mV grid even
# when battery telemetry is not itself step-aligned.
setup_good
writev "$PSY/battery/voltage_now" 4003123
cat > "$BIN/pps-step-hook" <<EOF
#!/bin/sh
cat '$PSY/qcom-battmgr-usb/voltage_now' > '$WORK/requested-voltage'
printf '90\n' > '$PSY/battery/capacity'
EOF
chmod +x "$BIN/pps-step-hook"
run_policy ARMADA_CHARGE_MAX_EVENTS=1 ARMADA_CHARGE_SAMPLE_HOOK="$BIN/pps-step-hook" >/dev/null
assert_eq "$(( $(<"$WORK/requested-voltage") % 20000 ))" 0 'PPS request step'

# Read-to-clear electrical faults and pair-coherence failures remain latched
# after successful pump cleanup; they cannot silently re-arm after 60 seconds.
setup_good
cat > "$BIN/electrical-hook" <<EOF
#!/bin/sh
printf 'Overvoltage\n' > '$PSY/hl7139-master/health'
EOF
chmod +x "$BIN/electrical-hook"
if run_policy ARMADA_CHARGE_MAX_EVENTS=1 ARMADA_CHARGE_SAMPLE_HOOK="$BIN/electrical-hook" >/dev/null 2>&1; then
	fail 'electrical fault returned success'
fi
assert_eq "$(<"$STATE/fault")" electrical 'electrical latch'
assert_eq "$(<"$PSY/hl7139-master/online")" 0 'electrical cleanup master'
assert_eq "$(<"$PSY/hl7139-slave/online")" 0 'electrical cleanup slave'

setup_good
cat > "$BIN/telemetry-hook" <<EOF
#!/bin/sh
printf '7600000\n' > '$PSY/hl7139-slave/voltage_now'
EOF
chmod +x "$BIN/telemetry-hook"
if run_policy ARMADA_CHARGE_MAX_EVENTS=1 ARMADA_CHARGE_SAMPLE_HOOK="$BIN/telemetry-hook" >/dev/null 2>&1; then
	fail 'incoherent pump telemetry returned success'
fi
assert_eq "$(<"$STATE/fault")" telemetry 'telemetry latch'

# A cable-cycle latch clears only after both pumps also report VBUS absent;
# the USB supply going offline first is not enough to re-arm the session.
setup_good
cat > "$BIN/cable-cycle-hook" <<EOF
#!/bin/sh
printf 'Overvoltage\n' > '$PSY/hl7139-master/health'
printf '0\n' > '$PSY/qcom-battmgr-usb/online'
printf '1\n' > '$PSY/hl7139-master/present'
printf '1\n' > '$PSY/hl7139-slave/present'
(sleep 0.1; printf '0\n' > '$PSY/hl7139-master/present'; printf '0\n' > '$PSY/hl7139-slave/present') &
EOF
chmod +x "$BIN/cable-cycle-hook"
run_policy ARMADA_CHARGE_MAX_EVENTS=2 ARMADA_CHARGE_MAX_IDLE_LOOPS=1 \
	ARMADA_CHARGE_SAMPLE_HOOK="$BIN/cable-cycle-hook" >/dev/null
# Let the hook's delayed VBUS-removal writes finish before the temporary
# power-supply tree is removed by the EXIT trap.
sleep 0.2
[[ ! -e "$STATE/fault" ]] || fail 'fault cleared before pump VBUS went absent'

# The user-facing toggle script ships executable and stays opt-in: 'status'
# works without root, while 'enable'/'disable' demand root.
TOGGLE="$ROOT/system_files/usr/bin/armada-charge-toggle"
[[ -x "$TOGGLE" ]] || fail 'armada-charge-toggle not installed/executable'
bash -n "$TOGGLE" || fail 'armada-charge-toggle syntax'
grep -q "systemctl enable --now" "$TOGGLE" || fail 'toggle enable path missing'
grep -q "systemctl disable --now" "$TOGGLE" || fail 'toggle disable path missing'
grep -q "rm -f" "$TOGGLE" || fail 'toggle must remove the opt-in flag on disable'
grep -qE "EUID != 0" "$TOGGLE" || fail 'toggle must require root for enable/disable'

sh -n "$POLICY" "$CLEANUP"
printf 'Pocket EVO direct-charge safety tests passed\n'

