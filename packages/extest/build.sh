#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
set -euxo pipefail

source ./BASE.env

rm -rf out
mkdir -p out

dnf -y install git cargo rust gcc
git clone https://github.com/Supreeeme/extest /tmp/extest
git -C /tmp/extest checkout "${COMMIT}"
# upstream forces x86
rm -f /tmp/extest/.cargo/config.toml
( cd /tmp/extest && cargo build --release )
cp /tmp/extest/target/release/libextest.so /work/out/
