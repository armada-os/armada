#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
GADGET="$ROOT/system_files/usr/libexec/armada/mtp-gadget"
UNIT="$ROOT/system_files/usr/lib/systemd/system/armada-mtp.service"
CONTROL="$ROOT/system_files/usr/libexec/armada/armada-control"
STORAGE_LIB="$ROOT/system_files/usr/lib/armada/storage-lib"
INSTALLER_VISIBILITY="$ROOT/system_files/usr/libexec/armada/installer-visibility"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

bash -n "$GADGET"
bash -n "$STORAGE_LIB"
bash -n "$INSTALLER_VISIBILITY"
grep -Fq 'storage "/var/home/armada" "Home" "rw"' "$GADGET"
grep -Fq 'source /usr/lib/armada/storage-lib' "$GADGET"
grep -Fq 'armada_running_from_internal && sd_source=$(armada_mounted_sd)' "$GADGET"
grep -Fq 'ln -sfn -- "$sd_source" "$sd_link"' "$GADGET"
grep -Fq 'storage "/run/armada-mtp/sdcard" "SD Card" "rw,removable"' "$GADGET"
# A bind mount pins the card and defeats safe ejection.
! grep -Fq 'mount --bind' "$GADGET"
grep -Fq 'show_hidden_files 0' "$GADGET"
grep -Fq 'armada_running_from_internal && exit 0' "$INSTALLER_VISIBILITY"
grep -Fq 'systemd-id128 machine-id -a' "$GADGET"
! grep -Fq 'serial=armada' "$GADGET"
grep -Fq 'armada_uid="$(id -u armada)"' "$GADGET"
grep -Fq 'stale USB gadget exists' "$GADGET"
grep -Fq 'no USB device controller found' "$GADGET"
grep -Fq 'ExecStartPost=+/usr/libexec/armada/mtp-gadget bind' "$UNIT"
grep -Fq 'ExecStart=/usr/bin/umtprd -conf /run/armada-mtp/umtprd.conf' "$UNIT"
grep -Fq 'ExecStopPost=+/usr/libexec/armada/mtp-gadget teardown' "$UNIT"
! grep -Fq 'PrivateTmp=' "$UNIT"
! grep -Fq '[Install]' "$UNIT"
grep -Fq '"set_mtp_enabled": action_set_mtp_enabled' "$CONTROL"
grep -Fq 'action = "start" if enabled else "stop"' "$CONTROL"
! grep -Fq 'action, "--now", "armada-mtp.service"' "$CONTROL"
# Defense in depth if the unit becomes enableable again.
grep -Fq 'systemctl disable armada-mtp.service' "$ROOT/build_files/40-vendor-system-files.sh"
grep -Fq 'umtp-responder@sha256:' "$ROOT/Containerfile"

(
    source "$STORAGE_LIB"
    ARMADA_INTERNAL_DEVICE=/dev/internal-link
    findmnt() { printf '/dev/sda3[/root]\n'; }
    readlink() {
        [[ "${*: -1}" == /dev/internal-link ]] && printf '/dev/sda\n' || printf '%s\n' "${*: -1}"
    }
    lsblk() { printf 'sda\n'; }
    armada_running_from_internal
)
! (
    source "$STORAGE_LIB"
    ARMADA_INTERNAL_DEVICE=/dev/internal-link
    findmnt() { printf '/dev/mmcblk0p3[/root]\n'; }
    readlink() {
        [[ "${*: -1}" == /dev/internal-link ]] && printf '/dev/sda\n' || printf '%s\n' "${*: -1}"
    }
    lsblk() { printf 'mmcblk0\n'; }
    armada_running_from_internal
)
! (
    source "$STORAGE_LIB"
    armada_internal_device() { return 1; }
    armada_running_from_internal
)

one="$WORK/one"
one_mount="$one/media/My Card"
mkdir -p "$one/block/mmcblk0/device" "$one/block/mmcblk0p1" "$one_mount"
printf 'SD\n' > "$one/block/mmcblk0/device/type"
(
    source "$STORAGE_LIB"
    ARMADA_BLOCK_CLASS="$one/block"
    ARMADA_MEDIA_ROOT="$one/media"
    runuser() { return 0; }
    findmnt() {
        local node=
        while (($#)); do
            if [[ "$1" == -S ]]; then node="$2"; shift 2; else shift; fi
        done
        case "$node" in
            /dev/mmcblk0p1) printf '{"filesystems":[{"target":"%s","options":"rw,nosuid"}]}\n' "$one_mount" ;;
            *) printf '{"filesystems":[]}\n' ;;
        esac
    }
    [[ "$(armada_mounted_sd)" == "$one_mount" ]]
)

none="$WORK/none"
mkdir -p "$none/block/mmcblk0/device" "$none/media"
printf 'MMC\n' > "$none/block/mmcblk0/device/type"
! (
    source "$STORAGE_LIB"
    ARMADA_BLOCK_CLASS="$none/block"
    ARMADA_MEDIA_ROOT="$none/media"
    armada_mounted_sd
)

two="$WORK/two"
two_mount_a="$two/media/Card One"
two_mount_b="$two/media/Card Two"
mkdir -p "$two/block/mmcblk0/device" "$two/block/mmcblk0p1" "$two/block/mmcblk0p2" \
    "$two_mount_a" "$two_mount_b"
printf 'SD\n' > "$two/block/mmcblk0/device/type"
! (
    source "$STORAGE_LIB"
    ARMADA_BLOCK_CLASS="$two/block"
    ARMADA_MEDIA_ROOT="$two/media"
    runuser() { return 0; }
    findmnt() {
        local node=
        while (($#)); do
            if [[ "$1" == -S ]]; then node="$2"; shift 2; else shift; fi
        done
        case "$node" in
            /dev/mmcblk0p1) printf '{"filesystems":[{"target":"%s","options":"rw"}]}\n' "$two_mount_a" ;;
            /dev/mmcblk0p2) printf '{"filesystems":[{"target":"%s","options":"rw"}]}\n' "$two_mount_b" ;;
            *) printf '{"filesystems":[]}\n' ;;
        esac
    }
    armada_mounted_sd
)

! (
    source "$STORAGE_LIB"
    ARMADA_BLOCK_CLASS="$one/block"
    ARMADA_MEDIA_ROOT="$one/media"
    runuser() { return 1; }
    findmnt() {
        printf '{"filesystems":[{"target":"%s","options":"rw"}]}\n' "$one_mount"
    }
    armada_mounted_sd
)

! (
    source "$STORAGE_LIB"
    ARMADA_BLOCK_CLASS="$one/block"
    ARMADA_MEDIA_ROOT="$one/media"
    runuser() { return 0; }
    findmnt() {
        printf '{"filesystems":[{"target":"%s","options":"ro,nosuid"}]}\n' "$one_mount"
    }
    armada_mounted_sd
)

printf 'MTP integration test passed\n'
