%global debug_package %{nil}
%global source_date_epoch_from_changelog 0

Name:           dtbloader
Version:        0
Release:        1%{?dist}.armada
Summary:        EFI driver that installs a devicetree for the running device

# dtbloader is BSD-3-Clause; bundled libfdt, gnu-efi and sha1 are linked in.
License:        BSD-3-Clause AND (GPL-2.0-or-later OR BSD-2-Clause) AND BSD-2-Clause AND LicenseRef-Fedora-Public-Domain
URL:            https://github.com/TravMurav/dtbloader
Source0:        %{url}/releases/download/%{version}/dtbloader-%{version}.tar.gz

ExclusiveArch:  aarch64
BuildRequires:  clang
BuildRequires:  lld
BuildRequires:  llvm
BuildRequires:  make

%description
dtbloader picks the devicetree for the running device and installs it in the
UEFI configuration table, for platforms whose firmware does not provide one.

%prep
%autosetup

%build
%make_build ARCH=aarch64

%install
install -Dpm 0644 build-aarch64/dtbloader.efi %{buildroot}%{_prefix}/lib/dtbloader/dtbloaderaa64.efi

%files
%license LICENSE
%doc README.md
%{_prefix}/lib/dtbloader/dtbloaderaa64.efi

%changelog
