#!/bin/bash
set -euxo pipefail

cd /ctx/build_files

run_step() {
    local step="${1#./}"
    local start="${SECONDS}"

    "$@"
    printf '%s completed in %d seconds\n' "${step}" "$((SECONDS - start))"
}

run_step ./10-base-packages.sh
run_step ./20-install-kernel.sh
run_step ./30-install-steam-session.sh
run_step ./40-vendor-system-files.sh
run_step ./45-install-decky-plugins.sh
run_step ./50-create-user.sh
run_step ./55-generate-initramfs.sh
run_step ./60-set-default-target.sh
run_step ./70-cleanup.sh
run_step ./80-finalize-update-state.sh
