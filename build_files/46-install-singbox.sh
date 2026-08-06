#!/bin/bash
set -euxo pipefail

# sing-box static binary, pinned release + sha256 (arm64).
SB_VER=1.13.16
SB_SHA=d587fb00bdc3c044227f35d15d154f271bc75108475091eda2542e4b82bb2949
curl -fsSL -o /tmp/sing-box.tar.gz     "https://github.com/SagerNet/sing-box/releases/download/v${SB_VER}/sing-box-${SB_VER}-linux-arm64.tar.gz"
echo "${SB_SHA}  /tmp/sing-box.tar.gz" | sha256sum -c -
tar -xzf /tmp/sing-box.tar.gz -C /tmp
install -m 0755 "/tmp/sing-box-${SB_VER}-linux-arm64/sing-box" /usr/bin/sing-box
rm -rf /tmp/sing-box.tar.gz "/tmp/sing-box-${SB_VER}-linux-arm64"
/usr/bin/sing-box version
