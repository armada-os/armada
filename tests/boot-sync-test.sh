#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "${work}"' EXIT
export TRACE=${work}/trace SYNC_LOCK=${work}/sync.lock
export BOOTIMG=${work}/bootimg EFIUPDATE=${work}/efi BOOTC=${work}/bootc
export UPDATE=${ROOT}/system_files/usr/libexec/armada/armada-boot-update
for name in bootimg efi; do
    cat > "${work}/${name}" <<'EOF'
#!/bin/bash
name=${0##*/}
printf '%s %s\n' "${name}" "$*" >> "${TRACE}"
if [ "${FAIL:-}" = "${name}" ] && [ ! -e "${TRACE}.rolled-back" ]; then
    exit 23
fi
EOF
    chmod +x "${work}/${name}"
done
cat > "${BOOTC}" <<'EOF'
#!/bin/bash
[ "$*" = rollback ]
printf 'rollback\n' >> "${TRACE}"
[ "${FAIL_ROLLBACK:-0}" = 0 ] || exit 42
touch "${TRACE}.rolled-back"
EOF
chmod +x "${BOOTC}"

"${UPDATE}" --snapshot-prev
printf 'bootimg --snapshot-prev\nefi \n' > "${work}/expected"
cmp "${work}/expected" "${TRACE}"

for failed in bootimg efi; do
    : > "${TRACE}"
    rm -f "${TRACE}.rolled-back"
    status=0
    FAIL=${failed} "${ROOT}/system_files/usr/libexec/armada/armada-bootimg-finalize" 2>"${work}/error" || status=$?
    [ "${status}" = 23 ]
    case "${failed}" in bootimg) step=ABL ;; efi) step=EFI ;; esac
    grep -Fxq "armada-boot-update: ${step} boot sync failed (status 23)" "${work}/error"
    {
        printf 'bootimg \n'
        [ "${failed}" != efi ] || printf 'efi \n'
        printf 'rollback\nbootimg \nefi \n'
    } > "${work}/expected"
    cmp "${work}/expected" "${TRACE}"
done

: > "${TRACE}"
rm -f "${TRACE}.rolled-back"
status=0
FAIL=bootimg FAIL_ROLLBACK=1 "${ROOT}/system_files/usr/libexec/armada/armada-bootimg-finalize" || status=$?
[ "${status}" = 23 ]
printf 'bootimg \nrollback\n' > "${work}/expected"
cmp "${work}/expected" "${TRACE}"
