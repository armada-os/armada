#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
UPDATE=${ROOT}/system_files/usr/libexec/armada/armada-efi-update
work=$(mktemp -d)
trap 'rm -rf "${work}"' EXIT
esp=${work}/esp
boot=${work}/boot
sysroot=${work}/sysroot
deploy=${sysroot}/ostree/deploy/default/deploy/test.0
rollback_deploy=${sysroot}/ostree/deploy/default/deploy/rollback.0
bootdir=${boot}/ostree/default-test
rollback_bootdir=${boot}/ostree/default-rollback
mkdir -p "${esp}/armada" "${boot}/loader/entries" "${deploy}/usr/lib/systemd/boot/efi" \
    "${deploy}/usr/share/edk2/drivers" "${deploy}/usr/lib/armada/efi/drivers" \
    "${deploy}/usr/lib/armada" "${rollback_deploy}/usr/lib/armada" \
    "${bootdir}/dtb/qcom" "${rollback_bootdir}/dtb/qcom"
printf kernel > "${esp}/KERNEL"
mkdir -p "${esp}/EFI.disabled" "${deploy}/usr/libexec/armada" "${rollback_deploy}/usr/libexec/armada"
printf grub > "${esp}/EFI.disabled/old-grub"
for target in "${deploy}" "${rollback_deploy}"; do
    cp "${UPDATE}" "${target}/usr/libexec/armada/armada-efi-update"
    chmod +x "${target}/usr/libexec/armada/armada-efi-update"
    cp "${ROOT}/system_files/usr/libexec/armada/device-env" "${target}/usr/libexec/armada/device-env"
    cp -r "${ROOT}/system_files/usr/lib/armada/devices" "${target}/usr/lib/armada/devices"
done
export LOCK_FILE=${work}/efi.lock
mkdir -p "${esp}/EFI/BOOT/theme" "${esp}/EFI/refind" "${esp}/EFI/systemd/drivers" \
    "${esp}/EFI/fedora" "${boot}/grub2"
printf stale > "${esp}/EFI/BOOT/refind.conf"
printf stale > "${esp}/EFI/BOOT/theme/armada-banner.bmp"
printf stale > "${esp}/EFI/refind/refind_aa64.efi"
printf stale > "${esp}/EFI/fedora/grubaa64.efi"
printf stale > "${esp}/EFI/fedora/shim.efi"
printf stale > "${esp}/EFI/fedora/grub.cfg"
printf stale > "${esp}/EFI/BOOT/fbaa64.efi"
printf stale > "${esp}/EFI/BOOT/BOOTAA64.CSV"
printf stale > "${esp}/EFI/BOOT/grub.cfg"
printf stale > "${esp}/EFI/BOOT/grubaa64.efi"
printf stale > "${boot}/grub2/grub.cfg"
printf stale > "${esp}/EFI/systemd/drivers/dtbloaderaa64.efi"
printf stale > "${esp}/EFI/systemd/drivers/adtbloaderaa64.efi"
mkdir -p "${esp}/dtbloader/dtbs/qcom"
printf stale > "${esp}/dtbloader/dtbs/qcom/qcs8550-renamed-device.dtb"
printf keep > "${esp}/dtbloader/dtbs/qcom/README"
printf loader > "${deploy}/usr/lib/systemd/boot/efi/systemd-bootaa64.efi"
printf ext4 > "${deploy}/usr/share/edk2/drivers/ext4aa64.efi"
printf adtbloader > "${deploy}/usr/lib/armada/efi/drivers/adtbloaderaa64.efi"
printf armada-boot > "${deploy}/usr/lib/armada/efi/armada-boot.efi"
printf '20260930.current\n' > "${deploy}/usr/lib/armada/version"
printf '20260924.previous\n' > "${rollback_deploy}/usr/lib/armada/version"
printf thor > "${bootdir}/dtb/qcom/qcs8550-ayn-thor.dtb"
printf new > "${bootdir}/dtb/qcom/qcs8550-new-device.dtb"
printf x1e > "${bootdir}/dtb/qcom/x1e-test.dtb"
printf kernel > "${bootdir}/vmlinuz"
printf initrd > "${bootdir}/initramfs"
printf thor-old > "${rollback_bootdir}/dtb/qcom/qcs8550-ayn-thor.dtb"
printf kernel-old > "${rollback_bootdir}/vmlinuz"
printf initrd-old > "${rollback_bootdir}/initramfs"
mkdir -p "${esp}/ostree/stale" "${esp}/loader/entries"
printf stale > "${esp}/loader/entries/stale.conf"
printf 'qcs8550-ayn-thor\nqcs8550-new-device\n' > "${deploy}/usr/lib/armada/supported-dtbs"
for name in rotation-evo rotation-odin3 rotation-rp6-top; do
    printf dtb > "${bootdir}/dtb/qcom/${name}.dtb"
    printf '%s\n' "${name}" >> "${deploy}/usr/lib/armada/supported-dtbs"
