#!/usr/bin/env bash
# Builder dependencies for steam-bootstrap. Single source for both the local
# builder image (Containerfile) and the CI builder stage (../Containerfile).
set -euo pipefail
dnf -y install python3 curl unzip file tar xz zstd xorg-x11-server-Xvfb gtk2 libatomic
dnf clean all
