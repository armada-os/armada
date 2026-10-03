#!/usr/bin/env bash
#
# Regression test for: KONKR Pocket FIT Elite speakers produce no sound
# (upstream issue #248).
#
# Root cause: the "SPK2/SPK3 PCM Playback Volume" controls of the two
# AW88261 amps come up at 0, which is -90 dB on their 0..360 (0.25 dB/step)
# scale. The UCM Speaker device had no EnableSequence, so nothing ever
# raised them and the speakers were silent. Verified on hardware: at 0 no
# sound; after the Speaker EnableSequence sets 360 (0 dB), audible output.
#
# This asserts both csets are present in the shipped UCM profile with a
# non-zero value. It cannot verify acoustic output; that needs the device.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CONF="$ROOT/system_files/usr/share/alsa/ucm2/KONKR/PocketFitElite/HiFi.conf"

if [[ ! -f "$CONF" ]]; then
	printf 'conf file not found: %s\n' "$CONF" >&2
	exit 1
fi

# Extract the SectionDevice."Speaker" { ... } block.
block=$(awk '
	/SectionDevice\."Speaker"/ { capture=1 }
	capture { print; if (/^\}/ && started) exit }
	capture && /\{/ { started=1 }
' "$CONF")

if [[ -z "$block" ]]; then
	printf 'could not locate SectionDevice."Speaker" block in %s\n' "${CONF#"$ROOT"/}" >&2
	exit 1
fi

failed=0
for ctl in "SPK2 PCM Playback Volume" "SPK3 PCM Playback Volume"; do
	line=$(grep -F "cset" <<<"$block" | grep -F "$ctl" || true)
	if [[ -z "$line" ]]; then
		printf 'no cset for '\''%s'\'' in the Speaker EnableSequence -- amp stays muted at probe default\n' \
			"$ctl" >&2
		failed=1
		continue
	fi
	value=$(sed -n "s/.*name='$ctl' \([0-9]\+\).*/\1/p" <<<"$line")
	if [[ -z "$value" || "$value" == "0" ]]; then
		printf '%s'\'' is set to mute (value=%s): %s\n' "$ctl" "${value:-<unparsed>}" "$line" >&2
		failed=1
	fi
done

if ((failed)); then
	exit 1
fi

printf 'KONKR Pocket FIT Elite speaker unmute test passed\n'