done
cat > "${boot}/loader/entries/ostree-1.conf" <<EOF
title old
version 2
options ostree=/ostree/deploy/default/deploy/test.0
linux /boot/ostree/default-test/vmlinuz
initrd /boot/ostree/default-test/initramfs
fdtdir /ostree/default-test/dtb
EOF
cat > "${boot}/loader/entries/ostree-rollback.conf" <<EOF
title old rollback
version 1
options ostree=/ostree/deploy/default/deploy/rollback.0
linux /boot/ostree/default-rollback/vmlinuz
initrd /boot/ostree/default-rollback/initramfs
fdtdir /ostree/default-rollback/dtb
EOF
mkdir "${work}/bin"
printf '#!/bin/sh\nexit 0\n' > "${work}/bin/findmnt"
cat > "${work}/bin/fdtget" <<'EOF'
#!/bin/sh
case "$3" in
    *qcs8550-ayn-thor.dtb) printf 'AYN Thor\n' ;;
    *qcs8550-new-device.dtb) printf 'New Handheld\n' ;;
    *rotation-evo.dtb) printf 'AYANEO Pocket EVO\n' ;;
    *rotation-odin3.dtb) printf 'AYN Odin 3\n' ;;
    *rotation-rp6-top.dtb) printf 'Retroid Pocket 6 TOP-DPAD\n' ;;
    *) exit 1 ;;
esac
EOF
chmod +x "${work}/bin/findmnt" "${work}/bin/fdtget"
printf 'quiet armada.device=auto\n' > "${work}/cmdline"

cp "${boot}/loader/entries/ostree-1.conf" "${work}/original-entry"
cp "${boot}/loader/entries/ostree-rollback.conf" "${work}/original-rollback"

PATH=${work}/bin:${PATH} ESP=${esp} BOOTROOT=${boot} SYSROOT=${sysroot} \
    CMDLINE=${work}/cmdline \
    ARGS_FILE=${ROOT}/system_files/usr/lib/armada/bootimg-args "${UPDATE}"

cmp "${deploy}/usr/lib/armada/efi/armada-boot.efi" "${esp}/EFI/BOOT/BOOTAA64.EFI"
cmp "${deploy}/usr/lib/armada/efi/armada-boot.efi" "${esp}/EFI/Microsoft/Boot/bootmgfw.efi"
! test -e "${esp}/EFI/BOOT/refind.conf"
! test -e "${esp}/EFI/BOOT/theme"
! test -e "${esp}/EFI/refind"
! test -e "${esp}/EFI/fedora"
! test -e "${esp}/EFI/BOOT/fbaa64.efi"
! test -e "${esp}/EFI/BOOT/BOOTAA64.CSV"
! test -e "${esp}/EFI/BOOT/grub.cfg"
! test -e "${esp}/EFI/BOOT/grubaa64.efi"
test -d "${boot}/grub2"
! test -e "${esp}/EFI.disabled"
cmp "${deploy}/usr/share/edk2/drivers/ext4aa64.efi" "${esp}/EFI/systemd/drivers/ext4aa64.efi"
cmp "${deploy}/usr/lib/armada/efi/drivers/adtbloaderaa64.efi" \
    "${esp}/EFI/BOOT/drivers_aa64/adtbloaderaa64.efi"
! test -e "${esp}/EFI/systemd/drivers/adtbloaderaa64.efi"
! test -e "${esp}/EFI/systemd/drivers/dtbloaderaa64.efi"
cmp "${bootdir}/dtb/qcom/qcs8550-ayn-thor.dtb" \
    "${esp}/dtbloader/dtbs/qcom/qcs8550-ayn-thor.dtb"
cmp "${bootdir}/dtb/qcom/x1e-test.dtb" "${esp}/dtbloader/dtbs/qcom/x1e-test.dtb"
! test -e "${esp}/dtbloader/dtbs/qcom/qcs8550-renamed-device.dtb"
grep -Fxq keep "${esp}/dtbloader/dtbs/qcom/README"
grep -qx 'title Armada OS (Automatic)' "${esp}/loader/entries/ostree-1.conf"
grep -qx 'title Armada OS - AYN Thor' "${esp}/loader/entries/ostree-1-dtb-qcs8550-ayn-thor.conf"
grep -qx 'title Armada OS - New Handheld' \
    "${esp}/loader/entries/ostree-1-dtb-qcs8550-new-device.conf"
