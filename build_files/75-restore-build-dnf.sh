#!/bin/bash
set -euxo pipefail

BUILD_DNF_STATE_DIR=/tmp/armada-build-dnf

rm -f /etc/dnf/libdnf5.conf.d/10-armada-build.conf

if [[ -d "${BUILD_DNF_STATE_DIR}/yum.repos.d" ]]; then
    for repo in "${BUILD_DNF_STATE_DIR}"/yum.repos.d/*.repo; do
        [[ -e "${repo}" ]] || continue
        cp -a "${repo}" "/etc/yum.repos.d/${repo##*/}"
    done
fi

rm -rf "${BUILD_DNF_STATE_DIR}"
