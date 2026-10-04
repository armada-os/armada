%global debug_package %{nil}
%global source_date_epoch_from_changelog 0
# Set by generate.sh from BASE.env.
%{!?steam_version:%global steam_version 0}

Name:           steam
Version:        %{steam_version}
Release:        1%{?dist}.armada
Summary:        Steam client launcher and installer for Armada
License:        LicenseRef-Steam
URL:            https://github.com/armada-os/armada-packages
BuildArch:      noarch

Source0:        steam.tar.gz

%description
%{name} carries Steam Frame's launcher layout (bin_steam.sh, the steam symlink,
steam.desktop and /usr/bin/steam) and the scripts that start, install, repair
and verify the Steam client. The client itself is staged into the user's home
when the image is built; repairs restore it from the booted image.

%prep
%autosetup -n work

%install
mkdir -p %{buildroot}
cp -a system/. %{buildroot}/

%files
%license LICENSE.md
%{_bindir}/steam
%{_datadir}/applications/steam.desktop
%{_prefix}/lib/steam/bin_steam.sh
%{_prefix}/lib/steam/steam
%{_prefix}/lib/steam/steam.desktop
%{_prefix}/lib/steam/armada-steam-run
%{_prefix}/lib/steam/steam-install
%{_prefix}/lib/steam/steam-verify

%changelog
* Sun Oct 04 2026 Radical <radical@radical.fun> - 0-1
- Initial package