grep -q '^options armada.device=qcs8550-ayn-thor ' \
    "${esp}/loader/entries/ostree-1-dtb-qcs8550-ayn-thor.conf"
grep -qx 'devicetree /ostree/default-test/dtb/qcom/qcs8550-ayn-thor.dtb' \
    "${esp}/loader/entries/ostree-1-dtb-qcs8550-ayn-thor.conf"
! test -e "${esp}/loader/entries/ostree-1-dtb-x1e-test.conf"
grep -qx 'title Armada OS (Previous Version)' "${esp}/loader/entries/ostree-rollback.conf"
grep -q '^options armada.device=auto ' "${esp}/loader/entries/ostree-rollback.conf"
! grep -q '^architecture armada-hidden$' "${esp}/loader/entries/ostree-rollback.conf"
! grep -q '^fdtdir ' "${esp}/loader/entries/ostree-rollback.conf"
! test -e "${esp}/loader/entries/ostree-rollback-dtb-qcs8550-ayn-thor.conf"
! test -e "${esp}/loader/entries/ostree-rollback-dtb-qcs8550-new-device.conf"
grep -q '^options armada.device=auto ' "${esp}/loader/entries/ostree-1.conf"
grep -qx 'linux /ostree/default-test/vmlinuz' "${esp}/loader/entries/ostree-1.conf"
grep -qx 'initrd /ostree/default-test/initramfs' "${esp}/loader/entries/ostree-1.conf"
! grep -q '^fdtdir ' "${esp}/loader/entries/ostree-1.conf"
! grep -q '^ARMADA_BOOT_' "${esp}/armada/backend.conf"
grep -qx 'ARMADA_DEFAULT_VERSION=20260930.current' "${esp}/armada/backend.conf"
grep -Fxq 'ARMADA_EFI_ROTATION=AYANEO Pocket EVO:90' "${esp}/armada/backend.conf"
grep -Fxq 'ARMADA_EFI_ROTATION=AYN Odin 3:270' "${esp}/armada/backend.conf"
grep -Fxq 'ARMADA_EFI_ROTATION=Retroid Pocket 6 TOP-DPAD:90' "${esp}/armada/backend.conf"
! grep -Eq '^ARMADA_EFI_ROTATION=(AYN Thor|New Handheld):' "${esp}/armada/backend.conf"
grep -qx 'ARMADA_ROLLBACK_ENTRY=ostree-rollback.conf' "${esp}/armada/backend.conf"
grep -qx 'ARMADA_ROLLBACK_VERSION=20260924.previous' "${esp}/armada/backend.conf"
grep -qx 'ARMADA_ROLLBACK_DTBS=/ostree/default-rollback/dtb/qcom' "${esp}/armada/backend.conf"
! test -e "${esp}/armada/device"
grep -Fqx 'default ostree-1.conf' "${esp}/loader/loader.conf"
grep -Fxq 'timeout menu-hidden' "${esp}/loader/loader.conf"
cmp "${bootdir}/vmlinuz" "${esp}/ostree/default-test/vmlinuz"
cmp "${bootdir}/initramfs" "${esp}/ostree/default-test/initramfs"
cmp "${work}/original-entry" "${boot}/loader/entries/ostree-1.conf"
cmp "${work}/original-rollback" "${boot}/loader/entries/ostree-rollback.conf"
! compgen -G "${boot}/loader/entries/*-dtb-*.conf" >/dev/null
! test -e "${esp}/ostree/stale"
! test -e "${esp}/loader/entries/stale.conf"

rm "${rollback_deploy}/usr/libexec/armada/armada-efi-update"
PATH=${work}/bin:${PATH} ESP=${esp} BOOTROOT=${boot} SYSROOT=${sysroot} \
    CMDLINE=${work}/cmdline \
    ARGS_FILE=${ROOT}/system_files/usr/lib/armada/bootimg-args "${UPDATE}"
grep -qx 'architecture armada-hidden' "${esp}/loader/entries/ostree-rollback.conf"
! grep -q '^ARMADA_ROLLBACK_' "${esp}/armada/backend.conf"
cp "${UPDATE}" "${rollback_deploy}/usr/libexec/armada/armada-efi-update"
chmod +x "${rollback_deploy}/usr/libexec/armada/armada-efi-update"

printf 'quiet armada.device=qcs8550-ayn-thor\n' > "${work}/cmdline"
PATH=${work}/bin:${PATH} ESP=${esp} BOOTROOT=${boot} SYSROOT=${sysroot} \
    CMDLINE=${work}/cmdline \
    ARGS_FILE=${ROOT}/system_files/usr/lib/armada/bootimg-args "${UPDATE}"
