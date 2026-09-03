#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RENAME="$ROOT/system_files/usr/libexec/armada/armada-esp-rename"
UNIT="$ROOT/system_files/usr/lib/systemd/system/armada-esp-rename.service"
FSCK_DROPIN="$ROOT/system_files/usr/lib/systemd/system/systemd-fsck@.service.d/10-armada-esp-rename.conf"
INSTALLER="$ROOT/system_files/usr/libexec/armada/armada-installer"
VENDOR_BUILD="$ROOT/build_files/40-vendor-system-files.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_eq() {
    [[ "$2" == "$3" ]] || fail "$1: expected ${3@Q}, got ${2@Q}"
}

STATE="$WORK/state"
BIN="$WORK/bin"
mkdir -p "$STATE" "$BIN"
export STATE

# Replace only block-device guards so the shipped logic runs against fakes.
sed -e 's/\[\[ -b \$parent \]\]/true/' \
    -e 's/\[\[ -b \$esp \]\]/true/' \
    "$RENAME" > "$WORK/rename.sh"

cat > "$WORK/storage-lib" <<'EOF'
armada_root_device() { echo /dev/fakedisk; }
EOF
cat > "$BIN/readlink" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "${@: -1}"
EOF
cat > "$BIN/lsblk" <<'EOF'
#!/usr/bin/env bash
root=OTHER_ROOT
[[ $(cat "$STATE/has_root") == 1 ]] && root=ARMADA_ROOT
extra=
[[ $(cat "$STATE/duplicate") == 0 ]] || extra=',{"name":"/dev/fake4","partlabel":"ARMADA","partn":4}'
printf '{"blockdevices":[{"name":"/dev/fakedisk","pttype":"%s","children":[{"name":"/dev/fake1","partlabel":"%s","partn":1},{"name":"/dev/fake2","partlabel":"ARMADA_BOOT","partn":2},{"name":"/dev/fake3","partlabel":"%s","partn":3}%s]}]}\n' \
    "$(cat "$STATE/table")" "$(cat "$STATE/partlabel")" "$root" "$extra"
EOF
cat > "$BIN/blkid" <<'EOF'
#!/usr/bin/env bash
if [[ " $* " == *" -s TYPE "* ]]; then
    cat "$STATE/fstype"
else
    cat "$STATE/fslabel"
