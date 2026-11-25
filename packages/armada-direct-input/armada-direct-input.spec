%global debug_package %{nil}
%global source_date_epoch_from_changelog 0

Name:           armada-direct-input
Version:        0.1.0
Release:        1%{?dist}.armada
Summary:        Gyro for the raw rsinput gamepad in direct controller mode
License:        GPL-3.0-or-later
URL:            https://github.com/armada-os/armada

Source0:        armada-direct-input.tar.gz

BuildRequires:  gcc

%description
armada-direct-motion feeds the Snapdragon Sensor Core IMU (through libssc,
loaded at runtime) into the rsinput motion sensors node when Armada's direct
controller mode replaces InputPlumber.

%prep
%autosetup -n work

%build
%{__cc} %{optflags} %{build_ldflags} -o armada-direct-motion src/armada-direct-motion.c -lm

%install
install -Dpm 0755 armada-direct-motion %{buildroot}%{_libexecdir}/armada/armada-direct-motion

%files
%doc README.md
%{_libexecdir}/armada/armada-direct-motion

%changelog
