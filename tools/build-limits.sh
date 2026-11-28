#!/bin/bash
# Print podman args capping a build's memory, without swap, so it can't freeze the host.
# ARMADA_BUILD_MEMORY: a size like 12g, or none.
set -euo pipefail

mem=${ARMADA_BUILD_MEMORY:-}
[ "$mem" != none ] || exit 0
if ! podman info --format '{{.Host.CgroupControllers}}' 2>/dev/null | grep -qw memory; then
    echo "note: podman can't limit memory on this host; building without a cap" >&2
    exit 0
fi

if [ -z "$mem" ]; then
    avail=$(awk '/^MemAvailable:/ { print int($2 / 1048576) }' /proc/meminfo)
    # MemAvailable includes the desktop's own page cache; leave it a quarter.
    gb=$(( ${avail:-0} * 3 / 4 ))
    if [ "$gb" -lt 4 ]; then
        echo "only ${avail:-0} GB of memory is free; close something or set ARMADA_BUILD_MEMORY" >&2
        exit 1
    fi
    mem="${gb}g"
fi
echo "--memory=$mem"
echo "--memory-swap=$mem"
