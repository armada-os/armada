#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

rm -rf out
mkdir -p out

dnf -y install gcc kernel-headers
gcc -O2 -Wall -Wextra -fPIC -shared -o out/libsteam-v4l2-shim.so steam-v4l2-shim.c -ldl
