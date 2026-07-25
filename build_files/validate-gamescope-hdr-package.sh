#!/bin/bash
set -euo pipefail

readonly gamescope=${ARMADA_GAMESCOPE_VALIDATOR_BINARY:-/usr/bin/gamescope}
readonly rpm_query=${ARMADA_GAMESCOPE_VALIDATOR_RPM:-/usr/bin/rpm}
readonly capability_marker=${ARMADA_GAMESCOPE_VALIDATOR_MARKER:-/usr/lib/armada/gamescope-hdr-capabilities}
readonly required_provide=armada-gamescope-expose-client-sampleable-formats
readonly required_option=--expose-client-sampleable-formats
readonly marker_value=expose-client-sampleable-formats-v1

# Never allow a marker from an earlier image layer to survive failed validation.
rm -f -- "$capability_marker"

if [[ ! -f "$gamescope" || -L "$gamescope" ]]; then
    printf 'ERROR: Gamescope must be a regular, non-symlink file: %s\n' "$gamescope" >&2
    exit 1
fi

if [[ ! -x "$rpm_query" ]]; then
    printf 'ERROR: RPM query command is unavailable: %s\n' "$rpm_query" >&2
    exit 1
fi

if ! "$rpm_query" -q --whatprovides "$required_provide" >/dev/null 2>&1; then
    printf 'ERROR: installed Gamescope package lacks RPM capability %s\n' \
        "$required_provide" >&2
    exit 1
fi

# Gamescope carries file capabilities that cannot be exercised in rootless
# image builds. Inspect the installed payload without executing it.
if ! LC_ALL=C grep -aFq -- "$required_option" "$gamescope"; then
    printf 'ERROR: installed Gamescope lacks %s\n' "$required_option" >&2
    exit 1
fi

marker_directory=${capability_marker%/*}
if [[ "$marker_directory" == "$capability_marker" ]]; then
    marker_directory=.
fi
mkdir -p -- "$marker_directory"
temporary_marker=$(mktemp "${capability_marker}.tmp.XXXXXX")
cleanup() {
    rm -f -- "$temporary_marker"
}
trap cleanup EXIT HUP INT TERM
printf '%s\n' "$marker_value" >"$temporary_marker"
chmod 0644 -- "$temporary_marker"
mv -f -- "$temporary_marker" "$capability_marker"
trap - EXIT HUP INT TERM
