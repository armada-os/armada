%global upstream_name uMTP-Responder
%global forgeurl https://github.com/viveris/%{upstream_name}
%global source_date_epoch_from_changelog 0

Name:           umtp-responder
Version:        0
Release:        1%{?dist}.armada
Summary:        Lightweight Media Transfer Protocol responder

License:        GPL-3.0-or-later
URL:            %{forgeurl}
Source0:        %{forgeurl}/archive/%{commit}/%{upstream_name}-%{commit}.tar.gz

Patch1:         0001-portability-use-default-linux-mqueue-depth.patch
Patch2:         0002-storage-use-configured-gid.patch
Patch3:         0003-path-harden-object-path-containment.patch
Patch4:         0004-unicode-support-full-utf8-utf16-conversion.patch
Patch5:         0005-inotify-synchronize-session-database-lifetime.patch

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  systemd-devel

%description
uMTP Responder is a lightweight MTP device-side responder for Linux USB
gadgets. This build enables FunctionFS operation and systemd readiness
notification for Armada integration.

%prep
%autosetup -n %{upstream_name}-%{commit} -p1

%build
%make_build \
    CFLAGS="%{build_cflags} -I./inc -Wall -DSYSTEMD_NOTIFY" \
    LDFLAGS="%{build_ldflags} -lpthread -lrt -lsystemd"

%install
install -Dpm 0755 umtprd %{buildroot}%{_sbindir}/umtprd

%files
%license LICENSE
%doc README.md conf/umtprd.conf
%{_sbindir}/umtprd

%changelog
