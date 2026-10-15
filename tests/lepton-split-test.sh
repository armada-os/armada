#!/usr/bin/env bash
set -euo pipefail
steamvr() { return 0; }
source "${1:?usage: lepton-split-test.sh <patched-tool>/liblepton/liblepton.sh}"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir "$work/APK set"
APP_DIR="$work/APK set"
APP_PATH=
printf base > "$APP_DIR/base.apk"
printf split > "$APP_DIR/config.arm64_v8a.apk"
printf 'base.apk\nconfig.arm64_v8a.apk\n' > "$APP_DIR/.armada-apks"
[[ "$(get_apk_path)" == "$APP_DIR/base.apk" ]]
mapfile -t files < <(get_app_apks)
[[ "${#files[@]}" == 2 && "${files[1]}" == "$APP_DIR/config.arm64_v8a.apk" ]]
hash=$(extract_app_hash)
printf changed >> "$APP_DIR/config.arm64_v8a.apk"
[[ "$(extract_app_hash)" != "$hash" ]]

export ADB_CALLS="$work/calls"
cat > "$work/adb" <<'EOF'
#!/usr/bin/env bash
printf '%q ' "$@" >> "$ADB_CALLS"
printf '\n' >> "$ADB_CALLS"
EOF
chmod +x "$work/adb"
ADB="$work/adb"
uninherit_lepton_lock() { :; }
podman_attach() { :; }
extract_app_id() { echo org.example.test; }
adb_port() { echo 5555; }
is_steamlaunch() { return 0; }
install_app "$APP_DIR/base.apk"
calls=$(<"$ADB_CALLS")
[[ "$calls" == *" install-multiple -g "* && "$calls" == *"config.arm64_v8a.apk"* ]]

mkdir "$work/overlay" "$work/installed"
cp "$APP_DIR/"*.apk "$work/overlay/"
printf installed > "$work/installed/base.apk"
cp "$APP_DIR/config.arm64_v8a.apk" "$work/installed/split_config.arm64_v8a.apk"
printf keep > "$work/overlay/steam_appid.txt"
APP_PATH="$work/installed"
post_install=$(sed -n '/# Move everything to our overlay\./,/# Now that we know/p' \
    "$LEPTON_DIR/../images/rootfs_overlay/system/bin/cmd")
[[ "$post_install" == *'mv '* ]]
eval "${post_install//\/data\/steam_app/$work/overlay}"
[[ ! -e "$work/overlay/config.arm64_v8a.apk" ]]
[[ -f "$work/overlay/split_config.arm64_v8a.apk" ]]
[[ "$(<"$work/overlay/base.apk")" == installed ]]
[[ "$(<"$work/overlay/steam_appid.txt")" == keep ]]
[[ -f "$APP_DIR/config.arm64_v8a.apk" ]]

printf standalone > "$work/standalone.apk"
APP_PATH="$work/standalone.apk"
[[ "$(extract_app_hash)" == "$(sha256sum "$APP_PATH" | cut -d' ' -f1)" ]]
: > "$ADB_CALLS"
install_app "$APP_PATH"
calls=$(<"$ADB_CALLS")
[[ "$calls" == *" install -g "* && "$calls" != *"install-multiple"* ]]

APP_PATH="$APP_DIR/base.apk"
rm "$APP_DIR/config.arm64_v8a.apk"
if extract_app_hash >/dev/null; then
    echo 'accepted an incomplete APK set' >&2
    exit 1
fi
: > "$ADB_CALLS"
if install_app "$APP_PATH"; then
    echo 'installed an incomplete APK set' >&2
    exit 1
fi
calls=$(<"$ADB_CALLS")
[[ "$calls" != *" install "* && "$calls" != *" install-multiple "* ]]
echo 'Lepton split APK tests passed'
