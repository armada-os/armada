%global debug_package %{nil}
%global build_cxxflags %{build_cxxflags} %{?armada_march}

Name:           armada-autohdr
# Keep this in sync with CMakeLists.txt.
Version:        0.1.0
Release:        1%{?dist}.armada
Summary:        SDR inverse tone mapping and HDR presentation policy
License:        GPL-2.0-or-later
URL:            https://github.com/armada-os/armada
Source0:        %{name}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  ninja-build

%description
Shared AutoHDR library with inverse tone mapping, presentation policy and
plane-allocation decisions. Compositor adapters supply display and frame data.

%package devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
C API headers and pkg-config metadata for integrating %{name}.

%prep
%autosetup -c -n %{name}

%build
%cmake -G Ninja
%cmake_build

%check
CTEST_OUTPUT_ON_FAILURE=1 %cmake_build --target test

%install
%cmake_install

%files
%doc README.md
%{_libdir}/libarmada-autohdr.so.*

%files devel
%{_includedir}/armada-autohdr.h
%{_libdir}/libarmada-autohdr.so
%{_libdir}/pkgconfig/armada-autohdr.pc

%changelog
