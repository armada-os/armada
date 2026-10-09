#!/bin/bash
set -euxo pipefail

version_file=/usr/lib/armada/version
os_release=/usr/lib/os-release

# Preserve the Fedora base version for compatibility checks which match
# Armada's ID_LIKE against Fedora's ID and then compare VERSION_ID.
base_version_id=$(
    source "${os_release}"
    printf '%s' "${VERSION_ID:-}"
)
if [[ -z ${base_version_id} || ${base_version_id} == *[!a-z0-9._-]* ]]; then
    echo "ERROR: invalid base VERSION_ID for os-release: ${base_version_id@Q}" >&2
    exit 1
fi

armada_version=$(<"${version_file}")
if [[ -z ${armada_version} || ${armada_version} == *[!a-z0-9._-]* ]]; then
    echo "ERROR: invalid Armada version for os-release: ${armada_version@Q}" >&2
    exit 1
fi

install -d -m 0755 /usr/lib /etc
cat >"${os_release}" <<EOF
NAME="Armada"
VERSION="${armada_version}"
ID=armada
ID_LIKE="fedora"
VERSION_ID="${base_version_id}"
BUILD_ID="${armada_version}"
PRETTY_NAME="Armada ${armada_version}"
DEFAULT_HOSTNAME=armada
IMAGE_ID=armada
IMAGE_VERSION="${armada_version}"
HOME_URL="https://armadaos.dev/"
DOCUMENTATION_URL="https://armadaos.dev/"
SUPPORT_URL="https://armadaos.dev/troubleshooting/frequently-asked-questions/"
BUG_REPORT_URL="https://github.com/armada-os/armada/issues"
EOF
chmod 0644 "${os_release}"

# Keep the vendor-owned release metadata in /usr. The relative link also works
# when /etc is inspected through a mounted sysroot or from an initramfs.
ln -sfnT ../usr/lib/os-release /etc/os-release
