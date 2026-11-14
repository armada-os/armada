#!/bin/bash
set -euxo pipefail

pkgs=(
    /packages/jupiter-hw-support/*.rpm

    # SteamOS Manager: upstream main plus the Steam Frame series, with our device configs.
    /packages/steamos-manager/steamos-manager-[0-9]*.rpm

    # Armada's patched gamescope packages
    /packages/gamescope/terra-gamescope{,-libs}-[0-9]*.aarch64.rpm \
    /packages/gamescope-session/gamescope-session-*.rpm \
    /packages/gamescope-session-steam/gamescope-session-steam-*.rpm

    # Frame's lepton, stock tool's dependencies and a modified armada-lepton tool
    /packages/lepton/lepton-{guestos,armada}-[0-9]*.rpm

    # Aurora Store integration in Armada Store for Lepton.
    /packages/armada-aurora/*.rpm

    # Steam itself
    /packages/steam/steam-[0-9]*.rpm
)

dnf5 -y install --setopt=install_weak_deps=False "${pkgs[@]}"

# Initial Steam bootstrap
STEAM_BOOTSTRAP_HOME=/var/home/armada
STEAM_HOME="${STEAM_BOOTSTRAP_HOME}/.local/share/Steam"

(cd /packages/steam && sha256sum -c steam-bootstrap.tar.zst.sha256)
rm -rf "${STEAM_BOOTSTRAP_HOME}"
mkdir -p "${STEAM_BOOTSTRAP_HOME}"
tar --zstd -xf /packages/steam/steam-bootstrap.tar.zst -C "${STEAM_BOOTSTRAP_HOME}"
/usr/lib/steam/steam-verify --crc "${STEAM_HOME}"
rm -f /etc/steamos-oobe-image

# Proton CachyOS, included for SM8250 
# TODO: consider replacing with Proton 11 (ARM64) from Valve or fetching after install
mkdir -p /usr/share/steam/compatibilitytools.d
cp -a /packages/proton-cachyos/proton-cachyos-11.0-arm64 /usr/share/steam/compatibilitytools.d/

echo "Pre-staged: ARM64 Steam bootstrap and Proton CachyOS"
