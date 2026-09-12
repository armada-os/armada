#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MOUNT_HELPER="$ROOT/system_files/usr/libexec/armada/armada-guestos-mount"
SERVICE="$ROOT/system_files/usr/lib/systemd/system/armada-guestos.service"
STEAM_BUILD="$ROOT/build_files/30-install-steam-session.sh"
VENDOR_BUILD="$ROOT/build_files/40-vendor-system-files.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_contains() {
    [[ "$1" == *"$2"* ]] || fail "expected output to contain ${2@Q}, got ${1@Q}"
}

mkdir -p "$WORK/root/usr/share/fex-emu/RootFS" "$WORK/root/usr/share/guestos/fex-mesa" \
    "$WORK/bin" "$WORK/run"
touch "$WORK/root/usr/share/fex-emu/RootFS/ArchLinux.sqsh" \
    "$WORK/root/usr/share/fex-emu/RootFS/ArmadaMesa.sqsh"
sed \
    -e "s|/usr/share/fex-emu/RootFS|$WORK/root/usr/share/fex-emu/RootFS|g" \
    -e "s|/usr/share/guestos/fex-mesa|$WORK/root/usr/share/guestos/fex-mesa|g" \
    -e "s|/run/armada/guestos|$WORK/run|g" \
    "$MOUNT_HELPER" > "$WORK/helper"
chmod +x "$WORK/helper"

cat > "$WORK/bin/mountpoint" <<'EOF'
#!/usr/bin/env bash
[[ -f "$MOUNT_STATE/$(printf '%s' "$2" | sed 's|/|_|g')" ]]
EOF
cat > "$WORK/bin/mount" <<'EOF'
#!/usr/bin/env bash
printf 'mount %s\n' "$*" >> "$MOUNT_LOG"
if [[ -n "${FAIL_MATCH:-}" && "$*" == *"${FAIL_MATCH}"* ]]; then
    exit 1
fi
target="${!#}"
touch "$MOUNT_STATE/$(printf '%s' "$target" | sed 's|/|_|g')"
EOF
cat > "$WORK/bin/umount" <<'EOF'
#!/usr/bin/env bash
printf 'umount %s\n' "$*" >> "$MOUNT_LOG"
rm -f "$MOUNT_STATE/$(printf '%s' "$1" | sed 's|/|_|g')"
EOF
chmod +x "$WORK/bin"/*

export MOUNT_LOG="$WORK/mount.log" MOUNT_STATE="$WORK/state"
mkdir -p "$MOUNT_STATE"

assert_failed_start_cleans_up() {
    local fail_match="$1"

    rm -f "$MOUNT_STATE"/* "$MOUNT_LOG"
    if FAIL_MATCH="$fail_match" PATH="$WORK/bin:/usr/bin:/bin" "$WORK/helper" start; then
        fail "start succeeded with injected failure ${fail_match@Q}"
    fi
    if find "$MOUNT_STATE" -type f -print -quit | grep -q .; then
        fail "start left mounts behind after injected failure ${fail_match@Q}"
    fi
}

assert_failed_start_cleans_up 'ArchLinux.sqsh'
assert_failed_start_cleans_up 'ArmadaMesa.sqsh'
assert_failed_start_cleans_up '-t overlay'

: > "$MOUNT_LOG"
PATH="$WORK/bin:/usr/bin:/bin" "$WORK/helper" start

log="$(<"$MOUNT_LOG")"
rootfs_sqsh="$WORK/root/usr/share/fex-emu/RootFS/ArchLinux.sqsh"
mesa_sqsh="$WORK/root/usr/share/fex-emu/RootFS/ArmadaMesa.sqsh"
assert_contains "$log" "mount -t squashfs -o ro,loop $rootfs_sqsh $WORK/run/rootfs"
assert_contains "$log" "mount -t squashfs -o ro,loop $mesa_sqsh $WORK/run/mesa"
assert_contains "$log" "mount -t overlay overlay -o lowerdir=$WORK/run/mesa:$WORK/run/rootfs $WORK/root/usr/share/guestos/fex-mesa"

before="$(wc -l < "$MOUNT_LOG")"
PATH="$WORK/bin:/usr/bin:/bin" "$WORK/helper" start
[[ "$(wc -l < "$MOUNT_LOG")" -eq "$before" ]] || fail 'start is not idempotent'

PATH="$WORK/bin:/usr/bin:/bin" "$WORK/helper" stop
tail -n 3 "$MOUNT_LOG" > "$WORK/unmount.log"
expected=$(printf 'umount %s\numount %s\numount %s' \
    "$WORK/root/usr/share/guestos/fex-mesa" "$WORK/run/mesa" "$WORK/run/rootfs")
[[ "$(<"$WORK/unmount.log")" == "$expected" ]] || fail 'mounts were not removed in reverse order'

grep -qx 'ConditionPathExists=/usr/share/fex-emu/RootFS/ArchLinux.sqsh' "$SERVICE" ||
    fail 'service does not require ArchLinux.sqsh'
grep -qx 'ConditionPathExists=/usr/share/fex-emu/RootFS/ArmadaMesa.sqsh' "$SERVICE" ||
    fail 'service does not require ArmadaMesa.sqsh'

# Separate components keep Mesa-only updates from invalidating ArchLinux.sqsh.
grep -F 'b"fex-rootfs"' "$STEAM_BUILD" | grep -Fq '/ArchLinux.sqsh' ||
    fail 'ArchLinux.sqsh does not have its own rechunk component'
grep -F 'b"fex-mesa"' "$VENDOR_BUILD" | grep -Fq '"${mesa_sqsh}"' ||
    fail 'ArmadaMesa.sqsh does not have its own rechunk component'
grep -Fq 'install -Dm0644 /packages/mesa-x86/ArmadaMesa.sqsh "${mesa_sqsh}"' "$VENDOR_BUILD" ||
    fail 'Armada regenerates rather than consumes the packaged Mesa image'
if grep -q 'mksquashfs' "$VENDOR_BUILD"; then
    fail 'Armada regenerates the packaged Mesa image'
fi

echo 'guestos mount test passed'
