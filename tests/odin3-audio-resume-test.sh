#!/usr/bin/env bash
set -euo pipefail

readonly root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly helper="$root/system_files/usr/libexec/armada/odin3-audio-resume"
readonly temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT

device_env="$temporary/device-env"
systemctl_mock="$temporary/systemctl"
calls="$temporary/systemctl.calls"
trigger="$temporary/armada-odin3-audio-resume-trigger"
pending="$temporary/armada-odin3-audio-resume"

cat >"$device_env" <<'EOF'
printf '%s\n' 'ARMADA_DEVICE_ID=ayn-odin-3'
printf '%s\n' "ARMADA_DEVICE_NAME='AYN Odin 3'"
printf '%s\n' 'ARMADA_SOC_CLASS=SM8750'
EOF
cat >"$systemctl_mock" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$MOCK_SYSTEMCTL_CALLS"
[[ "${MOCK_SYSTEMCTL_FAIL:-0}" != 1 ]]
EOF
chmod 0755 "$systemctl_mock"

run_helper() {
    XDG_RUNTIME_DIR="$temporary" \
    ARMADA_AUDIO_DEVICE_ENV="$device_env" \
    ARMADA_AUDIO_SYSTEMCTL="$systemctl_mock" \
    MOCK_SYSTEMCTL_CALLS="$calls" \
        bash "$helper"
}

printf '%s\n' 'Virtual Surround Sound' >"$trigger"
run_helper
[[ ! -e "$trigger" ]]
[[ "$(cat "$pending")" == 'Virtual Surround Sound' ]]
[[ "$(cat "$calls")" == \
    '--user --no-block restart armada-odin3-audio-hotplug.service' ]]

rm -f "$pending" "$calls"
printf '%s\n' 'not-an-output' >"$trigger"
run_helper
[[ ! -e "$trigger" && ! -e "$pending" && ! -e "$calls" ]]

printf '%s\n' 'Virtual Surround Sound' >"$trigger"
if XDG_RUNTIME_DIR="$temporary" \
    ARMADA_AUDIO_DEVICE_ENV="$device_env" \
    ARMADA_AUDIO_SYSTEMCTL="$systemctl_mock" \
    MOCK_SYSTEMCTL_CALLS="$calls" \
    MOCK_SYSTEMCTL_FAIL=1 \
        bash "$helper"; then
    printf '%s\n' 'ERROR: failed systemctl restart was reported as success' >&2
    exit 1
fi
[[ -f "$trigger" && ! -e "$pending" ]]

printf '%s\n' 'Odin 3 audio resume helper tests passed'
