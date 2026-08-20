#!/bin/bash
set -euxo pipefail

dnf5 -y install --nogpgcheck \
    --repofrompath 'terra,https://repos.fyralabs.com/terra$releasever' \
    terra-release

dnf5 -y install --setopt=install_weak_deps=False \
    sddm \
    pipewire \
    pipewire-alsa \
    pipewire-pulseaudio \
    pulseaudio-utils \
    wireplumber \
    alsa-lib \
    alsa-ucm \
    alsa-utils \
    qcom-firmware \
    atheros-firmware \
    NetworkManager \
    NetworkManager-wifi \
    iwd \
    wpa_supplicant \
    bluez \
    dbus-broker \
    python3-gobject \
    python3-websocket-client \
    polkit \
    upower \
    sudo \
    rsync \
    curl \
    git \
    jq \
    htop \
    lsof \
    scx-scheds \
    unzip \
    fuse \
    evtest \
    dbus-x11 \
    xdg-user-dirs \
    xdg-terminal-exec \
    desktop-file-utils \
    btrfs-progs \
    parted \
    gdisk \
    binutils \
    blas \
    bzip2-libs \
    lapack \
    xz \
    dracut \
    dracut-config-generic \
    qt6-qttools \
    qt6-qtvirtualkeyboard \
    zenity \
    seatd \
    cage \
    wlr-randr \
    distrobox

curl --connect-timeout 30 --max-time 120 --retry 3 -fsSL \
    -o /etc/yum.repos.d/negativo17-fedora-multimedia.repo \
    https://negativo17.org/repos/fedora-multimedia.repo

dnf5 -y install --setopt=install_weak_deps=False \
    ffmpeg \
    ffmpeg-libs \
    libavcodec \
    libfdk-aac \
    gstreamer1-plugins-ugly \
    gstreamer1-plugin-libav

# Install the remaining plugins from Fedora; Negativo17's full -bad package
# pulls a large soundfont payload that Armada does not need.
rm -f /etc/yum.repos.d/negativo17-fedora-multimedia.repo

dnf5 -y install --setopt=install_weak_deps=False \
    gstreamer1-plugins-good \
    gstreamer1-plugins-bad-free \
    gstreamer1-plugin-openh264 \
    gstreamer1-plugin-dav1d

dnf5 -y install --setopt=install_weak_deps=False \
    /packages/umtp-responder/umtp-responder-*.rpm

# CachyOS Proton's ARM64 GStreamer asks for Arch's libbz2 soname.
ln -sf libbz2.so.1 /usr/lib64/libbz2.so.1.0

# Some AppImages link zlib's unversioned development soname.
ln -sf libz.so.1 /usr/lib64/libz.so

# pressure-vessel needs en_US.UTF-8; the base image ships only minimal-langpack (C.utf8).
dnf5 -y install --setopt=install_weak_deps=False glibc-langpack-en

dnf5 -y install --setopt=install_weak_deps=False \
    google-noto-sans-vf-fonts \
    google-noto-sans-cjk-vf-fonts \
    google-noto-sans-thai-vf-fonts \
    google-noto-sans-arabic-vf-fonts \
    google-noto-sans-hebrew-vf-fonts \
    google-noto-sans-devanagari-vf-fonts \
    google-noto-color-emoji-fonts \
    google-noto-sans-mono-fonts

dnf5 -y install --setopt=install_weak_deps=False \
    plasma-workspace \
    plasma-desktop \
    plasma-mobile \
    plasma-pa \
    plasma-nm \
    bluedevil \
    maliit-keyboard \
    libappindicator-gtk3 \
    libdbusmenu-gtk3 \
    kdialog \
    kio-extras \
    libsmbclient \
    cifs-utils \
    waydroid \
    kscreen \
    konsole \
    dolphin \
    ark \
    gwenview \
    kwrite

# feedbackd's role-routing sinks can wedge Steam audio during session startup.
rm -f /usr/share/wireplumber/wireplumber.conf.d/media-role-nodes.conf

# Patched KWin lets devices pin Plasma's virtual keyboard to a configured output.
dnf5 -y install --setopt=install_weak_deps=False \
    /packages/kwin/kwin-[0-9]*.rpm \
    /packages/kwin/kwin-common-[0-9]*.rpm \
    /packages/kwin/kwin-libs-[0-9]*.rpm

# PowerDevil's KWin backend treats 0 as safe; reserve 5% for internal panels.
dnf5 -y install --setopt=install_weak_deps=False /packages/powerdevil/powerdevil-*.fc44.armada.*.rpm

dnf5 -y install --setopt=install_weak_deps=False firefox

dnf5 -y install --setopt=install_weak_deps=False \
    heroic-games-launcher

# scx_cosmos/scx_lavd for the Armada Control scheduler setting; without the
# binaries armada-powerd reports the scheduler choice as unavailable.
dnf5 -y install --setopt=install_weak_deps=False scx-scheds

dnf5 -y install --setopt=install_weak_deps=False \
    --repofrompath 'copr-ublue-os-packages,https://download.copr.fedorainfracloud.org/results/ublue-os/packages/fedora-$releasever-$basearch/' \
    --setopt=copr-ublue-os-packages.gpgcheck=0 \
    --setopt=copr-ublue-os-packages.repo_gpgcheck=0 \
    flatpak \
    bazaar \
    krunner-bazaar

mkdir -p /etc/flatpak/remotes.d
curl --retry 3 -fsSL -o /etc/flatpak/remotes.d/flathub.flatpakrepo \
    https://dl.flathub.org/repo/flathub.flatpakrepo
