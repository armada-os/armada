#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
# ccache at /ccache: a cache mount in the stage, a bind mount locally.
set -euxo pipefail

source ./BASE.env
export KERNEL_VERSION="${VERSION}"
export CCACHE_DIR="${CCACHE_DIR:-/ccache}"
export CCACHE_MAXSIZE=4G
mkdir -p "${CCACHE_DIR}"

rm -rf out
mkdir -p out

dnf -y install gcc binutils make bc bison flex openssl-devel \
    elfutils-libelf-devel dwarves zstd xz cpio patch curl perl-interpreter python3 \
    findutils diffutils gawk grep sed coreutils hostname gzip tar ccache kmod
# The install above can upgrade libzstd (pulled in by the -devel packages)
# without upgrading the zstd binary, which then refuses to run.
dnf -y upgrade zstd
WORK_DIR=/tmp/armada-kernel-build OUT_DIR=/work/out \
    bash scripts/build-kernel.sh
