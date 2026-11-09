%global debug_package %{nil}
%global source_date_epoch_from_changelog 0

Name:           armada-direct-input
Version:        0.1.0
Release:        1%{?dist}.armada
Summary:        Extra buttons for the raw rsinput gamepad in direct controller mode
License:        GPL-3.0-or-later
URL:            https://github.com/armada-os/armada

Source0:        armada-direct-input.tar.gz

BuildRequires:  gcc

%description
%{name} writes the back paddles and the Quick Access chord into the raw
rsinput gamepad node when Armada's direct controller mode replaces InputPlumber.

%prep
%autosetup -n work

%build
%{__cc} %{optflags} %{build_ldflags} -o %{name} src/%{name}.c

%install
install -Dpm 0755 %{name} %{buildroot}%{_libexecdir}/armada/%{name}

%files
%doc README.md
%{_libexecdir}/armada/%{name}

%changelog