grep -qx 'qcs8550-ayn-thor' "${esp}/armada/device"
grep -Fqx 'default ostree-1.conf' "${esp}/loader/loader.conf"
grep -Fxq 'timeout menu-hidden' "${esp}/loader/loader.conf"
grep -qx 'title Armada OS' "${esp}/loader/entries/ostree-1.conf"
grep -q '^options armada.device=qcs8550-ayn-thor ' "${esp}/loader/entries/ostree-1.conf"
grep -qx 'devicetree /ostree/default-test/dtb/qcom/qcs8550-ayn-thor.dtb' \
    "${esp}/loader/entries/ostree-1.conf"
grep -qx 'title Armada OS (Previous Version)' "${esp}/loader/entries/ostree-rollback.conf"
grep -q '^options armada.device=qcs8550-ayn-thor ' \
    "${esp}/loader/entries/ostree-rollback.conf"
grep -qx 'devicetree /ostree/default-rollback/dtb/qcom/qcs8550-ayn-thor.dtb' \
    "${esp}/loader/entries/ostree-rollback.conf"
! grep -q '^architecture armada-hidden$' "${esp}/loader/entries/ostree-rollback.conf"
! compgen -G "${esp}/loader/entries/*-dtb-*.conf" >/dev/null

rm "${rollback_bootdir}/dtb/qcom/qcs8550-ayn-thor.dtb"
PATH=${work}/bin:${PATH} ESP=${esp} BOOTROOT=${boot} SYSROOT=${sysroot} \
    CMDLINE=${work}/cmdline \
    ARGS_FILE=${ROOT}/system_files/usr/lib/armada/bootimg-args "${UPDATE}"
grep -qx 'architecture armada-hidden' "${esp}/loader/entries/ostree-rollback.conf"
cmp "${work}/original-rollback" "${boot}/loader/entries/ostree-rollback.conf"
! grep -q '^ARMADA_ROLLBACK_' "${esp}/armada/backend.conf"

printf 'quiet armada.device=auto\n' > "${work}/cmdline"
rm "${boot}/loader/entries/ostree-rollback.conf"
PATH=${work}/bin:${PATH} ESP=${esp} BOOTROOT=${boot} SYSROOT=${sysroot} \
    CMDLINE=${work}/cmdline \
    ARGS_FILE=${ROOT}/system_files/usr/lib/armada/bootimg-args "${UPDATE}"
! test -e "${esp}/loader/entries/ostree-rollback.conf"
! grep -q '^ARMADA_ROLLBACK_' "${esp}/armada/backend.conf"

rm "${bootdir}/dtb/qcom/qcs8550-new-device.dtb"
if PATH=${work}/bin:${PATH} ESP=${esp} BOOTROOT=${boot} SYSROOT=${sysroot} \
    CMDLINE=${work}/cmdline \
    ARGS_FILE=${ROOT}/system_files/usr/lib/armada/bootimg-args "${UPDATE}" 2>"${work}/error"; then
    echo "EFI update accepted a missing DTB in the default deployment" >&2
    exit 1
fi
grep -Fq "missing DTB: ${bootdir}/dtb/qcom/qcs8550-new-device.dtb" "${work}/error"

cmp "${work}/original-entry" "${boot}/loader/entries/ostree-1.conf"
[ "$(cat "${esp}/KERNEL")" = kernel ]

printf new > "${bootdir}/dtb/qcom/qcs8550-new-device.dtb"
run_update() {
    PATH=${work}/bin:${PATH} ESP=${esp} BOOTROOT=${boot} SYSROOT=${sysroot} \
        CMDLINE=${work}/cmdline ARGS_FILE=${ROOT}/system_files/usr/lib/armada/bootimg-args "${UPDATE}"
}
run_update
cmp "${work}/original-entry" "${boot}/loader/entries/ostree-1.conf"

