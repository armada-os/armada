#!/usr/bin/env bash
# Covers the /KERNEL regeneration path: the shared BLS-to-cmdline transform,
# the known-good KERNEL.BAK snapshot, the target-deployment DTB list lookup,
# and the initramfs ostree fallback that rescues a stale /KERNEL.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ARMADA_LIB="$ROOT/system_files/usr/lib/armada"
UPDATE="$ROOT/system_files/usr/libexec/armada/armada-bootimg-update"
FALLBACK="$ROOT/system_files/usr/lib/dracut/modules.d/91armada-ostree-fallback/armada-ostree-fallback.sh"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_eq() {
    [[ "$2" == "$3" ]] || fail "$1: expected ${3@Q}, got ${2@Q}"
}
assert_contains() {
    [[ "$2" == *"$3"* ]] || fail "$1: expected output to contain ${3@Q}, got ${2@Q}"
}

# --- shared cmdline transform ------------------------------------------------

source "$ARMADA_LIB/bootimg-args"

BLS_OPTS="root=UUID=r rootflags=subvol=/root rw boot=UUID=b rootwait"
BLS_OPTS+=" rootflags=noatime,compress=zstd:1,space_cache=v2 console=tty0 quiet"
BLS_OPTS+=" console=ttyS0 ostree=/ostree/boot.1/default/csum/0"

cmdline="$(armada_bootimg_cmdline "$BLS_OPTS")"
# ostree= must lead: it is the karg the boot depends on, so a truncated
# header loses tuning kargs rather than the root pointer.
[[ "$cmdline" == "ostree=/ostree/boot.1/default/csum/0 "* ]] ||
    fail "transform: ostree= is not first: $cmdline"
[[ "$cmdline" != *"console=ttyS0"* ]] || fail "transform: serial console not dropped"
[[ "$cmdline" == *"console=tty0"* ]] || fail "transform: dropped the real console"
# Both rootflags= tokens must survive as one, or the root subvolume changes.
assert_contains "transform" "$cmdline" "rootflags=subvol=/root,noatime,compress=zstd:1"
[[ "$cmdline" != *"space_cache=v2"* ]] || fail "transform: legacy space_cache kept"
[[ "$(grep -o 'rootflags=' <<<"$cmdline" | wc -l)" == 1 ]] ||
    fail "transform: more than one rootflags= token"

# No ostree= karg must fail loudly rather than bake an unbootable /KERNEL.
if armada_bootimg_cmdline "root=UUID=r rw quiet" >/dev/null 2>&1; then
    fail "transform: accepted an options line with no ostree= karg"
fi

# Splitting the options line must not glob against the working directory.
globbed="$(cd "$WORK" && touch realfile && armada_bootimg_cmdline "ostree=/o/b/c/0 weird=*")"
assert_contains "transform" "$globbed" 'weird=*'
# ...and the noglob must not leak to the caller.
before="$-"; armada_bootimg_cmdline "ostree=/o/b/c/0" >/dev/null
assert_eq "transform shell options" "$-" "$before"

