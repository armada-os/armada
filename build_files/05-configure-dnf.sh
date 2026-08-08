#!/bin/bash
set -euxo pipefail

BUILD_DNF_STATE_DIR=/tmp/armada-build-dnf

mkdir -p /etc/dnf/libdnf5.conf.d
cat >/etc/dnf/libdnf5.conf.d/10-armada-build.conf <<'EOF'
[main]
fastestmirror=True
max_parallel_downloads=10
minrate=200k
timeout=20
EOF

if [[ -n "${ARMADA_FEDORA_MIRROR:-}" ]]; then
    fedora_mirror="${ARMADA_FEDORA_MIRROR%/}"
    mkdir -p "${BUILD_DNF_STATE_DIR}/yum.repos.d"

    for repo in /etc/yum.repos.d/fedora*.repo; do
        [[ -e "${repo}" ]] || continue
        grep -q '^#baseurl=http://download.example/pub/fedora/linux' "${repo}" || continue
        cp -a "${repo}" "${BUILD_DNF_STATE_DIR}/yum.repos.d/${repo##*/}"
        sed -i \
            -e 's|^metalink=|#metalink=|' \
            -e "s|^#baseurl=http://download.example/pub/fedora/linux|baseurl=${fedora_mirror}|" \
            "${repo}"
    done
fi