profile=${deploy}/usr/lib/armada/devices/ayaneo-pocket-evo.conf
sed -i 's/ARMADA_EFI_ROTATION=90/ARMADA_EFI_ROTATION=180/' "${profile}"
run_update
grep -Fxq 'ARMADA_EFI_ROTATION=AYANEO Pocket EVO:180' "${esp}/armada/backend.conf"
sed -i 's/ARMADA_EFI_ROTATION=180/ARMADA_EFI_ROTATION=45/' "${profile}"
run_update
! grep -q '^ARMADA_EFI_ROTATION=AYANEO Pocket EVO:' "${esp}/armada/backend.conf"
sed -i '/^ARMADA_EFI_ROTATION=/d' "${profile}"
run_update
! grep -q '^ARMADA_EFI_ROTATION=AYANEO Pocket EVO:' "${esp}/armada/backend.conf"
cp "${ROOT}/system_files/usr/lib/armada/devices/ayaneo-pocket-evo.conf" "${profile}"
mv "${deploy}/usr/libexec/armada/device-env" "${work}/device-env"
run_update
! grep -q '^ARMADA_EFI_ROTATION=' "${esp}/armada/backend.conf"
mv "${work}/device-env" "${deploy}/usr/libexec/armada/device-env"
run_update
grep -Fxq 'ARMADA_EFI_ROTATION=AYANEO Pocket EVO:90' "${esp}/armada/backend.conf"

# A new kernel deployment changes both BLS paths; EFI must follow without touching the originals.
cp -r "${deploy}" "${deploy%/*}/next.0"
cp -r "${bootdir}" "${boot}/ostree/default-next"
sed -i -e 's|test.0|next.0|' -e 's|default-test|default-next|g' \
    "${boot}/loader/entries/ostree-1.conf"
printf next-kernel > "${boot}/ostree/default-next/vmlinuz"
run_update
cmp "${boot}/ostree/default-next/vmlinuz" "${esp}/ostree/default-next/vmlinuz"
grep -q 'ostree=/ostree/deploy/default/deploy/next.0' "${esp}/loader/entries/ostree-1.conf"
cp "${work}/original-entry" "${boot}/loader/entries/ostree-1.conf"
run_update
grep -q 'ostree=/ostree/deploy/default/deploy/test.0' "${esp}/loader/entries/ostree-1.conf"

# The first EFI install must fail before exposing loaders when the FAT partition is full.
rm -rf "${esp}/EFI"
cat > "${work}/bin/df" <<'EOF'
#!/bin/sh
printf 'Avail\n0\n'
EOF
chmod +x "${work}/bin/df"
if run_update; then
    echo 'EFI setup accepted a full partition' >&2
    exit 1
fi
! test -e "${esp}/EFI/BOOT/BOOTAA64.EFI"
! test -e "${esp}/EFI/systemd/systemd-bootaa64.efi"
[ "$(cat "${esp}/KERNEL")" = kernel ]
rm "${work}/bin/df"

cat > "${work}/bin/cp" <<'EOF'
#!/bin/sh
case "$*" in *drivers_aa64*) printf partial > "$3"; exit 1 ;; esac
exec /usr/bin/cp "$@"
EOF
chmod +x "${work}/bin/cp"
if run_update 2>"${work}/error"; then
    echo 'EFI setup ignored an interrupted copy' >&2
    exit 1
fi
grep -Fq "could not stage ${deploy}/usr/lib/armada/efi/drivers/adtbloaderaa64.efi" "${work}/error"
! test -e "${esp}/EFI/BOOT/BOOTAA64.EFI"
! test -e "${esp}/EFI/systemd/systemd-bootaa64.efi"
rm "${work}/bin/cp"
test -s "${esp}/EFI/BOOT/drivers_aa64/adtbloaderaa64.efi.new"
cat > "${work}/bin/df" <<'EOF'
#!/bin/sh
if [ -e "${ESP}/EFI/BOOT/drivers_aa64/adtbloaderaa64.efi.new" ]; then
    printf 'Avail\n0\n'
else
    exec /usr/bin/df "$@"
fi
EOF
chmod +x "${work}/bin/df"
run_update
rm "${work}/bin/df"
! test -e "${esp}/EFI/BOOT/drivers_aa64/adtbloaderaa64.efi.new"
cmp "${deploy}/usr/lib/armada/efi/armada-boot.efi" "${esp}/EFI/BOOT/BOOTAA64.EFI"

# Old deployments must boot /KERNEL rather than leave stale EFI files in control.
rm "${deploy}/usr/libexec/armada/armada-efi-update"
run_update
for file in EFI/BOOT/BOOTAA64.EFI EFI/Microsoft/Boot/bootmgfw.efi EFI/systemd/systemd-bootaa64.efi; do
    ! test -e "${esp}/${file}"
done
[ "$(cat "${esp}/KERNEL")" = kernel ]
cp "${UPDATE}" "${deploy}/usr/libexec/armada/armada-efi-update"
chmod +x "${deploy}/usr/libexec/armada/armada-efi-update"
run_update
cmp "${deploy}/usr/lib/armada/efi/armada-boot.efi" "${esp}/EFI/BOOT/BOOTAA64.EFI"
cmp "${work}/original-entry" "${boot}/loader/entries/ostree-1.conf"
