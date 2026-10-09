%global debug_package %{nil}

Name:           armada-splash
# Always update the version when you update the package
Version:        1
Release:        1%{?dist}.armada
Summary:        Boot splash for Armada
License:        GPL-2.0-or-later
URL:            https://github.com/armada-os/armada-packages

Source0:        armada-splash.tar.gz

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  libX11-devel
BuildRequires:  libdrm-devel

%description
%{name} is the boot splash that Armada uses instead of Plymouth

%prep
%autosetup -n work

%build
%make_build

%install
%make_install

%files
%license LICENSE.md
%doc README.md
%{_prefix}/lib/dracut/modules.d/91armada-splash/*
%{_prefix}/lib/systemd/system/sddm.service.d/armada*.conf
%{_prefix}/lib/systemd/system/armada*.service
%{_libexecdir}/armada/armada*

%changelog
* Mon Aug 03 2026 Radical <radical@radical.fun> - 1-1
- Initial package
