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
printf stale > "${esp}/loader/entries/armada-stale.conf"
printf other > "${esp}/loader/entries/other-os.conf"
printf stale > "${esp}/dtbs/qcom/removed-device.dtb"

cat > "${boot}/loader/entries/ostree-2.conf" <<EOF
title Armada 20261023.a7ecb8e (ostree:0)
version 2
options quiet ostree=/ostree/deploy/default/deploy/test.0
linux /boot/ostree/default-test/vmlinuz
initrd /boot/ostree/default-test/initramfs
fdtdir /ostree/default-test/dtb
EOF
cat > "${boot}/loader/entries/ostree-1.conf" <<EOF
title Armada 20261023.0b3da6b (ostree:1)
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
printf 'timeout 3\neditor no\ndefault armada-*\n' | cmp - "${esp}/loader/loader.conf"
grep -Fxq 'linux /ostree/default-test/vmlinuz' "${esp}/loader/entries/armada-ostree-2.conf"
grep -Fxq 'initrd /ostree/default-old/initramfs' "${esp}/loader/entries/armada-ostree-1.conf"
grep -Fxq 'fdtdir /ostree/default-test/dtb' "${esp}/loader/entries/armada-ostree-2.conf"
printf 'title Armada\nversion 20261023.a7ecb8e\n' | cmp - <(head -2 "${esp}/loader/entries/armada-ostree-2.conf")
printf 'title Armada (Rollback)\nversion 20261023.0b3da6b\n' | cmp - <(head -2 "${esp}/loader/entries/armada-ostree-1.conf")
grep -Fxq 'version 2' "${boot}/loader/entries/ostree-2.conf"
test ! -e "${esp}/loader/entries/armada-stale.conf"
printf other | cmp - "${esp}/loader/entries/other-os.conf"
test ! -e "${esp}/ostree/stale"
test ! -e "${esp}/EFI/fedora"
test ! -e "${esp}/EFI/BOOT/grubaa64.efi"
test ! -e "${esp}/EFI.disabled"
test -s "${esp}/KERNEL"
[ -z "$(find "${esp}" -name "*.new")" ]

# A second run with nothing changed copies nothing.
run > "${work}/log"
test ! -s "${work}/log"

# A loader.conf the user changed is kept.
printf 'timeout 10\n' > "${esp}/loader/loader.conf"
run > "${work}/log"
printf 'timeout 10\n' | cmp - "${esp}/loader/loader.conf"

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
test ! -e "${esp}/loader/entries/armada-ostree-2.conf"
test ! -e "${esp}/loader/entries/armada-ostree-1.conf"
printf other | cmp - "${esp}/loader/entries/other-os.conf"
printf 'timeout 10\n' | cmp - "${esp}/loader/loader.conf"
test ! -e "${esp}/ostree"
test -s "${esp}/KERNEL"

# Moving forward again restores the EFI boot files.
sed -i 's/^version 0$/version 2/' "${boot}/loader/entries/ostree-2.conf"
run > "${work}/log"
test -s "${esp}/EFI/BOOT/BOOTAA64.EFI"
test -s "${esp}/loader/entries/armada-ostree-2.conf"
cmp "${bootdir}/vmlinuz" "${esp}/ostree/default-test/vmlinuz"

# A deployment ostree dropped leaves the ESP before the copy, even one that
# then fails, and no entry is left pointing at it.
rm -r "${old_bootdir}" "${boot}/loader/entries/ostree-1.conf"
printf '#!/bin/sh\nprintf "Avail\\n1\\n"\n' > "${work}/bin/df"
chmod +x "${work}/bin/df"
if run 2> "${work}/error"; then exit 1; fi
rm "${work}/bin/df"
test ! -e "${esp}/ostree/default-old"
if grep -rqF default-old "${esp}/loader/entries"; then exit 1; fi
cmp "${bootdir}/vmlinuz" "${esp}/ostree/default-test/vmlinuz"
test -s "${esp}/loader/entries/armada-ostree-2.conf"

# A broken default entry fails before touching the ESP.
rm "${bootdir}/initramfs"
if run 2> "${work}/error"; then exit 1; fi
grep -Fq 'missing or empty initrd' "${work}/error"