# The real BLS line has to fit the boot header with room to spare.
(( ${#cmdline} <= ARMADA_CMDLINE_MAX )) ||
    fail "transform: ${#cmdline}B exceeds ${ARMADA_CMDLINE_MAX}B"

# --- armada-bootimg-update: snapshot + DTB list resolution -------------------

# Neutralize the two things a test cannot provide: a mounted ESP and a
# lock under /run. Everything else runs as shipped.
ESP="$WORK/esp"; BOOT="$WORK/boot"; SYS="$WORK/sysroot"
mkdir -p "$ESP"
sed -e 's|findmnt -rn "${ESP}"|true "${ESP}"|' \
    -e "s|/run/armada-bootimg.lock|$WORK/lock|" "$UPDATE" > "$WORK/update.sh"

run_update() {
    ESP="$ESP" BOOTROOT="$BOOT" SYSROOT="$SYS" \
        ARGS_FILE="$ARMADA_LIB/bootimg-args" \
        DTB_LIST="$ARMADA_LIB/supported-dtbs" \
        MKBOOTIMG="$ROOT/build_files/vendor/mkbootimg/mkbootimg.py" \
        bash "$WORK/update.sh" "$@" 2>&1 || true
}

# A deployment tree complete enough to bake a real boot.img from.
CSUM=abc123
DEPLOY="$SYS/ostree/deploy/default/deploy/${CSUM}.0"
BOOTDIR="$BOOT/ostree/default-${CSUM}"
mkdir -p "$DEPLOY/usr/lib/armada" "$BOOTDIR/dtb/qcom" "$BOOT/loader/entries" \
    "$SYS/ostree/boot.1.0/default/$CSUM"
ln -sfn boot.1.0 "$SYS/ostree/boot.1"
ln -sfn "../../../deploy/default/deploy/${CSUM}.0" "$SYS/ostree/boot.1/default/$CSUM/0"
printf 'fake-kernel' > "$BOOTDIR/vmlinuz-9.9.9"
printf 'fake-initramfs' > "$BOOTDIR/initramfs-9.9.9.img"
# Named only in the deployment's list, so a hit proves the target-deployment
# lookup ran; a miss would fall back to the running list and not find it.
printf 'target-only-board\n' > "$DEPLOY/usr/lib/armada/supported-dtbs"
printf 'fake-dtb' > "$BOOTDIR/dtb/qcom/target-only-board.dtb"
cat > "$BOOT/loader/entries/ostree-1.conf" <<EOF
title Armada
version 1
options root=UUID=r rw rootflags=subvol=/root ostree=/ostree/boot.1/default/$CSUM/0
linux /boot/ostree/default-${CSUM}/vmlinuz-9.9.9
initrd /boot/ostree/default-${CSUM}/initramfs-9.9.9.img
fdtdir /boot/ostree/default-${CSUM}/dtb
EOF

out="$(run_update)"
assert_contains "regen" "$out" "wrote $ESP/KERNEL"
[[ -f "$ESP/KERNEL" ]] || fail "regen: no /KERNEL written"
[[ -s "$ESP/.armada-bootimg.id" ]] || fail "regen: no stamp written"
# Only the deployment's own list names this DTB, so it was read from there.
[[ "$out" != *"missing DTB"* ]] || fail "regen: did not use the target deployment's DTB list"

# A second run is a no-op: the stamp matches.
assert_contains "regen idempotence" "$(run_update)" "already current"

# The snapshot is boot-time only; a shutdown-style run must never write it.
[[ ! -e "$ESP/KERNEL.BAK" ]] || fail "snapshot: written without --snapshot-prev"

out="$(run_update --snapshot-prev)"
assert_contains "snapshot" "$out" "saved known-good"
# cmp, not $(cat): these are real boot images with null bytes.
cmp -s "$ESP/KERNEL.BAK" "$ESP/KERNEL" || fail "snapshot: spare differs from /KERNEL"
assert_eq "snapshot stamp" "$(cat "$ESP/.armada-bootimg.prev.id")" "$(cat "$ESP/.armada-bootimg.id")"

# Unchanged stamp means no repeat copy (this would be ~68 MB on every boot).
printf 'mutated' > "$ESP/KERNEL"
run_update --snapshot-prev >/dev/null
cmp -s "$ESP/KERNEL.BAK" "$ESP/KERNEL" && fail "snapshot: recopied on an unchanged stamp"

# A new /KERNEL means the spare refreshes to the image that just booted.
printf 'booted-image' > "$ESP/KERNEL"; printf 'NEW-ID' > "$ESP/.armada-bootimg.id"
run_update --snapshot-prev >/dev/null
assert_eq "snapshot refresh" "$(cat "$ESP/KERNEL.BAK")" "booted-image"

# Never leave the staging temp behind.
[[ ! -e "$ESP/KERNEL.TMP" ]] || fail "snapshot: staging temp leaked"

# A failing snapshot must not divert the regen: at shutdown a nonzero exit
# here would make the finalize hook roll back a healthy update.
printf 'X' > "$ESP/KERNEL"; printf 'UNWRITABLE' > "$ESP/.armada-bootimg.id"
chmod a-w "$ESP"
out="$(run_update --snapshot-prev)"
chmod u+w "$ESP"
assert_contains "snapshot failure" "$out" "snapshot failed"
[[ "$out" == *"already current"* || "$out" == *"KERNEL"* ]] ||
    fail "snapshot failure: regen did not continue"

# A stamp that outlived its image must not suppress recreating the spare: a
# manual recovery moves KERNEL.BAK away and leaves the hidden stamp behind.
# Settle /KERNEL first, so the spare's stamp matches and the skip would fire.
run_update >/dev/null
run_update --snapshot-prev >/dev/null
[[ -f "$ESP/KERNEL.BAK" ]] || fail "snapshot: no spare to start the deletion case from"
assert_contains "snapshot skip precondition" "$(run_update --snapshot-prev)" "already current"
rm -f "$ESP/KERNEL.BAK"
run_update --snapshot-prev >/dev/null
[[ -f "$ESP/KERNEL.BAK" ]] || fail "snapshot: a surviving stamp suppressed recreating the spare"

# An ostree= karg that resolves to nothing means the entry does not describe a
# deployment that exists. Baking it would stamp an unbootable /KERNEL current and
# suppress the finalize hook's rollback, so the regen must fail instead.
cp "$BOOT/loader/entries/ostree-1.conf" "$WORK/entry.bak"
sed -i "s|ostree=/ostree/boot.1/default/$CSUM/0|ostree=/ostree/boot.1/default/gone/0|" \
    "$BOOT/loader/entries/ostree-1.conf"
rm -f "$ESP/KERNEL"
out="$(run_update)"
assert_contains "unresolvable ostree= fails closed" "$out" "does not resolve"
[[ ! -f "$ESP/KERNEL" ]] || fail "regen: wrote /KERNEL for a deployment that does not resolve"
cp "$WORK/entry.bak" "$BOOT/loader/entries/ostree-1.conf"

# The regen waits on a lock and then does a slow write; systemd must not kill it
# first. Both stop paths need a timeout above the lock wait plus that write.
lock_wait=$(sed -n 's/.*flock -w \([0-9]*\).*/\1/p' "$UPDATE" | head -1)
[[ -n "$lock_wait" ]] || fail "could not read the regen lock wait"

sync_unit="$ROOT/system_files/usr/lib/systemd/system/armada-bootimg-sync.service"
stop=$(sed -n 's/^TimeoutStopSec=\([0-9]*\)s\?$/\1/p' "$sync_unit" | head -1)
if [[ -z "$stop" ]]; then
    grep -qE '^[[:space:]]*TimeoutStopSec=' "$sync_unit" &&
        fail "sync unit: TimeoutStopSec is not plain seconds, so this check cannot compare it"
    fail "sync unit: no explicit TimeoutStopSec, so the default can kill the regen"
fi
(( stop > lock_wait )) || fail "sync unit: TimeoutStopSec ${stop}s does not exceed the ${lock_wait}s lock wait"
mapfile -t sync_stops < <(sed -n 's/^ExecStop=//p' "$sync_unit")
assert_eq "sync bootimg ordering" "${sync_stops[0]:-}" \
    "/usr/libexec/armada/armada-bootimg-update"
assert_eq "sync ABL ordering" "${sync_stops[1]:-}" \
    "-/usr/libexec/armada/armada-abl-finalize"

# OSTree already sets 5m for slow media, and it applies to each ExecStop, so the
# drop-in must never set a smaller value: that would shorten the regen's window.
dropin="$ROOT/system_files/usr/lib/systemd/system/ostree-finalize-staged.service.d/10-armada-bootimg.conf"
if grep -qE '^[[:space:]]*TimeoutStopSec=' "$dropin"; then
    fail "finalize drop-in: sets TimeoutStopSec; it must inherit OSTree's 5m so the two cannot drift"
fi
mapfile -t finalize_stops < <(sed -n 's/^ExecStop=//p' "$dropin")
assert_eq "finalize bootimg ordering" "${finalize_stops[0]:-}" \
    "/usr/libexec/armada/armada-bootimg-finalize"
[[ "${#finalize_stops[@]}" -eq 1 ]] ||
    fail "finalize drop-in: ABL must run only from the shutdown sync unit"
[[ -x "$ROOT/system_files/usr/libexec/armada/armada-abl-finalize" ]] ||
    fail "finalize ABL helper is not executable"

# --- initramfs ostree fallback ----------------------------------------------

FB="$WORK/fallback"; mkdir -p "$FB"
sed -e "s|/sysroot|$FB/sysroot|g" -e "s|/proc/cmdline|$FB/cmdline|" \
    -e "s|/run/armada|$FB/run/armada|g" \
    -e 's|log() {.*|log() { echo "LOG: $*"; }|' "$FALLBACK" > "$FB/fb.sh"

# The rescue must never write to the deployment tree: /KERNEL is the artifact
# that is wrong, and ostree owns everything under /sysroot/ostree.
cat > "$FB/mount" <<EOF
#!/usr/bin/env bash
echo "BIND \$*"
# Capture the bound content: the module unlinks the source right after binding,
# and a real bind would keep it readable through the target.
[[ "\$1" == "--bind" ]] && cp "\$2" "$FB/bound" 2>/dev/null
exit 0
EOF
chmod +x "$FB/mount"
printf '#!/usr/bin/env bash\necho "UMOUNT $*"\nexit 0\n' > "$FB/umount"; chmod +x "$FB/umount"
sysroot_fingerprint() { find "$FB/sysroot" -printf '%p %y %l\n' 2>/dev/null | sort; }

# ostree alternates boot.0/boot.1 and deletes the old tree, so a /KERNEL that
# was not regenerated in the same shutdown bakes a path that no longer exists.
strand_tree() {
    rm -rf "$FB/sysroot" "$FB/run" "$FB/bound"
    mkdir -p "$FB/sysroot/ostree/boot.0.1/default/$2" "$FB/sysroot/ostree/deploy/default/deploy/d.0"
    ln -sfn boot.0.1 "$FB/sysroot/ostree/boot.0"
    ln -sfn ../../../deploy/default/deploy/d.0 "$FB/sysroot/ostree/boot.0.1/default/$2/$3"
    printf '%s\n' "$1" > "$FB/cmdline"
}
run_fb() { PATH="$FB:$PATH" bash "$FB/fb.sh" 2>&1; }
fixed_cmdline() { cat "$FB/bound" 2>/dev/null || true; }

# Bootversion swapped out from under the baked path.
strand_tree "ostree=/ostree/boot.1/default/csum/0 rw quiet" csum 0
before="$(sysroot_fingerprint)"
out="$(run_fb)"
assert_eq "fallback swapped bootversion" "$(fixed_cmdline)" "ostree=/ostree/boot.0/default/csum/0 rw quiet"
assert_contains "fallback binds over cmdline" "$out" "BIND --bind $FB/run/armada/cmdline $FB/cmdline"
# /proc/cmdline is normally immutable, so the replacement must not be writable.
assert_contains "fallback binds read-only" "$out" "BIND -o remount,bind,ro $FB/cmdline"
# Read-only on the target does not make the source read-only, so the writable
# alias has to be gone: writing it would still change what /proc/cmdline shows.
[[ ! -e "$FB/run/armada/cmdline" ]] || fail "fallback: left a writable alias at /run/armada/cmdline"
# A marker records that the rescue fired, and gates putting the real cmdline back.
[[ -s "$FB/run/armada/ostree-fallback-remapped" ]] || fail "fallback: no remap marker"
# /proc/cmdline is conventionally the bootloader's, and the stale value is the
# evidence the device was rescued, so the replacement is dropped once it is used.
assert_contains "fallback restores the real cmdline" "$(PATH="$FB:$PATH" bash "$FB/fb.sh" --restore 2>&1)" \
    "UMOUNT $FB/cmdline"
assert_eq "fallback leaves the deployment tree alone" "$(sysroot_fingerprint)" "$before"

# Same bootversion, but the deployment moved index (a rollback reorder).
strand_tree "ostree=/ostree/boot.0/default/csum/0 rw" csum 1
before="$(sysroot_fingerprint)"
run_fb >/dev/null
assert_eq "fallback moved index" "$(fixed_cmdline)" "ostree=/ostree/boot.0/default/csum/1 rw"
assert_eq "fallback moved index leaves tree alone" "$(sysroot_fingerprint)" "$before"

# Every other karg must survive the rewrite untouched.
strand_tree "root=UUID=r ostree=/ostree/boot.1/default/csum/0 rootwait quiet loglevel=3" csum 0
run_fb >/dev/null
assert_eq "fallback preserves other kargs" "$(fixed_cmdline)" \
    "root=UUID=r ostree=/ostree/boot.0/default/csum/0 rootwait quiet loglevel=3"

# An unwritable marker must abort the remap: --restore keys off the marker, so a
# replacement mounted without one would persist across switch-root.
strand_tree "ostree=/ostree/boot.1/default/csum/0" csum 0
mkdir -p "$FB/run/armada/ostree-fallback-remapped"   # blocks the marker write
out="$(run_fb)"
assert_contains "unwritable marker aborts" "$out" "could not write the restore marker"
[[ "$out" != *"BIND --bind"* ]] || fail "fallback: bound the replacement with no restore marker"
[[ ! -e "$FB/run/armada/cmdline" ]] || fail "fallback: left the staged cmdline after aborting"

# A failed bind must not leave a marker claiming there is something to restore.
strand_tree "ostree=/ostree/boot.1/default/csum/0" csum 0
printf '#!/usr/bin/env bash\nexit 1\n' > "$FB/mount"; chmod +x "$FB/mount"
run_fb >/dev/null
[[ ! -e "$FB/run/armada/ostree-fallback-remapped" ]] || fail "fallback: stale marker after a failed bind"
cat > "$FB/mount" <<EOF
#!/usr/bin/env bash
echo "BIND \$*"
[[ "\$1" == "--bind" ]] && cp "\$2" "$FB/bound" 2>/dev/null
exit 0
EOF
chmod +x "$FB/mount"

# --restore without a marker must do nothing: no rescue happened this boot.
strand_tree "ostree=/ostree/boot.0/default/csum/0" csum 0
assert_eq "restore without a marker" "$(PATH="$FB:$PATH" bash "$FB/fb.sh" --restore 2>&1)" ""

# A healthy boot must be a silent no-op that stages nothing.
strand_tree "ostree=/ostree/boot.0/default/csum/0" csum 0
assert_eq "fallback healthy boot" "$(run_fb)" ""
assert_eq "fallback healthy boot stages nothing" "$(fixed_cmdline)" ""

# Nothing to remap onto: exit cleanly and let ostree-prepare-root fail normally.
strand_tree "ostree=/ostree/boot.1/default/gone/0" other 0
before="$(sysroot_fingerprint)"
out="$(run_fb)" || fail "fallback: nonzero exit with no rescue available"
assert_contains "fallback unfixable" "$out" "no surviving bootlink"
assert_eq "fallback unfixable stages nothing" "$(fixed_cmdline)" ""
assert_eq "fallback unfixable leaves tree alone" "$(sysroot_fingerprint)" "$before"

# Malformed and absent kargs must not crash the initramfs.
strand_tree "ostree=/ostree/boot.1/default/csum/0/extra" csum 0
assert_contains "fallback malformed karg" "$(run_fb)" "unparseable"
strand_tree "quiet ro" csum 0
assert_eq "fallback absent karg" "$(run_fb)" ""

# A karg containing a glob character must not be expanded during the rewrite.
# Run where a matching file exists, or the glob has nothing to expand to and the
# assertion passes whether or not noglob is set.
strand_tree "ostree=/ostree/boot.1/default/csum/0 weird=*" csum 0
mkdir -p "$FB/globdir" && : > "$FB/globdir/weird=EXPANDED"
( cd "$FB/globdir" && run_fb >/dev/null )
assert_eq "fallback noglob" "$(fixed_cmdline)" "ostree=/ostree/boot.0/default/csum/0 weird=*"

# An unavailable overmount is reported, not fatal.
strand_tree "ostree=/ostree/boot.1/default/csum/0" csum 0
printf '#!/usr/bin/env bash\nexit 1\n' > "$FB/mount"; chmod +x "$FB/mount"
out="$(run_fb)" || fail "fallback: nonzero exit when the overmount fails"
assert_contains "fallback overmount failure" "$out" "could not overmount"

# --- dracut module wiring ----------------------------------------------------

# Everything above drives the script directly, so nothing would notice if the
# module stopped installing the hooks that run it, or a binary it needs.
MODSETUP="$ROOT/system_files/usr/lib/dracut/modules.d/91armada-ostree-fallback/module-setup.sh"

dropin_fmt=$(sed -n "s/^[[:space:]]*printf '\(\[Service\][^']*\)'.*/\1/p" "$MODSETUP" | head -1)
[[ -n "$dropin_fmt" ]] || fail "module-setup: generates no [Service] drop-in, so neither hook is wired"
dropin=$(printf '%b' "$dropin_fmt")
assert_contains "drop-in pre-hook" "$dropin" \
    "ExecStartPre=/usr/libexec/armada/armada-ostree-fallback"
assert_contains "drop-in restore hook" "$dropin" \
    "ExecStartPost=/usr/libexec/armada/armada-ostree-fallback --restore"

# A binary the module fails to declare is absent from the initramfs even though
# the host running this test has it, so only the declaration can be checked here.
declared=" $(sed -n 's/^[[:space:]]*inst_multiple[[:space:]]*//p' "$MODSETUP" | tr '\n' ' ') "
for bin in mkdir mount umount rm; do
    case "$declared" in
        *" $bin "*) ;;
        *) fail "module-setup: does not install ${bin}, which the fallback runs" ;;
    esac
done

printf 'boot image regeneration test passed\n'
