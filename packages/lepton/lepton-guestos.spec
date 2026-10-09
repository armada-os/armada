%global debug_package %{nil}
# The overlay holds Android libraries; their sonames are not host dependencies.
%global __requires_exclude_from ^%{_datadir}/steam/compatibilitytools.d/lepton-armada/overlay/.*$
%global __provides_exclude_from ^%{_datadir}/steam/compatibilitytools.d/lepton-armada/overlay/.*$

Name:           lepton-guestos
# Always update the version when you update the package
Version:        1
Release:        1%{?dist}.armada
Summary:        Host side of Steam's Lepton Android compatibility tool
License:        MIT
URL:            https://github.com/armada-os/armada
ExclusiveArch:  aarch64

Source0:        guestos-android.erofs
Source1:        usr-share-guestos-android.mount
Source2:        steamvr
Source3:        VkLayer_fossilize.json
Source4:        lepton-armada
Source5:        compatibilitytool.vdf
Source6:        toolmanifest.vdf
Source7:        launcher.patch
Source8:        overlay.tar

BuildRequires:  systemd-rpm-macros

# Lepton drives rootless podman with pasta networking.
Requires:       podman
Requires:       catatonit
Requires:       passt
# Its launch scripts.
Requires:       inotify-tools
Requires:       attr
Requires:       jq
Requires:       util-linux
Requires:       android-tools

%description
Mesa, the Fossilize layer and other files Lepton (Steam app 3029110) expects
the OS to provide under /usr/share/guestos/android, plus the host tools and
paths its scripts assume.

%package -n lepton-armada
Summary:        Lepton (Armada) compat tool, Lepton with controllers and a second display
Requires:       lepton-guestos = %{version}-%{release}
Requires:       patch

%description -n lepton-armada
Lepton (Armada) compat tool. On launch it patches a copy of Lepton's launcher
scripts to pass Steam Input's controllers to Android and to give Android the
secondary screen as an external display, redone whenever Steam updates Lepton.

%prep

%build

%install
install -Dpm 0644 %{SOURCE0} %{buildroot}%{_datadir}/armada/lepton/guestos-android.erofs
install -dm 0755 %{buildroot}%{_datadir}/guestos/android
install -Dpm 0644 %{SOURCE1} %{buildroot}%{_unitdir}/usr-share-guestos-android.mount
install -Dpm 0755 %{SOURCE2} %{buildroot}%{_bindir}/steamvr
# Lepton reads layer IDs from any JSON under /usr/share/vulkan; the host loader only scans *_layer.d.
install -Dpm 0644 %{SOURCE3} %{buildroot}%{_datadir}/vulkan/guestos-android/VkLayer_fossilize.json
# Lepton hardcodes Debian's adb path.
install -dm 0755 %{buildroot}%{_prefix}/lib/android-sdk/platform-tools
ln -s ../../../bin/adb %{buildroot}%{_prefix}/lib/android-sdk/platform-tools/adb
install -Dpm 0755 %{SOURCE4} %{buildroot}%{_datadir}/steam/compatibilitytools.d/lepton-armada/lepton
install -Dpm 0644 -t %{buildroot}%{_datadir}/steam/compatibilitytools.d/lepton-armada %{SOURCE5} %{SOURCE6} %{SOURCE7}
# Android 11 only, so these reach lepton-armada's copy and not the directory every Lepton mounts.
install -dm 0755 %{buildroot}%{_datadir}/steam/compatibilitytools.d/lepton-armada/overlay
tar -C %{buildroot}%{_datadir}/steam/compatibilitytools.d/lepton-armada/overlay -xf %{SOURCE8}

%files
%{_datadir}/armada/lepton/
%dir %{_datadir}/guestos
%dir %{_datadir}/guestos/android
%{_unitdir}/usr-share-guestos-android.mount
%{_bindir}/steamvr
%{_datadir}/vulkan/guestos-android/
%{_prefix}/lib/android-sdk/

%files -n lepton-armada
%{_datadir}/steam/compatibilitytools.d/lepton-armada/

%changelog
* Thu Oct 01 2026 Radical <radical@radical.fun> - 1-1
- Initial package
