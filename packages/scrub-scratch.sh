#!/usr/bin/env bash
# Remove build scratch before the stage's layer is committed.
#
# A RUN commits its whole filesystem diff, so scratch left behind is baked into
# the layer. Deleting it inside the same RUN leaves no trace in the diff.
#
# Deliberately not touched: /work/out (the artifacts), /ccache and other cache
# mounts (excluded from the layer already, and wanted for the next build).
set -uo pipefail

find /tmp -mindepth 1 -delete 2>/dev/null || true
rm -rf /root/rpmbuild /root/.cache 2>/dev/null || true
rm -rf /var/cache/dnf /var/cache/libdnf5 /var/cache/pacman/pkg 2>/dev/null || true
exit 0
