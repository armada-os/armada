#!/usr/bin/env bash
# Opt-in read-only checks against a running Odin 3 audio session.
set -euo pipefail

if [[ "${ODIN3_AUDIO_DEVICE_TEST:-0}" != 1 ]]; then
    printf '%s\n' 'SKIP: set ODIN3_AUDIO_DEVICE_TEST=1 on an Odin 3'
    exit 0
fi

readonly model_path="${ODIN3_AUDIO_MODEL_PATH:-/sys/firmware/devicetree/base/model}"
model="$(tr -d '\0' <"$model_path")"
if [[ "$model" != "AYN Odin 3" ]]; then
    printf 'ERROR: expected AYN Odin 3, found %q\n' "$model" >&2
    exit 1
fi

for command in pactl wpctl; do
    command -v "$command" >/dev/null ||
        { printf 'ERROR: missing %s\n' "$command" >&2; exit 1; }
done

mapfile -t public_sinks < <(
    pactl list short sinks |
        while IFS=$'\t' read -r _ sink_name _; do
            printf '%s\n' "$sink_name"
        done
)

stereo_count=0
virtual_count=0
for sink_name in "${public_sinks[@]}"; do
    case "$sink_name" in
        Stereo) (( stereo_count += 1 )) ;;
        'Virtual Surround Sound') (( virtual_count += 1 )) ;;
        alsa_output.platform-sound.HiFi__Speaker__sink|effect_input.odin3-stereo|effect_input.odin3_dvs)
            printf 'ERROR: obsolete or physical Odin sink is public: %s\n' \
                "$sink_name" >&2
            exit 1
            ;;
    esac
done

if (( stereo_count != 1 || virtual_count != 1 )); then
    printf 'ERROR: expected one Stereo and one Virtual Surround Sound sink; found %s and %s\n' \
        "$stereo_count" "$virtual_count" >&2
    printf '  public sink: %s\n' "${public_sinks[@]}" >&2
    exit 1
fi

default_sink="$(pactl get-default-sink)"
case "$default_sink" in
    Stereo | 'Virtual Surround Sound') ;;
    *)
        printf 'ERROR: unexpected default sink: %s\n' "$default_sink" >&2
        exit 1
        ;;
esac

if [[ -n "${ODIN3_AUDIO_EXPECT_DEFAULT:-}" &&
      "$default_sink" != "$ODIN3_AUDIO_EXPECT_DEFAULT" ]]; then
    printf 'ERROR: expected persisted default %q, found %q\n' \
        "$ODIN3_AUDIO_EXPECT_DEFAULT" "$default_sink" >&2
    exit 1
fi

virtual_volume="$(
    pactl get-sink-volume 'Virtual Surround Sound' |
        grep -oE '[0-9]+%' | sort -u || true
)"
if [[ "$virtual_volume" == *$'\n'* || ! "$virtual_volume" =~ ^[0-9]+%$ ]]; then
    printf 'ERROR: Virtual Surround Sound has unequal or unreadable channel volumes: %q\n' \
        "$virtual_volume" >&2
    exit 1
fi
virtual_volume_percent=${virtual_volume%\%}
virtual_mute="$(pactl get-sink-mute 'Virtual Surround Sound')"
virtual_mute=${virtual_mute##*: }
case "$virtual_mute" in
    yes | no) ;;
    *)
        printf 'ERROR: unreadable Virtual Surround Sound mute state: %q\n' \
            "$virtual_mute" >&2
        exit 1
        ;;
esac

if [[ -n "${ODIN3_AUDIO_EXPECT_VIRTUAL_VOLUME_PERCENT:-}" &&
      "$virtual_volume_percent" != "$ODIN3_AUDIO_EXPECT_VIRTUAL_VOLUME_PERCENT" ]]; then
    printf 'ERROR: expected persisted Virtual Surround Sound volume %s%%, found %s%%\n' \
        "$ODIN3_AUDIO_EXPECT_VIRTUAL_VOLUME_PERCENT" "$virtual_volume_percent" >&2
    exit 1
fi
if [[ -n "${ODIN3_AUDIO_EXPECT_VIRTUAL_MUTE:-}" &&
      "$virtual_mute" != "$ODIN3_AUDIO_EXPECT_VIRTUAL_MUTE" ]]; then
    printf 'ERROR: expected persisted Virtual Surround Sound mute %q, found %q\n' \
        "$ODIN3_AUDIO_EXPECT_VIRTUAL_MUTE" "$virtual_mute" >&2
    exit 1
fi

wpctl_status="$(wpctl status --name)"
transport_name='alsa_output.platform-sound.HiFi__Speaker__sink'
transport_id="$(
    sed -n "\|${transport_name}|s/^[^0-9]*\([0-9][0-9]*\)\..*/\1/p" \
        <<<"$wpctl_status" | head -n 1
)"
if [[ -z "$transport_id" ]]; then
    printf 'ERROR: hidden speaker transport %s is absent\n' "$transport_name" >&2
    exit 1
fi
transport_volume="$(wpctl get-volume "$transport_id")"
if grep -Fq '[MUTED]' <<<"$transport_volume"; then
    printf 'ERROR: hidden speaker transport is muted: %s\n' "$transport_volume" >&2
    exit 1
fi
transport_volume=${transport_volume#Volume: }
if ! awk -v volume="$transport_volume" \
    'BEGIN { exit !(volume >= 0.999999 && volume <= 1.000001) }'; then
    printf 'ERROR: hidden speaker transport must remain at 100%%, found %s\n' \
        "$transport_volume" >&2
    exit 1
fi

printf 'Current default: %s\n' "$default_sink"
printf 'Virtual Surround Sound: %s%%, mute=%s\n' \
    "$virtual_volume_percent" "$virtual_mute"
printf '%s\n' 'To verify persistence, reboot without changing audio state and run:'
printf 'ODIN3_AUDIO_DEVICE_TEST=1 ODIN3_AUDIO_EXPECT_DEFAULT=%q ' "$default_sink"
printf 'ODIN3_AUDIO_EXPECT_VIRTUAL_VOLUME_PERCENT=%q ' "$virtual_volume_percent"
printf 'ODIN3_AUDIO_EXPECT_VIRTUAL_MUTE=%q %q\n' \
    "$virtual_mute" "$0"
printf '%s\n' 'Odin 3 live audio checks passed'
