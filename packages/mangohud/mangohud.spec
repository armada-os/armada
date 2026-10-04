# armada fork of Fedora's mangohud.spec. Refresh from
# https://src.fedoraproject.org/rpms/mangohud/raw/rawhide/f/mangohud.spec, re-apply patches.
%global appname MangoHud
%global forgeurl https://github.com/flightlessmango/MangoHud
%global tarball_version %%(echo %{version} | tr '~' '-')
# Fedora forces nodownload; let meson fetch subprojects from the wraps at build time.
%global __meson_wrap_mode default
# %changelog is intentionally empty; don't derive SOURCE_DATE_EPOCH from it.
%global source_date_epoch_from_changelog 0

%bcond_with tests

Name:           mangohud
# overwritten from BASE.env by build.sh
Version:        0
Release:        1%{?dist}.armada
Summary:        Vulkan and OpenGL overlay for monitoring FPS, temperatures, CPU/GPU load

License:        MIT
URL:            %{forgeurl}
Source0:        %{forgeurl}/archive/v%{tarball_version}/%{name}-%{tarball_version}.tar.gz

Patch1:         0001-Qualcomm-GPU-support.patch
Patch2:         0002-GPU-monitoring.patch
Patch3:         0003-Battery-name.patch
Patch4:         0004-Qualcomm-battery-power-now.patch
Patch5:         0005-RAM-name.patch
Patch6:         0006-SM8750-Battery.patch
Patch7:         0007-gpu_fdinfo-skip-unreadable-fdinfo.patch

BuildRequires:  vulkan-headers
BuildRequires:  appstream
BuildRequires:  dbus-devel
BuildRequires:  gcc-c++
BuildRequires:  git-core
BuildRequires:  libappstream-glib
BuildRequires:  libstdc++-static
BuildRequires:  meson >= 0.60
BuildRequires:  python3-mako
BuildRequires:  pkgconfig(dri)
BuildRequires:  pkgconfig(glfw3)
BuildRequires:  pkgconfig(glslang)
BuildRequires:  pkgconfig(nlohmann_json)
BuildRequires:  pkgconfig(spdlog)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(x11)
BuildRequires:  pkgconfig(xkbcommon)

Requires:       hicolor-icon-theme
Requires:       vulkan-loader%{?_isa}
Suggests:       %{name}-mangoplot

%global _description %{expand:
A Vulkan and OpenGL overlay for monitoring FPS, temperatures, CPU/GPU load and
more.}

%description %{_description}


%package        mangoplot
Summary:        Local visualization "mangoplot" for %{name}
BuildArch:      noarch
Requires:       %{name} = %{version}-%{release}
Requires:       python3-matplotlib
Requires:       python3-numpy

%description    mangoplot
Local visualization "mangoplot" for %{name}.


%prep
%autosetup -n %{appname}-%{tarball_version} -p1


%build
%meson \
    -Dmangoapp=true \
    -Dmangohudctl=true \
    -Dinclude_doc=true \
    -Duse_system_spdlog=enabled \
    -Dwith_wayland=enabled \
    -Dwith_xnvctrl=disabled \
    -Dtests=disabled \
    -Dwith_fex=true \
    %{nil}
%meson_build


%install
%meson_install

# ERROR: ambiguous python shebang
sed -i "s@#!/usr/bin/env python@#!/usr/bin/python3@" \
    %{buildroot}%{_bindir}/mangoplot

rm -f %{buildroot}%{_libdir}/libimgui.a


%files
%license LICENSE
%doc README.md
%{_bindir}/mangoapp
%{_bindir}/mangohud
%{_bindir}/mangohudctl
%{_datadir}/icons/hicolor/scalable/*/*.svg
%{_datadir}/vulkan/implicit_layer.d/*Mango*.json
%{_docdir}/%{name}/%{appname}.conf.example
%{_docdir}/%{name}/presets.conf.example
%{_libdir}/%{name}/
%{_mandir}/man1/%{name}.1*
%{_mandir}/man1/mangoapp.1*
%{_metainfodir}/*.metainfo.xml

%files mangoplot
%{_bindir}/mangoplot


%changelog
