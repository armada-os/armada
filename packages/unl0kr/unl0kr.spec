%global upstream_name buffybox
%global source_date_epoch_from_changelog 0

Name:           unl0kr
Version:        3.5.1
Release:        1%{?dist}.armada
Summary:        On-screen keyboard disk unlocker for the initramfs

License:        GPL-3.0-or-later
URL:            https://gitlab.postmarketos.org/postmarketOS/buffybox

Source0:        %{url}/-/archive/%{version}/%{upstream_name}-%{version}.tar.bz2
# lvgl is a submodule, see BASE.env.
Source1:        https://github.com/lvgl/lvgl/archive/%{lvgl_commit}/lvgl-%{lvgl_commit}.tar.gz

# unl0kr has no rotation support.
# Added via this patch.
Patch0:         0001-unl0kr-add-configurable-display-rotation.patch

# Screen clearing is broken in multiple ways in upstream.
# Patched to clear to black on every exit path.
Patch1:         0002-unl0kr-fix-clear-on-exit.patch


BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  scdoc
BuildRequires:  inih-devel
BuildRequires:  pkgconfig(libinput)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libsystemd)
BuildRequires:  pkgconfig(libudev)

Requires:       cryptsetup
Requires:       libinput
Requires:       systemd-udev
Requires:       libxkbcommon

%description
unl0kr renders an on-screen keyboard directly to the framebuffer.
This keyboard is used to unlock LUKS volumes with a touchscreen.

Built from the buffybox repo with -Dsystemd=true; buffyboard is not installed.

%prep
%setup -q -n %{upstream_name}-%{version}
%patch -P 0 -p1
%patch -P 1 -p1
# Replace the empty submodule dir with the pinned lvgl tree
rm -rf lvgl
tar -xf %{SOURCE1}
mv lvgl-%{lvgl_commit} lvgl

%build
%meson -Dsystemd=true -Dman=true
%meson_build

%install
# --tags=unl0kr excludes buffyboard
%meson_install --tags=unl0kr

%files
%license COPYING
%doc README.md CHANGELOG.md
%{_bindir}/unl0kr
# The agent is a separate binary in libexecdir, invoked by the unit below.
%{_libexecdir}/unl0kr-agent
%config(noreplace) %{_sysconfdir}/unl0kr.conf
%{_prefix}/lib/systemd/system/unl0kr-agent.service
%{_prefix}/lib/systemd/system/unl0kr-agent.path
%{_mandir}/man1/unl0kr.1*
%{_mandir}/man5/unl0kr.conf.5*

%changelog
* Wed Sep 23 2026 Armada <armada@armada-os> - 3.5.1-1
- Initial package
- rotation config option added
- fixed screen clearing (broken in upstream)
