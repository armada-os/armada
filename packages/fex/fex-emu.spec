# armada-fex fork of Fedora's fex-emu.spec. Refresh from
# https://src.fedoraproject.org/rpms/fex-emu/raw/rawhide/f/fex-emu.spec.

# empty debugsource subpackage otherwise fails the build
%global debug_package %{nil}

%global shortcommit %(c=%{commit}; echo ${c:0:7})

%global srcname FEX
%global forgeurl https://github.com/FEX-Emu/FEX

# FEX upstream only supports building with clang
%global toolchain clang

%bcond integration 0
%bcond check 0
%bcond x86_debug 0

# Thunks ON: without HostThunks the loader SIGILLs on every x86 binary. Needs has_sysroot=1.
%bcond thunks 1
%global has_sysroot 1
%global sysroot_version fc44-armada

Name:       fex-emu
# Snapshots sort after their base release and before the next release.
Version:    %{base_version}^%{date}git%{shortcommit}
Release:    1%{?dist}.armada
Summary:    Fast usermode x86 and x86-64 emulator for ARM64

# FEX itself is MIT, see below for the bundled libraries
%global fex_license MIT AND Apache-2.0 AND BSL-1.0 AND BSD-3-Clause AND GPL-2.0-only
License:    %{fex_license}
URL:        https://fex-emu.com
%if %{defined commit}
Source0:     %{forgeurl}/archive/%{commit}/%{srcname}-%{commit}.tar.gz
%else
Source0:    %{forgeurl}/archive/%{srcname}-%{version}/%{srcname}-%{srcname}-%{version}.tar.gz
%endif

# coarse aggregate license: the sysroot is a build-time artifact, not shipped
# standalone, so Fedora's per-package fex-sysroot-macros.inc machinery is skipped.
%if 0%{?has_sysroot}
Source3:    fex-sysroot-%{sysroot_version}.tar.gz
Source4:    toolchain_x86_32.cmake
Source5:    toolchain_x86_64.cmake
Source6:    build-fex-sysroot.sh
%global     sysroot_license LGPL-2.1-or-later AND GPL-2.0-or-later AND MIT AND BSD-3-Clause
SourceLicense: %{fex_license} %{sysroot_license}
%endif

# Bundled dependencies managed as git submodules upstream
# These are too entangled with the build system to unbundle for now
# https://github.com/FEX-Emu/FEX/issues/2996
# https://github.com/FEX-Emu/FEX/issues/4267
#
# Run "spectool -g fex-emu.spec" to download archives after updating "externals".
#
%{lua:
local externals = {
  { name="cpp-optparse",    ref="9f94388",   owner="Sonicadvance1",  path="../Source/Common/cpp-optparse",                      license="MIT"},
  { name="drm-headers",     ref="3e49836",   owner="FEX-Emu",        package="kernel",                      version="6.17",     license="GPL-2.0-only"},
  { name="jemalloc",        ref="8436195",   owner="FEX-Emu",        path="jemalloc_glibc",                 version="5.3.0",    license="MIT"},
  { name="range-v3",        ref="ca1388fb9", owner="ericniebler",                                           version="0.12.0",   license="BSL-1.0 AND BSD-3-Clause AND MIT"},
  { name="rpmalloc",        ref="09142d7",   owner="FEX-Emu",                                               version="1.3.0",    license="MIT"},
  { name="Vulkan-Headers",  ref="ee2ec5f",   owner="KhronosGroup",   package="vulkan-headers",              version="1.4.362",  license="Apache-2.0"},
  { name="vixl",            ref="585d860",   owner="FEX-Emu",                                                                   license="MIT"},
  { name="unordered_dense", ref="3234af2",   owner="martinus",                                                                  license="MIT"},
  { name="zydis",           ref="9bfadd6",   owner="zyantific",                                                                 license="MIT"},
}

for i, s in ipairs(externals) do
  si = 100 + i
  print(string.format("Source%d: https://github.com/%s/%s/archive/%s/%s-%s.tar.gz", si, s.owner, s.name, s.ref, s.name, s.ref).."\n")
  if s.bcond and not rpm.isdefined(string.format("with_%s", s.bcond)) then goto continue1 end
  print(string.format("Provides: bundled(%s) = %s", (s.package or s.name), (s.version or "0")).."\n")
  ::continue1::
end

function print_setup_externals()
  for i, s in ipairs(externals) do
    si = 100 + i
    if s.bcond and not rpm.isdefined(string.format("with_%s", s.bcond)) then goto continue2 end
    print(string.format("mkdir -p External/%s", (s.path or s.name)).."\n")
    print(string.format("tar -xzf %s --strip-components=1 -C External/%s", rpm.expand("%{SOURCE"..si.."}"), (s.path or s.name)).."\n")
    ::continue2::
  end
end
}

