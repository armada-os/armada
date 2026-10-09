%global debug_package %{nil}
%global source_date_epoch_from_changelog 0

Name:           armada-rgb
# Keep this in sync with Cargo.toml.
Version:        0.1.0
Release:        1%{?dist}.armada
Summary:        RGB lighting controller for Armada
License:        GPL-3.0-or-later
URL:            https://github.com/armada-os/armada-packages

Source0:        armada-rgb.tar.gz

BuildRequires:  cargo
BuildRequires:  rust

%description
%{name} controls RGB lighting on handheld devices.

%prep
%autosetup -n work

%build
cargo build --release --locked

%install
install -Dpm 0755 target/release/%{name} %{buildroot}%{_bindir}/%{name}
install -Dpm 0644 profiles.json %{buildroot}%{_datadir}/%{name}/profiles.json

%files
%doc README.md
%{_bindir}/%{name}
%{_datadir}/%{name}/profiles.json

%changelog
