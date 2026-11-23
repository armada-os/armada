#!/usr/bin/env bash
# Builder dependencies for steam. Single source for both the local builder
# image (Containerfile) and the CI builder stage (../Containerfile). generate.sh
# runs with no network, so everything it needs, rpmbuild included, is baked in.
set -euo pipefail
dnf -y install python3 curl unzip tar gzip zstd rpm-build rpmdevtools
dnf clean all