# FEX upstream only supports these architectures
%if %{with x86_debug}
ExclusiveArch:  %{arm64} %{x86_64}
%else
ExclusiveArch:  %{arm64}
%endif

BuildRequires:  cmake
BuildRequires:  clang
BuildRequires:  git-core
BuildRequires:  lld
BuildRequires:  llvm
BuildRequires:  ninja-build
BuildRequires:  python3
%ifarch %{arm64}
BuildRequires:  python3-setuptools
%endif
BuildRequires:  sed
BuildRequires:  systemd-rpm-macros
%if %{with check}
BuildRequires:  nasm
BuildRequires:  python3-clang
%endif

BuildRequires:  catch-devel
BuildRequires:  fmt-devel
BuildRequires:  libepoxy-devel
BuildRequires:  SDL2-devel
BuildRequires:  xxhash-devel
%ifarch %{x86_64}
BuildRequires:  xbyak-devel
%endif
%if %{with thunks}
BuildRequires:  alsa-lib-devel
BuildRequires:  clang-devel
BuildRequires:  libdrm-devel
BuildRequires:  libglvnd-devel
BuildRequires:  libX11-devel
BuildRequires:  libXrandr-devel
BuildRequires:  llvm-devel
BuildRequires:  openssl-devel
BuildRequires:  wayland-devel
BuildRequires:  zlib-devel
%endif

BuildRequires:  cmake(Qt6Qml)
BuildRequires:  cmake(Qt6Quick)
BuildRequires:  cmake(Qt6Widgets)

Requires:       systemd-udev
Requires:       %{name}-filesystem = %{version}-%{release}
%if %{with thunks}
Recommends:     %{name}-thunks = %{version}-%{release}
%endif

# Fedora rootfs does not work with the Proton/pressure-vessel path.
# Recommends:     fex-emu-rootfs-fedora
# erofs-fuse is REQUIRED, not recommended: FEXServer execvpe's `erofsfuse`
# at startup to mount the rootfs. Absent binary → exec fails → Logger's
# std::thread destructs unjoined → terminate(). Upstream Fedora's spec
# only Recommends it; here it's Requires (image builds with install_weak_deps=False).
Requires:       erofs-fuse
Recommends:     erofs-utils
Recommends:     squashfs-tools
Recommends:     squashfuse

# Drop once f42 is retired
Obsoletes:      fex-emu-gdb < 2409-4
Provides:       fex-emu-gdb = %{version}-%{release}

# This build provides fex-emu-thunks at the matching version; evict any older
# Fedora fex-emu-thunks left dangling on upgrade because their
# Requires: fex-emu = <old-version> can no longer be satisfied.
Obsoletes:      fex-emu-thunks < %{version}-%{release}

# Do not check guest thunks for requires, since these are x86-64 binaries that link against libs in the FEX RootFS.
%global __requires_exclude_from ^%{_datadir}/fex-emu/GuestThunks.*$

# Do not check guest and host thunks for provides, since these are not general system libraries on the host.
%global __provides_exclude_from ^(%{_datadir}/fex-emu/GuestThunks.*|%{_libdir}/fex-emu/HostThunks.*)$

%description
FEX allows you to run x86 and x86-64 binaries on an AArch64 host, similar to
qemu-user and box86. It has native support for a rootfs overlay, so you don't
need to chroot, as well as some thunklibs so it can forward things like GL to
the host. FEX presents a Linux 5.0+ interface to the guest, and supports only
AArch64 as a host. FEX is very much work in progress, so expect things to
change.

%package        filesystem
Summary:        FEX rootfs and overlay filesystem
BuildArch:      noarch

%description    filesystem
%{summary}.

%package        devel
Summary:        Development headers and libraries for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
This package provides development headers and libraries for %{name}.

%package        utils
Summary:        Utility tools for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    utils
This package provides utility tools for %{name} for advanced users.

