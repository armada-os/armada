# armada SteamOS Manager RPM, built from holo/steamos-manager at a pinned commit
# with the steam-frame series rebased on top. Ships our device configs, not
# upstream's x86 ones.
%global forgeurl https://gitlab.steamos.cloud/holo/steamos-manager
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global userunits steamos-manager.service steamos-manager-session-cleanup.service steamos-manager-configure-cecd.service
# %changelog is intentionally empty; don't derive SOURCE_DATE_EPOCH from it.
%global source_date_epoch_from_changelog 0

Name:           steamos-manager
# overwritten from BASE.env by build.sh
Version:        0
Release:        1%{?dist}.armada
Summary:        System daemon abstracting Steam's interactions with the OS

License:        MIT
URL:            %{forgeurl}
Source0:        %{forgeurl}/-/archive/%{commit}/%{name}-%{commit}.tar.gz
Source1:        platform.toml
Source2:        sm8250.toml
Source3:        sm8550.toml
Source4:        sm8650.toml
Source5:        sm8750.toml
Patch1:         0001-Initial-support-for-Steam-Frame.patch
Patch2:         0002-Factor-out-platform-profiles-into-its-own-manager.patch
Patch3:         0003-Add-a-custom-platform-profile-mechanism.patch
Patch4:         0004-Explicitly-track-state-in-devfreq-gpu-driver.patch
Patch5:         0005-Add-instructions-to-resolve-common-build-issues.patch
Patch6:         0006-Add-gpufreq_limit-to-custom-profiles.patch
Patch7:         0007-Fix-a-bug-where-UI-could-latch-a-bad-manual-clock-va.patch
Patch8:         0008-Add-GPU-manual-clock-minimum-value.patch
Patch9:         0009-Rename-minfreq-field-to-min_freq-for-consistency.patch
Patch10:        0010-Allow-CpuScaling1-to-be-served-by-a-remote-interface.patch
Patch11:        0011-inputplumber-Only-manage-target-devices-when-configu.patch
Patch12:        0012-wifi-Always-write-wpa_supplicant-as-the-backend.patch

BuildRequires:  cargo
BuildRequires:  rust
BuildRequires:  clang-devel
BuildRequires:  mold
BuildRequires:  make
BuildRequires:  glib2-devel
BuildRequires:  speech-dispatcher-devel
BuildRequires:  pkgconfig(libudev)
BuildRequires:  systemd-rpm-macros

Requires:       dbus
# the daemon links libspeechd unconditionally and won't start without it
Requires:       speech-dispatcher-libs
%{?systemd_requires}

%description
SteamOS Manager is the system daemon Steam talks to for OS-level features such
as performance profiles, GPU clocks and TDP. This build carries the Steam Frame
series for devicetree matching, devfreq GPU control and custom platform
profiles, and ships Armada's Snapdragon device configs in place of upstream's.

%prep
%autosetup -n %{name}-%{commit} -p1

%build
make build

%install
%make_install

# upstream's device configs are x86 hardware we don't ship
rm -f %{buildroot}%{_datadir}/steamos-manager/devices/*.toml
install -Dpm0644 %{SOURCE1} %{buildroot}%{_datadir}/steamos-manager/platform.toml
install -dm0755 %{buildroot}%{_datadir}/steamos-manager/devices
install -pm0644 -t %{buildroot}%{_datadir}/steamos-manager/devices \
    %{SOURCE2} %{SOURCE3} %{SOURCE4} %{SOURCE5}

# SteamOS-only: we run SDDM, and orca isn't installed even though libspeechd is
rm -f %{buildroot}%{_unitdir}/sddm.service.d/reset-oneshot-boot.conf
rmdir %{buildroot}%{_unitdir}/sddm.service.d
rm -f %{buildroot}%{_userunitdir}/orca.service

%post
%systemd_post steamos-manager.service
%systemd_user_post %{userunits}

%preun
%systemd_preun steamos-manager.service
%systemd_user_preun %{userunits}

%postun
%systemd_postun_with_restart steamos-manager.service
%systemd_user_postun_with_restart %{userunits}

%files
%license LICENSE
%doc README.md
%{_bindir}/steamosctl
%{_prefix}/lib/steamos-manager
%{_datadir}/dbus-1/interfaces/com.steampowered.SteamOSManager1.xml
%{_datadir}/dbus-1/services/com.steampowered.SteamOSManager1.service
%{_datadir}/dbus-1/system-services/com.steampowered.SteamOSManager1.service
%{_datadir}/dbus-1/system.d/com.steampowered.SteamOSManager1.conf
%dir %{_datadir}/steamos-manager
%{_datadir}/steamos-manager/platform.toml
%dir %{_datadir}/steamos-manager/devices
%{_datadir}/steamos-manager/devices/*.toml
%dir %{_datadir}/steamos-manager/remotes.d
%dir %{_sysconfdir}/steamos-manager
%dir %{_sysconfdir}/steamos-manager/remotes.d
%{_unitdir}/steamos-manager.service
%{_userunitdir}/steamos-manager.service
%{_userunitdir}/steamos-manager-session-cleanup.service
%{_userunitdir}/steamos-manager-configure-cecd.service

%changelog
