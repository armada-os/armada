#!/usr/bin/bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
UCM="${ROOT}/system_files/usr/share/alsa/ucm2/AYN/Odin2/HiFi.conf"
ROUTER="${ROOT}/system_files/usr/libexec/armada/odin2-mic-route"
UNIT="${ROOT}/system_files/usr/lib/systemd/system/armada-odin2-mic-route.service"
BUILD="${ROOT}/build_files/40-vendor-system-files.sh"

[[ "$(grep -c '^SectionDevice\."Mic"' "${UCM}")" -eq 1 ]]
! grep -q '^SectionDevice\."Headset"' "${UCM}"
grep -Fq 'CapturePCM "hw:${CardId},2"' "${UCM}"

bash -n "${ROUTER}"
grep -Fq 'sset "TX SMIC MUX0" SWR_MIC7' "${ROUTER}"
grep -Fq 'sset "TX SMIC MUX0" SWR_MIC1' "${ROUTER}"
grep -Fq 'cget numid=110' "${ROUTER}"
grep -Fq 'until grep -q AYN-Odin2 /proc/asound/cards' "${ROUTER}"

grep -Fq 'ExecStart=/usr/libexec/armada/odin2-mic-route' "${UNIT}"
grep -Fq 'RestartSec=1' "${UNIT}"
grep -Fq 'ExecCondition=/usr/bin/grep -a -q "AYN Odin 2" /sys/firmware/devicetree/base/model' "${UNIT}"
grep -Fq 'systemctl enable armada-odin2-mic-route.service' "${BUILD}"

printf 'Odin 2 microphone routing test passed\n'
