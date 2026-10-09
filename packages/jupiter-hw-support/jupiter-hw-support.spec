%global upstream_name jupiter-hw-support
%global packagever jupiter-3.7-20251020.1
%global source_date_epoch_from_changelog 0

Name:           armada-jupiter-hw-support
Version:        0
Release:        1%{?dist}.armada
Summary:        SteamOS-compatible storage and system helpers for Armada

License:        GPL-3.0-or-later
URL:            https://gitlab.com/evlaV/jupiter-hw-support
Source0:        %{url}/-/archive/%{packagever}/%{upstream_name}-%{packagever}.tar.gz
Source1:        org.armada.jupiter-hw-support.policy
Source2:        50-armada-jupiter-hw-support.rules
Patch1:         0001-armada-storage-behavior.patch
Patch2:         0002-armada-polkit-helper-safety.patch

BuildArch:      noarch
BuildRequires:  systemd-rpm-macros

Requires:       bash
Requires:       coreutils
Requires:       e2fsprogs
Requires:       exfatprogs
Requires:       f3
Requires:       jq
Requires:       openssh-server
Requires:       parted
Requires:       polkit
Requires:       systemd
Requires:       udisks2
Requires:       util-linux

%description
SteamOS-compatible storage and system helper subset adapted for Armada. This
package intentionally avoids Steam Deck firmware, fan, ALS, GPU, and
priv-write helpers.

%prep
%autosetup -n %{upstream_name}-%{packagever} -p1

%build

%install
install -Dpm 0644 usr/lib/hwsupport/common-functions %{buildroot}%{_prefix}/lib/hwsupport/common-functions
install -Dpm 0755 usr/lib/hwsupport/block-device-event.sh %{buildroot}%{_prefix}/lib/hwsupport/block-device-event.sh
install -Dpm 0755 usr/lib/hwsupport/steamos-automount.sh %{buildroot}%{_prefix}/lib/hwsupport/steamos-automount.sh
install -Dpm 0755 usr/lib/hwsupport/format-device.sh %{buildroot}%{_prefix}/lib/hwsupport/format-device.sh
install -Dpm 0755 usr/lib/hwsupport/format-sdcard.sh %{buildroot}%{_prefix}/lib/hwsupport/format-sdcard.sh

install -Dpm 0644 usr/lib/udev/rules.d/99-steamos-automount.rules %{buildroot}%{_prefix}/lib/udev/rules.d/99-steamos-automount.rules

install -Dpm 0755 usr/bin/steamos-polkit-helpers/steamos-format-device %{buildroot}%{_bindir}/steamos-polkit-helpers/steamos-format-device
install -Dpm 0755 usr/bin/steamos-polkit-helpers/steamos-format-sdcard %{buildroot}%{_bindir}/steamos-polkit-helpers/steamos-format-sdcard
install -Dpm 0755 usr/bin/steamos-polkit-helpers/steamos-set-hostname %{buildroot}%{_bindir}/steamos-polkit-helpers/steamos-set-hostname
install -Dpm 0755 usr/bin/steamos-polkit-helpers/steamos-enable-sshd %{buildroot}%{_bindir}/steamos-polkit-helpers/steamos-enable-sshd

install -Dpm 0644 %{SOURCE1} %{buildroot}%{_datadir}/polkit-1/actions/org.armada.jupiter-hw-support.policy
install -Dpm 0644 %{SOURCE2} %{buildroot}%{_datadir}/polkit-1/rules.d/50-armada-jupiter-hw-support.rules

%files
%{_prefix}/lib/hwsupport/common-functions
%{_prefix}/lib/hwsupport/block-device-event.sh
%{_prefix}/lib/hwsupport/steamos-automount.sh
%{_prefix}/lib/hwsupport/format-device.sh
%{_prefix}/lib/hwsupport/format-sdcard.sh
%{_prefix}/lib/udev/rules.d/99-steamos-automount.rules
%{_bindir}/steamos-polkit-helpers/steamos-format-device
%{_bindir}/steamos-polkit-helpers/steamos-format-sdcard
%{_bindir}/steamos-polkit-helpers/steamos-set-hostname
%{_bindir}/steamos-polkit-helpers/steamos-enable-sshd
%{_datadir}/polkit-1/actions/org.armada.jupiter-hw-support.policy
%{_datadir}/polkit-1/rules.d/50-armada-jupiter-hw-support.rules

%changelog
