#!/bin/bash
set -euxo pipefail

#
# Base
#

pkgs=(
    blas
    bzip2-libs
    glibc-langpack-en
    glibc-langpack-zh
    lapack
    libxcrypt-compat
    newt
    polkit
    sudo

    # Radio 
    bluez
    NetworkManager
    NetworkManager-wifi
    wpa_supplicant

    # Hardware support
    dracut
    dracut-config-generic
    upower
    atheros-firmware
    qcom-firmware

    # CLI tools
    binutils
    btop
    btrfs-progs
    cabextract
    curl
    distrobox
    evtest
    fuse
    gdisk
    git
    htop
    jq
    lsb_release
    lsof
    parted
    python-unversioned-command
    python3-gobject
    python3-vdf
    python3-websocket-client
    rsync
    tailscale
    unzip
    xz

    # Audio
    alsa-lib
    alsa-ucm
    alsa-utils
    pipewire
    pipewire-alsa
    pipewire-pulseaudio
    pulseaudio-utils
    wireplumber

    # Graphics - see 12-armada-packages.sh for mesa
    openal-soft
    SDL2_gfx
    SDL2_image
    SDL2_ttf
    sdl2-compat
    vulkan-loader
    vulkan-tools

    # FEX dependencies - see 12-armada-packages.sh for the main package
    erofs-fuse
    erofs-utils
    fuse-libs
    squashfs-tools
    squashfuse

    # Steam extras - see 12-armada-packages.sh for the main package
    steam-devices
    steam-notif-daemon
)

dnf5 -y install --nogpgcheck \
    --repofrompath 'terra,https://repos.fyralabs.com/terra$releasever' \
    terra-release

dnf5 -y install --setopt=install_weak_deps=False "${pkgs[@]}"


#
# Desktop
#

# KDE Plasma Desktop
kde_excludes=(
    # Login Manager - we use SDDM
    plasma-login-manager
    kcm-plasmalogin
    kde-settings-plasmalogin

    # Software updates - handled by bootc in Steam
    plasma-discover
    plasma-discover-kns
    plasma-discover-libs
    plasma-discover-notifier
    plasma-discover-offline-updates
    plasma-discover-packagekit
    plasma-pk-updates
    PackageKit-command-not-found
    PackageKit-glib

    # Hybrid-GPU managers - not currently useful
    cardwire
    switcheroo-control

    # File indexers
    localsearch
    tinysparql
    tracker
    tracker-miners

    # Plasma X11 session
    plasma-x11
    plasma-workspace-x11

    # Wallpapers - can be reconsidered when heroic has a flatpak, its over double the wallpaper package size.
    plasma-workspace-wallpapers

    # Unwanted apps
    akonadi-server-mysql
    firewall-config
    kcharselect
    kde-partitionmanager
    plasma-drkonqi
    plasma-setup
    plasma-welcome
    plasma-welcome-fedora
)

dnf5 -y install "${kde_excludes[@]/#/--exclude=}" @kde-desktop

desktop_pkgs=(
    # Login Manager
    sddm
    seatd

    # Session packages
    dbus-broker
    dbus-x11
    desktop-file-utils
    xdg-terminal-exec
    xdg-user-dirs

    # KDE extras
    gtk2
    gtk4
    gwenview
    kio-extras
    libadwaita
    libdbusmenu-gtk3
    qt6-qttools
    qt6-qttranslations
    qt6-qtvirtualkeyboard
    xorg-x11-server-Xwayland
    zenity

    # KDE Mobile
    plasma-mobile
    plasma-settings
    qmlkonsole

    # SMB
    libsmbclient
    cifs-utils

    # Miscellaneous
    cage
    firefox
    heroic-games-launcher
    waydroid
    wl-clipboard
    wlr-randr

    # Extra fonts
    google-noto-color-emoji-fonts
    google-noto-sans-arabic-vf-fonts
    google-noto-sans-cjk-fonts
    google-noto-sans-devanagari-vf-fonts
    google-noto-sans-hebrew-vf-fonts
    google-noto-sans-mono-fonts
    google-noto-sans-thai-vf-fonts
    google-noto-sans-vf-fonts
)

dnf5 -y install --setopt=install_weak_deps=False "${desktop_pkgs[@]}"

#
# Multimedia
#

dnf5 -y install --setopt=install_weak_deps=False \
    --repofrompath 'negativo-multimedia,https://negativo17.org/repos/multimedia/fedora-$releasever/$basearch/' \
    --setopt=negativo-multimedia.gpgcheck=0 \
    --setopt=negativo-multimedia.repo_gpgcheck=0 \
    ffmpeg \
    ffmpeg-libs \
    gstreamer1-plugin-libav \
    gstreamer1-plugins-ugly \
    libavcodec \
    libfdk-aac

# Install the remaining plugins from Fedora; Negativo17's full -bad package
# pulls a large soundfont payload that Armada does not need.
dnf5 -y install --setopt=install_weak_deps=False \
    gstreamer1-plugin-dav1d \
    gstreamer1-plugin-openh264 \
    gstreamer1-plugins-bad-free \
    gstreamer1-plugins-good

#
# Flatpak setup
#

dnf5 -y install --setopt=install_weak_deps=False \
    --repofrompath 'copr-ublue-os-packages,https://download.copr.fedorainfracloud.org/results/ublue-os/packages/fedora-$releasever-$basearch/' \
    --setopt=copr-ublue-os-packages.gpgcheck=0 \
    --setopt=copr-ublue-os-packages.repo_gpgcheck=0 \
    bazaar \
    flatpak \
    krunner-bazaar

mkdir -p /etc/flatpak/remotes.d
curl --retry 3 -fsSL -o /etc/flatpak/remotes.d/flathub.flatpakrepo \
    https://dl.flathub.org/repo/flathub.flatpakrepo