%if %{with thunks}
%package        thunks
Summary:        Thunk libraries for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    thunks
This package provides host library thunks for %{name}.
%endif

%prep
%if %{defined commit}
%setup -q -n %{srcname}-%{commit}
%else
%setup -q -n %{srcname}-%{srcname}-%{version}
%endif

# Unpack bundled libraries
%{lua: print_setup_externals()}

# Ensure library soversion is set
sed -i FEXCore/Source/CMakeLists.txt \
  -e '/PROPERTIES OUTPUT_NAME/aset_target_properties(${Name} PROPERTIES VERSION %{version})'

%if 0%{?has_sysroot}
  tar xzf %SOURCE3
  cp -p %SOURCE4 %SOURCE5 .
  CPPINC="/$(cd sysroot; ls -d usr/include/c++/*)"
  sed -i "s,%%CPPINC%%,$CPPINC,g" toolchain_*.cmake
%endif

# Disable pac-ret for FEX JIT compatibility; -O3 matches upstream FEX.
%global build_cflags %{build_cflags} -mbranch-protection=none -O3
%global build_cxxflags %{build_cxxflags} -mbranch-protection=none -O3

%build
%cmake -G Ninja \
    -DCMAKE_BUILD_TYPE=release \
    -DTUNE_CPU=cortex-a78 \
    -DENABLE_OFFLINE_TELEMETRY=OFF \
%ifarch %{x86_64}
    -DENABLE_X86_HOST_DEBUG=ON \
%endif
%if %{with thunks}
    -DBUILD_THUNKS=ON \
    -DENABLE_CLANG_THUNKS=ON \
%endif
%if %{with check}
    -DBUILD_TESTING=ON \
%else
    -DBUILD_TESTING=OFF \
%endif
%if %{with integration}
    -DBUILD_FEX_LINUX_TESTS=ON \
%else
    -DBUILD_FEX_LINUX_TESTS=OFF \
%endif
%if 0%{?has_sysroot}
    -DX86_DEV_ROOTFS=$PWD/sysroot \
    -DX86_32_TOOLCHAIN_FILE=$PWD/toolchain_x86_32.cmake \
    -DX86_64_TOOLCHAIN_FILE=$PWD/toolchain_x86_64.cmake \
%endif
    %{nil}

%cmake_build

%install
%cmake_install

# These are used to store RootFS and overlays for FEX that will be provided
# by other packages
install -Ddpm0755 %{buildroot}%{_datadir}/fex-emu/RootFS/
install -Ddpm0755 %{buildroot}%{_datadir}/fex-emu/overlays/

%if %{with thunks}
%if %{with integration}
# This is for running tests only (and gets installed into the wrong libdir)
rm %{buildroot}/usr/lib/libfex_thunk_test.so
%endif
%else
# Not useful without thunks
rm %{buildroot}%{_datadir}/fex-emu/ThunksDB.json
%endif

%postun
if [ $1 -eq 0 ]; then
/bin/systemctl try-restart systemd-binfmt.service
fi

%if %{with check}
%check
%ctest
%endif

%files
%license LICENSE
%doc Readme.md docs
%{_bindir}/FEX
%{_bindir}/FEXBash
%{_bindir}/FEXGetConfig
%{_bindir}/FEXOfflineCompiler
%{_bindir}/FEXpidof
%{_bindir}/FEXServer
%{_libdir}/libFEXCore.so.%{version}
%ifnarch %{x86_64}
%{_binfmtdir}/FEX-x86.conf
%{_binfmtdir}/FEX-x86_64.conf
%endif
%{_datadir}/fex-emu/AppConfig/
%{_mandir}/man1/FEX.1*

%files filesystem
%dir %{_datadir}/fex-emu/
%dir %{_datadir}/fex-emu/RootFS
%dir %{_datadir}/fex-emu/overlays

%files devel
%{_includedir}/FEXCore/
%{_libdir}/libFEXCore.so

%files utils
%{_bindir}/FEXConfig
%{_bindir}/FEXRootFSFetcher

%if %{with thunks}
%files thunks
%{_libdir}/fex-emu/HostThunks/
%{_libdir}/fex-emu/HostThunks_32/
%{_datadir}/fex-emu/ThunksDB.json
%{_datadir}/fex-emu/GuestThunks/
%{_datadir}/fex-emu/GuestThunks_32/
%endif

%changelog
