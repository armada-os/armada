# armada protontricks RPM, built from Matoking/protontricks at a pinned commit
# with unmerged ARM64 Proton support applied on top.
%global forgeurl https://github.com/Matoking/protontricks
%global shortcommit %(c=%{commit}; echo ${c:0:7})
# %changelog is intentionally empty; don't derive SOURCE_DATE_EPOCH from it.
%global source_date_epoch_from_changelog 0

Name:           protontricks
# overwritten from BASE.env by build.sh
Version:        0
Release:        1%{?dist}.armada
Summary:        Simple wrapper for running Winetricks commands for Proton-enabled games

License:        GPL-3.0-only
URL:            %{forgeurl}
Source0:        %{forgeurl}/archive/%{commit}/%{name}-%{commit}.tar.gz
Patch1:         0001-Add-support-for-ARM64-Proton.patch

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3dist(setuptools)
BuildRequires:  python3dist(setuptools-scm)
BuildRequires:  python3dist(wheel)
BuildRequires:  python3dist(vdf) >= 3.2
BuildRequires:  python3dist(pillow)
BuildRequires:  desktop-file-utils

# Installed manually in Armada, Fedora has a hard dependency on wine-common
# which has no aarch64 package.
#Requires:       winetricks

Recommends:     yad
Suggests:       zenity

%description
Run Winetricks commands for Steam Play/Proton games among other common Wine
features, such as launching external Windows executables.

This build carries Matoking/protontricks#503, unmerged upstream: Proton's
ARM64 builds ship their Wine executables in files/bin-arm64 rather than
files/bin, which stock protontricks cannot find. Armada's default compat
tool is one of those ARM64 builds.

%prep
%autosetup -n %{name}-%{commit} -p1

%build
export SETUPTOOLS_SCM_PRETEND_VERSION=%{version}
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l %{name}
rm -f %{buildroot}%{_bindir}/%{name}-desktop-install

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/*.desktop

%files -f %{pyproject_files}
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/%{name}
%{_bindir}/%{name}-launch
%{_datadir}/applications/*.desktop

%changelog
