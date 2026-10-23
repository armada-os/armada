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
old_deploy=${sysroot}/ostree/deploy/default/deploy/old.0
bootdir=${boot}/ostree/default-test
old_bootdir=${boot}/ostree/default-old

mkdir -p "${esp}" "${boot}/loader/entries" "${deploy}/usr/lib/systemd/boot/efi" \
    "${deploy}/usr/lib/dtbloader" "${deploy}/usr/libexec/armada" \
    "${old_deploy}/usr" "${bootdir}/dtb/qcom" "${old_bootdir}/dtb/qcom"
cp "${UPDATE}" "${deploy}/usr/libexec/armada/armada-efi-update"
printf loader > "${deploy}/usr/lib/systemd/boot/efi/systemd-bootaa64.efi"
printf dtbloader > "${deploy}/usr/lib/dtbloader/dtbloaderaa64.efi"
printf thor > "${bootdir}/dtb/qcom/qcs8550-ayn-thor.dtb"
printf x13s > "${bootdir}/dtb/qcom/sc8280xp-lenovo-thinkpad-x13s.dtb"
printf kernel > "${bootdir}/vmlinuz"
printf initrd > "${bootdir}/initramfs"
printf thor-old > "${old_bootdir}/dtb/qcom/qcs8550-ayn-thor.dtb"
printf kernel-old > "${old_bootdir}/vmlinuz"
printf initrd-old > "${old_bootdir}/initramfs"

printf kernel > "${esp}/KERNEL"
mkdir -p "${esp}/EFI.disabled" "${esp}/EFI/fedora" "${esp}/EFI/BOOT" "${esp}/ostree/stale" \
    "${esp}/loader/entries" "${esp}/dtbs/qcom"
printf stale > "${esp}/EFI/fedora/shim.efi"
printf stale > "${esp}/EFI/BOOT/grubaa64.efi"
printf stale > "${esp}/loader/entries/stale.conf"
printf stale > "${esp}/dtbs/qcom/removed-device.dtb"

cat > "${boot}/loader/entries/ostree-2.conf" <<EOF
title current
version 2
options quiet ostree=/ostree/deploy/default/deploy/test.0
linux /boot/ostree/default-test/vmlinuz
initrd /boot/ostree/default-test/initramfs
fdtdir /ostree/default-test/dtb
EOF
cat > "${boot}/loader/entries/ostree-1.conf" <<EOF
title old
version 1
options quiet ostree=/ostree/deploy/default/deploy/old.0
linux /boot/ostree/default-old/vmlinuz
initrd /boot/ostree/default-old/initramfs
fdtdir /ostree/default-old/dtb
EOF

mkdir "${work}/bin"
printf '#!/bin/sh\nexit 0\n' > "${work}/bin/findmnt"
chmod +x "${work}/bin/findmnt"
run() {
    PATH=${work}/bin:${PATH} ESP=${esp} BOOTROOT=${boot} SYSROOT=${sysroot} \
        ARGS_FILE=${ROOT}/system_files/usr/lib/armada/bootimg-args "${UPDATE}"
}

run > "${work}/log"
grep -Fq 'armada-efi-update: synced' "${work}/log"
cmp "${deploy}/usr/lib/systemd/boot/efi/systemd-bootaa64.efi" "${esp}/EFI/BOOT/BOOTAA64.EFI"
cmp "${deploy}/usr/lib/systemd/boot/efi/systemd-bootaa64.efi" "${esp}/EFI/systemd/systemd-bootaa64.efi"
cmp "${deploy}/usr/lib/dtbloader/dtbloaderaa64.efi" "${esp}/EFI/systemd/drivers/dtbloaderaa64.efi"
cmp "${bootdir}/vmlinuz" "${esp}/ostree/default-test/vmlinuz"
cmp "${old_bootdir}/initramfs" "${esp}/ostree/default-old/initramfs"
cmp "${bootdir}/dtb/qcom/sc8280xp-lenovo-thinkpad-x13s.dtb" \
    "${esp}/dtbs/qcom/sc8280xp-lenovo-thinkpad-x13s.dtb"
test ! -e "${esp}/dtbs/qcom/removed-device.dtb"
printf 'default ostree-2.conf\ntimeout menu-hidden\neditor no\n' | cmp - "${esp}/loader/loader.conf"
grep -Fxq 'linux /ostree/default-test/vmlinuz' "${esp}/loader/entries/ostree-2.conf"
grep -Fxq 'initrd /ostree/default-old/initramfs' "${esp}/loader/entries/ostree-1.conf"
grep -Fxq 'fdtdir /ostree/default-test/dtb' "${esp}/loader/entries/ostree-2.conf"
test ! -e "${esp}/loader/entries/stale.conf"
test ! -e "${esp}/ostree/stale"
test ! -e "${esp}/EFI/fedora"
test ! -e "${esp}/EFI/BOOT/grubaa64.efi"
test ! -e "${esp}/EFI.disabled"
test -s "${esp}/KERNEL"
[ -z "$(find "${esp}" -name "*.new")" ]

# A second run with nothing changed copies nothing.
run > "${work}/log"
test ! -s "${work}/log"

# Without enough space, nothing is replaced.
printf kernel-new > "${bootdir}/vmlinuz"
cat > "${work}/bin/df" <<'EOF'
#!/bin/sh
printf 'Avail\n1\n'
EOF
chmod +x "${work}/bin/df"
if run 2> "${work}/error"; then exit 1; fi
grep -Fq 'insufficient space' "${work}/error"
printf kernel | cmp - "${esp}/ostree/default-test/vmlinuz"
rm "${work}/bin/df"

# Rolling back to a release without EFI sync falls back to /KERNEL.
sed -i 's/^version 2$/version 0/' "${boot}/loader/entries/ostree-2.conf"
run > "${work}/log"
grep -Fq 'disabled EFI for older deployment old.0' "${work}/log"
test ! -e "${esp}/EFI/BOOT/BOOTAA64.EFI"
test ! -e "${esp}/EFI/systemd/systemd-bootaa64.efi"
test ! -e "${esp}/loader"
test ! -e "${esp}/ostree"
test -s "${esp}/KERNEL"

# Moving forward again restores the EFI boot files.
sed -i 's/^version 0$/version 2/' "${boot}/loader/entries/ostree-2.conf"
run > "${work}/log"
test -s "${esp}/EFI/BOOT/BOOTAA64.EFI"
test -s "${esp}/loader/entries/ostree-2.conf"
cmp "${bootdir}/vmlinuz" "${esp}/ostree/default-test/vmlinuz"

# A broken default entry fails before touching the ESP.
rm "${bootdir}/initramfs"
if run 2> "${work}/error"; then exit 1; fi
grep -Fq 'missing or empty initrd' "${work}/error"
