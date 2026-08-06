#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DEVICE_ENV="$ROOT/system_files/usr/libexec/armada/device-env"
CONTROLLER_LAYOUT="$ROOT/system_files/usr/libexec/armada/controller-layout"
CONTROLLER_TYPE="$ROOT/system_files/usr/libexec/armada/controller-type"
SOURCE_DEVICE_DIR="$ROOT/system_files/usr/lib/armada/devices"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
DEVICE_DIR="$tmp/devices"
mkdir -p "$DEVICE_DIR"
for profile in \
    defaults \
    ayn-odin-3 \
    retroid-pocket-5 \
    retroid-pocket-6 \
    retroid-pocket-flip2 \
    retroid-pocket-mini \
    retroid-pocket-mini-v2 \
    retroid-pocket-nova; do
    sed 's/\r$//' "$SOURCE_DEVICE_DIR/$profile.conf" >"$DEVICE_DIR/$profile.conf"
done

assert_device_legends() {
    local model=$1
    local expected=$2
    local actual
    actual="$(
        ARMADA_MODEL="$model" ARMADA_DEVICE_DIR="$DEVICE_DIR" \
            bash <(sed 's/\r$//' "$DEVICE_ENV") |
            sed -n 's/^ARMADA_BUILTIN_FACE_BUTTON_LEGENDS=//p'
    )"
    if [[ "$actual" != "$expected" ]]; then
        printf '%s: expected %s legends, got %s\n' "$model" "$expected" "$actual" >&2
        exit 1
    fi
}

assert_device_legends "AYN Odin 3" xbox
assert_device_legends "Retroid Pocket 5" nintendo
assert_device_legends "Retroid Pocket 6" nintendo
assert_device_legends "Retroid Pocket Flip2" nintendo
assert_device_legends "Retroid Pocket Mini" nintendo
assert_device_legends "Retroid Pocket Mini V2" nintendo
assert_device_legends "Retroid Pocket Nova" nintendo
assert_device_legends "Unknown Handheld" xbox

config="$tmp/controller.conf"
fake_device_env="$tmp/device-env"
cat >"$fake_device_env" <<'EOF'
#!/usr/bin/env bash
printf 'ARMADA_BUILTIN_FACE_BUTTON_LEGENDS=nintendo\n'
EOF
chmod +x "$fake_device_env"

export ARMADA_CONTROLLER_CONFIG="$config"
export ARMADA_DEVICE_ENV="$fake_device_env"

[[ "$(python3 "$CONTROLLER_LAYOUT" get)" == auto ]]
[[ "$(python3 "$CONTROLLER_LAYOUT" resolve)" == nintendo ]]

python3 "$CONTROLLER_LAYOUT" set xbox
[[ "$(python3 "$CONTROLLER_LAYOUT" get)" == xbox ]]
[[ "$(python3 "$CONTROLLER_LAYOUT" resolve)" == xbox ]]

CONTROLLER_TYPE="$CONTROLLER_TYPE" python3 - <<'PY'
import importlib.machinery
import os

module = importlib.machinery.SourceFileLoader(
    "controller_type", os.environ["CONTROLLER_TYPE"]
).load_module()
module.save_type("ds5")
PY

grep -Fxq 'button_layout=xbox' "$config"
grep -Fxq 'controller_type=ds5' "$config"

python3 "$CONTROLLER_LAYOUT" set auto
grep -Fxq 'controller_type=ds5' "$config"
[[ "$(python3 "$CONTROLLER_LAYOUT" resolve)" == nintendo ]]

if python3 "$CONTROLLER_LAYOUT" set invalid 2>/dev/null; then
    printf 'invalid button layout was accepted\n' >&2
    exit 1
fi

printf 'Controller layout policy test passed\n'
