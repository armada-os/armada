%global debug_package %{nil}
%global source_date_epoch_from_changelog 0

Name:           armada-direct-input
Version:        0.1.0
Release:        1%{?dist}.armada
Summary:        Extra buttons and gyro for the raw rsinput gamepad in direct controller mode
License:        GPL-3.0-or-later
URL:            https://github.com/armada-os/armada

Source0:        armada-direct-input.tar.gz

BuildRequires:  gcc

%description
%{name} writes the back paddles and the Quick Access chord into the raw
rsinput gamepad node when Armada's direct controller mode replaces InputPlumber.
armada-direct-motion feeds the Snapdragon Sensor Core IMU (through libssc,
loaded at runtime) into the rsinput motion sensors node.

%prep
%autosetup -n work

%build
%{__cc} %{optflags} %{build_ldflags} -o %{name} src/%{name}.c
%{__cc} %{optflags} %{build_ldflags} -o armada-direct-motion src/armada-direct-motion.c -lm

%install
install -Dpm 0755 %{name} %{buildroot}%{_libexecdir}/armada/%{name}
%{_libexecdir}/armada/armada-direct-motion
install -Dpm 0755 armada-direct-motion %{buildroot}%{_libexecdir}/armada/armada-direct-motion

%files
%doc README.md
%{_libexecdir}/armada/%{name}

%changelog
