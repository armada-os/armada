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
    if group == "sns_reg_config":
        # Image files have mtime 0; other recorded mtimes make the ADSP re-parse.
        for key, item in items.items():
            if isinstance(item, dict):
                item["data"] = "0"
        with open(os.path.join(dst, name), "w") as f:
            json.dump(entry, f, separators=(",", ":"))
    else:
        shutil.copyfile(path, os.path.join(dst, name))
    kept += 1
print(f"registry: {kept} entries")
EOF

fingerprint=$(sed -n 's/^ro.vendor.build.fingerprint=//p' "$vendor/build.prop" 2>/dev/null | head -1 || true)
if [ -z "$fingerprint" ]; then
    echo "no ro.vendor.build.fingerprint in $vendor/build.prop" >&2
    exit 1
fi
# The registry is only valid for the exact ADSP firmware running now.
fw_path=$(cat /sys/module/firmware_class/parameters/path)
if [ -n "$fw_path" ]; then
    echo "firmware_class.path is set; the ADSP may not run this image's firmware" >&2
    exit 1
fi
adsp_names=""
running=""
for rproc in /sys/class/remoteproc/remoteproc*; do
    case "$(cat "$rproc/name" 2>/dev/null)" in
        adsp)
            adsp_names=$(tr '\0' ' ' < "$rproc/device/of_node/firmware-name")
            running=$(cat "$rproc/firmware")
            ;;
    esac
done
if [ -z "$adsp_names" ]; then
    echo "no ADSP remoteproc found" >&2
    exit 1
fi
if [ "$running" != "${adsp_names%% *}" ]; then
    echo "ADSP firmware set to $running, not the DT's ${adsp_names%% *}" >&2
    exit 1
fi
fw=/usr/lib/firmware
files=""
for name in $adsp_names; do
    files="$files $name"
    # Split images load their segments as <name>.bNN.
    if [ "${name%.mdt}" != "$name" ]; then
        for seg in "$fw/${name%.mdt}".b[0-9][0-9]; do
            [ -e "$seg" ] && files="$files ${seg#"$fw"/}"
        done
    fi
done
adsp=""
adsp_sha256=""
for name in $files; do
    # The kernel searches these before /usr/lib/firmware.
    for shadow in "$fw/updates/$(uname -r)" "$fw/updates" "$fw/$(uname -r)"; do
        for f in "$shadow/$name" "$shadow/$name.xz" "$shadow/$name.zst"; do
            if [ -e "$f" ]; then
                echo "$f overrides $fw/$name" >&2
                exit 1
            fi
        done
    done
    if [ ! -f "$fw/$name" ]; then
        echo "missing $fw/$name" >&2
        exit 1
    fi
    [ -n "$adsp" ] || adsp=$fw/$name
    adsp_sha256="$adsp_sha256 $name:$(sha256sum "$fw/$name" | cut -d' ' -f1)"
done
adsp_version=$(grep -a -o -m1 'QC_IMAGE_VERSION_STRING=[A-Za-z0-9._-]*' "$adsp" | cut -d= -f2 || true)
if [ -z "$adsp_version" ]; then
    echo "no QC_IMAGE_VERSION_STRING in $adsp" >&2
    exit 1
fi
printf 'device=%s\nvendor_fingerprint=%s\nadsp_firmware=%s\nadsp_sha256=%s\ncaptured=%s\n' \
    "$id" "$fingerprint" "$adsp_version" "${adsp_sha256# }" \
    "$(date -u +%Y-%m-%d)" > "$root/SOURCE"

tar --sort=name --owner=0 --group=0 --numeric-owner --mtime=@0 \
    --mode=u=rwX,go=rX -C "$root" -cf - . | gzip -n > "$out/$id.tar.gz"
echo "wrote $out/$id.tar.gz"
cat "$root/SOURCE"
