#!/bin/bash
# Capture a board's SSC (gyro) data from its stock Android partitions.
# usage: capture.sh <device id> <vendor root> <persist root> [out dir]
set -euo pipefail

if [ $# -lt 3 ]; then
    echo "usage: $0 <device id> <vendor root> <persist root> [out dir]" >&2
    exit 2
fi
id=$1 vendor=$2 persist=$3
out=${4:-$(dirname "$(readlink -f "$0")")/data}
src=$vendor/etc/sensors
reg=$persist/sensors/registry

for path in "$src/config" "$src/sns_reg_config" "$reg/registry" "$reg/sns_reg_version"; do
    if [ ! -e "$path" ]; then
        echo "missing $path" >&2
        exit 1
    fi
done

work=$(mktemp -d)
trap 'rm -r -- "$work"' EXIT
root=$work/root
mkdir -p "$root/sensors/registry"

cp -r "$src/config" "$root/sensors/"
cp "$src/sns_reg_config" "$root/sensors/sns_reg.conf"
cp "$reg/sns_reg_version" "$root/sensors/"
ln -s /sys/devices/soc0 "$root/socinfo"

# Skip non-JSON debris and calibration Android learned on this unit; report
# non-default factory calibration, which may be per unit.
python3 -I - "$reg/registry" "$root/sensors/registry" <<'EOF'
import json, os, re, shutil, sys

src, dst = sys.argv[1:]
learned = re.compile(r"^sns_\w+_cal_(persist|table)_")
kept = 0
for name in sorted(os.listdir(src)):
    path = os.path.join(src, name)
    try:
        with open(path) as f:
            entry = json.load(f)
    except (OSError, ValueError):
        entry = None
    if not isinstance(entry, dict) or len(entry) != 1:
        print(f"skipped (not a registry entry): {name}")
        continue
    if learned.match(name):
        print(f"skipped (learned calibration): {name}")
        continue
    group, items = next(iter(entry.items()))
    if ".fac_cal" in group:
        for key, item in items.items():
            if isinstance(item, dict) and item.get("ver", "0") != "0":
                print(f"review: {group}.{key} = {item.get('data')}")
    shutil.copyfile(path, os.path.join(dst, name))
    kept += 1
print(f"registry: {kept} entries")
EOF

fingerprint=$(sed -n 's/^ro.vendor.build.fingerprint=//p' "$vendor/build.prop" 2>/dev/null | head -1 || true)
# The registry must suit the ADSP firmware this image loads.
adsp=""
for fw in /sys/class/remoteproc/remoteproc*/firmware; do
    case "$(cat "$fw" 2>/dev/null)" in
        *adsp*) adsp=/usr/lib/firmware/$(cat "$fw") ;;
    esac
done
adsp_version=""
if [ -f "$adsp" ]; then
    adsp_version=$(grep -a -o -m1 'QC_IMAGE_VERSION_STRING=[A-Za-z0-9._-]*' "$adsp" | cut -d= -f2 || true)
fi
printf 'device=%s\nvendor_fingerprint=%s\nadsp_firmware=%s\nadsp_firmware_path=%s\ncaptured=%s\n' \
    "$id" "${fingerprint:-unknown}" "${adsp_version:-unknown}" "${adsp#/usr/lib/firmware/}" \
    "$(date -u +%Y-%m-%d)" > "$root/SOURCE"

tar --sort=name --owner=0 --group=0 --numeric-owner --mtime=@0 \
    --mode=u=rwX,go=rX -C "$root" -cf - . | gzip -n > "$out/$id.tar.gz"
echo "wrote $out/$id.tar.gz"
cat "$root/SOURCE"
