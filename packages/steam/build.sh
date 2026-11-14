#!/usr/bin/env bash
# Phase 1: verify the manifest logic, then fetch the client packages.
#
# Phase 2 is generate.sh, run separately with networking off so it cannot reach
# the network: a RUN --network=none in the stage, --network none under
# ../build-local.sh.
set -euo pipefail

source BASE.env

rm -rf out
mkdir -p out work

python3 test.py
python3 fetch.py "$STEAM_CLIENT_CHANNEL" "$STEAM_CLIENT_VERSION"