fi
EOF
cat > "$BIN/findmnt" <<'EOF'
#!/usr/bin/env bash
[[ "$*" == "-rn --source /dev/fake1" ]] || exit 0
[[ $(cat "$STATE/mounted") == 1 ]]
EOF
cat > "$BIN/fatlabel" <<'EOF'
#!/usr/bin/env bash
[[ ! -e "$STATE/fail_fatlabel" ]] || exit 1
printf 'fatlabel:%s\n' "$2" >> "$STATE/log"
printf '%s\n' "$2" > "$STATE/fslabel"
EOF
cat > "$BIN/sgdisk" <<'EOF'
#!/usr/bin/env bash
[[ ! -e "$STATE/fail_sgdisk" ]] || exit 1
change=${1#--change-name=}
printf 'sgdisk:%s:%s\n' "$change" "$2" >> "$STATE/log"
printf '%s\n' "${change#*:}" > "$STATE/partlabel"
EOF
cat > "$BIN/sync" <<'EOF'
#!/usr/bin/env bash
echo sync >> "$STATE/log"
EOF
chmod +x "$BIN"/*

reset_state() {
    printf '%s\n' "${1:-ROCKNIX}" > "$STATE/partlabel"
    printf '%s\n' "${2:-ROCKNIX}" > "$STATE/fslabel"
    printf '%s\n' "${3:-gpt}" > "$STATE/table"
    printf '%s\n' "${4:-1}" > "$STATE/has_root"
    echo 0 > "$STATE/duplicate"
    echo 0 > "$STATE/mounted"
    echo vfat > "$STATE/fstype"
    : > "$STATE/log"
    rm -f "$STATE"/fail_*
}
run_rename() {
    ARMADA_STORAGE_LIB="$WORK/storage-lib" PATH="$BIN:$PATH" bash "$WORK/rename.sh"
}

reset_state
run_rename >/dev/null
assert_eq "GPT label" "$(cat "$STATE/partlabel")" ARMADA
assert_eq "filesystem label" "$(cat "$STATE/fslabel")" ARMADA
assert_eq "migration order" "$(tr '\n' ' ' < "$STATE/log")" \
    "fatlabel:ARMADA sgdisk:1:ARMADA:/dev/fakedisk sync "

reset_state ARMADA ARMADA
run_rename >/dev/null
[[ ! -s "$STATE/log" ]] || fail "already-renamed ESP was modified"

reset_state ROCKNIX ARMADA
run_rename >/dev/null
[[ $(cat "$STATE/log") != *fatlabel* ]] || fail "current FAT label was rewritten"
assert_eq "partial GPT label" "$(cat "$STATE/partlabel")" ARMADA

reset_state ARMADA ROCKNIX
run_rename >/dev/null
[[ $(cat "$STATE/log") != *sgdisk* ]] || fail "current GPT name was rewritten"
assert_eq "partial filesystem label" "$(cat "$STATE/fslabel")" ARMADA

reset_state ROCKNIX ROCKNIX dos
run_rename >/dev/null
[[ ! -s "$STATE/log" ]] || fail "MBR disk was modified"
reset_state ROCKNIX ROCKNIX gpt 0
run_rename >/dev/null
[[ ! -s "$STATE/log" ]] || fail "unrelated GPT was modified"
reset_state
echo 1 > "$STATE/duplicate"
run_rename >/dev/null
[[ ! -s "$STATE/log" ]] || fail "ambiguous ESP candidates were modified"
reset_state
echo 1 > "$STATE/mounted"
run_rename >/dev/null 2>&1
[[ ! -s "$STATE/log" ]] || fail "mounted ESP was modified"
reset_state
echo ext4 > "$STATE/fstype"
run_rename >/dev/null 2>&1
[[ ! -s "$STATE/log" ]] || fail "non-vfat ESP was modified"

reset_state
touch "$STATE/fail_fatlabel"
if run_rename >/dev/null 2>&1; then
    fail "fatlabel failure returned success"
fi
[[ ! -s "$STATE/log" ]] || fail "GPT rename followed failed FAT rename"

reset_state
touch "$STATE/fail_sgdisk"
if run_rename >/dev/null 2>&1; then
    fail "sgdisk failure returned success"
fi
assert_eq "failed GPT write filesystem label" "$(cat "$STATE/fslabel")" ARMADA
assert_eq "failed GPT write partition label" "$(cat "$STATE/partlabel")" ROCKNIX

grep -q '^DefaultDependencies=no$' "$UNIT" || fail "unit has default boot dependencies"
grep -q '^Before=boot-efi.mount local-fs.target$' "$UNIT" || fail "unit is not before the ESP mount"
grep -q '^TimeoutStartSec=30$' "$UNIT" || fail "unit has no bounded timeout"
grep -q '^ExecStart=-/usr/libexec/armada/armada-esp-rename$' "$UNIT" || fail "unit is not best effort"
grep -q '^After=armada-esp-rename.service$' "$FSCK_DROPIN" || fail "fsck can race the rename"
grep -q '^systemctl enable armada-esp-rename.service$' "$VENDOR_BUILD" || fail "unit is not enabled"
[[ -x "$RENAME" ]] || fail "rename helper is not executable"

grep -q 'ESP_PARTLABEL="ARMADA"' "$INSTALLER" || fail "new ESP label is not ARMADA"
grep -q 'ROCKNIX|ARMADA|ARMADA_BOOT|ARMADA_ROOT' "$INSTALLER" || fail "legacy ESP is not removable"
eval "$(sed -n '/^detect_mode()/,/^}/p' "$INSTALLER")"
eval "$(sed -n '/^cmd_detect()/,/^}/p' "$INSTALLER")"
partition_names() { echo ARMADA; }
need_root() { :; }
check_device() { :; }
find_userdata() { UD_ORIG_GIB=8; }
collect_our_tail() { LINUX_BYTES=536870912; }
detected=$(cmd_detect)
assert_eq "new ESP mode" "$(sed -n 's/^mode=//p' <<<"$detected")" occupied
assert_eq "new ESP owner" "$(sed -n 's/^installed=//p' <<<"$detected")" armada

echo "ESP rename tests passed"
