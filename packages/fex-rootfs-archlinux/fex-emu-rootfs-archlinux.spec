%global image_version 2026-08-11
%global image_sha256 5d0c1a38590c68e5c2597c2c8a26d2f80170b1b738c857d63e1cdadada5f5f2a


Name:           fex-emu-rootfs-archlinux
Version:        %{lua: return (rpm.expand("%{image_version}"):gsub("-", ""))}
Release:        1%{?dist}.armada
Summary:        Arch-based RootFS for the FEX emulator

# Generated from the Kiwi packages list with
#  gen-license-tag.py Fedora-FEX-RootFS-*.x86_64.packages
License:        (( GPL-1.0-or-later OR Artistic-1.0-Perl ) AND BSD-3-Clause) AND ((AFL-2.1 OR GPL-2.0-or-later) AND GPL-2.0-or-later) AND ((FTL OR GPL-2.0-or-later) AND BSD-3-Clause AND MIT AND MIT-Modern-Variant AND LicenseRef-Fedora-Public-Domain AND Zlib) AND ((GPL-1.0-or-later OR Artistic-1.0-Perl) AND Artistic-2.0) AND ((GPL-1.0-or-later OR Artistic-1.0-Perl) AND FSFAP) AND ((GPL-1.0-or-later OR Artistic-1.0-Perl) AND MPL-2.0) AND ((GPL-1.0-or-later OR Artistic-1.0-Perl) AND Martin-Birgmeier AND Spencer-86 AND MIT AND Unicode-3.0 AND LicenseRef-Fedora-Public-Domain) AND ((GPL-1.0-or-later OR Artistic-1.0-Perl) AND metamail) AND ((GPL-2.0-or-later OR LGPL-3.0-or-later) AND GPL-3.0-or-later) AND ((LGPL-3.0-or-later OR GPL-2.0-or-later OR (LGPL-3.0-or-later AND GPL-2.0-or-later)) AND GFDL-1.3-invariants-or-later) AND ((MPL-2.0 OR LGPL-2.1-or-later) AND Apache-2.0 WITH LLVM-exception AND BSD-3-Clause AND CC0-1.0 AND GPL-3.0-or-later AND IJG AND ISC AND MIT AND Unicode-3.0 AND Unicode-DFS-2016 AND (0BSD OR MIT OR Apache-2.0) AND (Apache-2.0 OR MIT) AND (Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT) AND (BSD-2-Clause OR Apache-2.0 OR MIT) AND (BSD-3-Clause OR Apache-2.0) AND (MIT OR Apache-2.0 OR Zlib) AND (Unlicense OR MIT)) AND (0BSD AND GPL-2.0-or-later AND LicenseRef-Fedora-Public-Domain) AND (Apache-2.0 AND BSD-3-Clause WITH AdditionRef-WebM-patent-license AND BSD-3-Clause AND FSFULLRWD) AND (Apache-2.0 AND BSD-3-Clause) AND (Apache-2.0 AND GPL-3.0-or-later AND MIT) AND (Apache-2.0 AND LGPL-2.0-or-later AND LGPL-2.1-or-later AND (Apache-2.0 OR LGPL-2.1-or-later)) AND (Apache-2.0 WITH LLVM-exception AND BSD-3-Clause AND Zlib AND BSD-2-Clause) AND (Apache-2.0 WITH LLVM-exception OR NCSA OR MIT) AND (Apache-2.0 WITH LLVM-exception OR NCSA) AND (BSD-2-Clause AND BSD-3-Clause) AND (BSD-2-Clause AND FSFULLR AND GPL-2.0-or-later WITH Libtool-exception AND BSD-3-Clause AND FSFUL) AND (BSD-2-Clause AND IJG AND Apache-2.0 AND BSD-3-Clause) AND (BSD-2-Clause AND ISC AND MIT AND LicenseRef-BSD-2-Clause-WITH-AdditionRef-AOMPL-1.0 AND (Apache-2.0 OR MIT) AND (Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT) AND (Unlicense OR MIT)) AND (BSD-2-Clause AND ISC) AND (BSD-2-Clause AND MIT) AND (BSD-2-Clause and LGPL-2.1-or-later) AND (BSD-2-Clause-Darwin AND BSD-2-Clause) AND (BSD-3-Clause AND (BSD-3-Clause OR GPL-2.0-only) AND GPL-2.0-or-later AND LGPL-2.1-or-later AND LGPL-2.0-or-later AND MIT-Modern-Variant) AND (BSD-3-Clause AND Apache-2.0 AND Zlib) AND (BSD-3-Clause AND BSD-2-Clause AND GPL-3.0-or-later) AND (BSD-3-Clause AND BSD-2-Clause AND ISC) AND (BSD-3-Clause AND BSD-2-Clause) AND (BSD-3-Clause AND FSFULLR AND X11 AND GPL-2.0-or-later AND FSFAP AND FSFUL AND GPL-3.0-or-later) AND (BSD-3-Clause AND GPL-2.0-or-later AND GFDL-1.3-or-later) AND (BSD-3-Clause AND GPL-2.0-or-later) AND (BSD-3-Clause AND ISC AND LicenseRef-Fedora-Public-Domain) AND (BSD-3-Clause AND LGPL-2.1-or-later) AND (BSD-3-Clause AND MIT AND LicenseRef-Fedora-Public-Domain) AND (BSD-3-Clause AND MIT-open-group AND Zlib AND Apache-2.0) AND (BSD-3-Clause OR GPL-2.0-only) AND (BSD-3-Clause OR GPL-2.0-or-later) AND (BSD-3-clause AND TU-Berlin-1.0) AND (Brian-Gladman-2-Clause AND BSD-2-Clause AND (BSD-2-Clause OR GPL-2.0-or-later) AND BSD-2-Clause-first-lines AND BSD-3-Clause AND BSD-4-Clause AND CMU-Mach-nodoc AND FSFULLRWD AND HPND AND HPND-export2-US AND HPND-export-US AND HPND-export-US-acknowledgement AND HPND-export-US-modify AND ISC AND MIT AND MIT-CMU AND OLDAP-2.8 AND OpenVision) AND (CC0-1.0 AND GPL-2.0-or-later AND GPL-3.0-or-later AND LGPL-2.1-or-later AND LGPL-3.0-or-later AND (BSD-3-Clause OR LGPL-3.0-or-later OR GPL-2.0-or-later) AND CC-BY-4.0 AND MIT) AND (GPL-1.0-or-later AND GPL-2.0-only AND GPL-2.0-or-later AND GPL-3.0-or-later AND LGPL-2.1-or-later AND BSD-2-Clause AND BSD-3-Clause AND BSD-4-Clause-UC AND LicenseRef-Fedora-Public-Domain) AND (GPL-1.0-or-later AND GPL-2.0-or-later AND GPL-3.0-or-later WITH Autoconf-exception-generic) AND (GPL-1.0-or-later OR Artistic-1.0-Perl) AND (GPL-2.0-only AND GPL-2.0-or-later AND BSD-2-Clause AND BSD-3-Clause AND BSD-4-Clause-UC AND LicenseRef-Fedora-Public-Domain) AND (GPL-2.0-only AND GPL-2.0-or-later AND LGPL-2.0-only AND LGPL-2.0-or-later AND LGPL-2.1-or-later AND LGPL-3.0-or-later AND BSD-3-Clause AND IJG-short AND (MIT OR Unlicense)) AND (GPL-2.0-only OR BSD-2-Clause AND BSD-3-Clause) AND (GPL-2.0-or-later AND BSD-2-Clause) AND (GPL-2.0-or-later AND GPL-3.0-or-later AND FSFUL AND FSFULLRWD AND LGPL-2.1-only AND LGPL-2.1-or-later AND X11) AND (GPL-2.0-or-later AND LGPL-2.0-or-later AND LGPL-2.1-or-later AND BSD-2-Clause) AND (GPL-2.0-or-later AND LGPL-2.1-only AND MIT AND BSD-4-Clause-UC AND MS-PL AND MPL-1.1) AND (GPL-2.0-or-later AND LGPL-2.1-or-later) AND (GPL-2.0-or-later AND MIT) AND (GPL-2.0-or-later OR Artistic-1.0-Perl) AND (GPL-2.0-or-later OR LGPL-2.1-or-later) AND (GPL-2.0-or-later OR LGPL-3.0-or-later) AND (GPL-2.0-or-later WITH Autoconf-exception-generic) AND (GPL-2.0-or-later WITH SANE-exception AND GPL-2.0-or-later AND GPL-2.0-only AND LGPL-2.0-or-later AND LGPL-2.1-or-later AND LicenseRef-Fedora-Public-Domain AND IJG AND MIT) AND (GPL-3.0-or-later AND (GPL-3.0-or-later WITH Bison-exception-2.2) AND (LGPL-2.0-or-later WITH GCC-exception-2.0) AND BSD-3-Clause AND GFDL-1.3-or-later AND GPL-2.0-or-later AND LGPL-2.1-or-later AND LGPL-2.0-or-later) AND (GPL-3.0-or-later AND (GPL-3.0-or-later WITH GCC-exception-3.1) AND GPL-2.0-or-later AND (GPL-2.0-or-later WITH GCC-exception-2.0) AND LGPL-2.0-or-later) AND (GPL-3.0-or-later AND GFDL-1.3-no-invariants-or-later AND LGPL-2.1-or-later AND LGPL-3.0-or-later) AND (GPL-3.0-or-later AND GFDL-1.3-only) AND (GPL-3.0-or-later AND GFDL-1.3-or-later AND BSD-4-Clause-UC AND MIT AND X11 AND LicenseRef-Fedora-Public-Domain) AND (GPL-3.0-or-later AND GPL-2.0-or-later AND GFDL-1.3-no-invariants-or-later) AND (GPL-3.0-or-later AND GPL-2.0-or-later AND LGPL-2.1-or-later AND BSD-3-Clause) AND (GPL-3.0-or-later AND LGPL-2.1-or-later AND (LGPL-3.0-or-later OR GPL-2.0-or-later)) AND (GPL-3.0-or-later AND LGPL-2.1-or-later AND LGPL-3.0-or-later) AND (GPL-3.0-or-later AND LGPL-2.1-or-later) AND (GPL-3.0-or-later AND LGPL-3.0-or-later AND (GPL-3.0-or-later WITH GCC-exception-3.1) AND (GPL-3.0-or-later WITH Texinfo-exception) AND (LGPL-2.1-or-later WITH GCC-exception-2.0) AND (GPL-2.0-or-later WITH GCC-exception-2.0) AND (GPL-2.0-or-later WITH GNU-compiler-exception) AND BSL-1.0 AND GFDL-1.3-or-later AND Linux-man-pages-copyleft-2-para AND SunPro AND BSD-1-Clause AND BSD-2-Clause AND BSD-2-Clause-Views AND BSD-3-Clause AND BSD-4-Clause AND BSD-Source-Code AND Zlib AND MIT AND Apache-2.0 AND (Apache-2.0 WITH LLVM-Exception) AND ZPL-2.1 AND ISC AND LicenseRef-Fedora-Public-Domain AND HP-1986 AND curl AND Martin-Birgmeier AND HPND-Markus-Kuhn AND dtoa AND SMLNJ AND AMD-newlib AND OAR AND HPND-merchantability-variant AND HPND-Intel) AND (GPL-3.0-or-later AND LGPL-3.0-or-later AND LGPL-2.1-or-later AND GPL-2.0-or-later AND LGPL-2.0-or-later AND GFDL-1.3-no-invariants-or-later) AND (GPL-3.0-or-later AND LGPL-3.0-or-later) AND (GPL-3.0-or-later AND MIT AND Unicode-DFS-2016 AND (0BSD OR MIT OR Apache-2.0) AND (Apache-2.0 OR MIT) AND (Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT) AND (BSD-2-Clause OR Apache-2.0 OR MIT) AND (MIT OR Zlib OR Apache-2.0) AND (Unlicense OR MIT)) AND (GPL-3.0-or-later AND MIT AND Unicode-DFS-2016 AND (0BSD OR MIT OR Apache-2.0) AND (Apache-2.0 OR MIT) AND (BSD-2-Clause OR Apache-2.0 OR MIT) AND (MIT OR Zlib OR Apache-2.0) AND (Unlicense OR MIT)) AND (HPND AND HPND-sell-variant AND X11 AND X11-distribute-modifications-variant AND MIT AND MIT-open-group AND xkeyboard-config-Zinoviev) AND (HPND AND LicenseRef-Fedora-Public-Domain AND Unicode-DFS-2016) AND (HPND AND MIT) AND (ISC AND BSD-2-Clause AND BSD-3-Clause AND BSD-4-Clause-UC) AND (ISC AND BSD-4-Clause AND BSD-2-Clause AND pkgconf AND MIT) AND (LGPL-2.0-or-later AND Apache-2.0 AND BSD-3-Clause AND BSL-1.0 AND MIT AND Unicode-3.0 AND Unicode-DFS-2016 AND (Apache-2.0 OR MIT) AND (Unlicense OR MIT)) AND (LGPL-2.0-or-later AND BSD-3-Clause AND GPL-2.0-or-later AND Apache-2.0 AND (LGPL-2.0-or-later AND BSD-3-Clause) AND (MIT WITH fmt-exception) AND NCL AND MIT AND LicenseRef-Fedora-Public-Domain) AND (LGPL-2.0-or-later AND LGPL-2.1-or-later) AND (LGPL-2.1-only OR MPL-1.1) AND (LGPL-2.1-or-later AND (BSD-3-Clause OR LGPL-2.1-or-later) AND FSFULLR AND GPL-2.0-or-later) AND (LGPL-2.1-or-later AND Apache-2.0 AND BSD-3-Clause AND MIT AND MPL-2.0 AND Unicode-3.0 AND Unicode-DFS-2016 AND (0BSD OR MIT OR Apache-2.0) AND (Apache-2.0 OR MIT) AND (BSD-3-Clause OR Apache-2.0) AND (MIT OR Apache-2.0 OR Zlib) AND (Unlicense OR MIT)) AND (LGPL-2.1-or-later AND BSD-3-Clause AND BSD-2-Clause AND BSD-2-Clause-FreeBSD AND 0BSD AND CC0-1.0 AND LicenseRef-Fedora-Public-Domain) AND (LGPL-2.1-or-later AND GPL-2.0-or-later AND BSD-3-Clause) AND (LGPL-2.1-or-later AND GPL-2.0-or-later AND IJG-short AND BSD-2-Clause) AND (LGPL-2.1-or-later AND LGPL-2.0-or-later AND BSD-2-Clause-Views AND MIT) AND (LGPL-2.1-or-later AND LGPL-2.1-only AND BSD-2-Clause) AND (LGPL-2.1-or-later AND MIT AND GPL-2.0-or-later) AND (LGPL-2.1-or-later AND MIT) AND (LGPL-2.1-or-later AND SunPro AND LGPL-2.1-or-later WITH GCC-exception-2.0 AND BSD-3-Clause AND GPL-2.0-or-later AND LGPL-2.1-or-later WITH GNU-compiler-exception AND GPL-2.0-only AND ISC AND LicenseRef-Fedora-Public-Domain AND HPND AND CMU-Mach AND LGPL-2.0-or-later AND Unicode-3.0 AND GFDL-1.1-or-later AND GPL-1.0-or-later AND FSFUL AND MIT AND Inner-Net-2.0 AND X11 AND GPL-2.0-or-later WITH GCC-exception-2.0 AND GFDL-1.3-only AND GFDL-1.1-only AND GPL-3.0-or-later AND GPL-3.0-or-later WITH Autoconf-exception-generic-3.0 AND GPL-3.0-or-later WITH Texinfo-exception) AND (LGPL-2.1-or-later AND Unicode-DFS-2016) AND (LGPL-2.1-or-later OR MPL-2.0 OR GPL-2.0-or-later) AND (LGPL-3.0-only OR CC-BY-SA-3.0) AND (LGPL-3.0-or-later OR GPL-2.0-or-later) AND (LGPL-3.0-or-later and MIT) AND (LicenseRef-BSD-3-Clause-Clear-WITH-AdditionRef-AOMPL-1.0 AND MIT AND ISC AND LicenseRef-Fedora-Public-Domain AND BSD-2-Clause) AND (LicenseRef-Callaway-BSD AND LicenseRef-Callaway-MIT) AND (LicenseRef-Callaway-LGPLv2 AND LicenseRef-Callaway-MIT) AND (LicenseRef-Callaway-LGPLv2+ AND Zlib) AND (LicenseRef-Callaway-MPLv1.1 OR GPL-2.0-or-later OR LicenseRef-Callaway-LGPLv2+) AND (LicenseRef-Fedora-Public-Domain AND (GPL-2.0-only WITH ClassPath-exception-2.0)) AND (LicenseRef-Fedora-Public-Domain AND ZPL-2.1) AND (MIT AND BSD-3-Clause AND SGI-B-2.0) AND (MIT AND CC-PDDC AND (GPL-3.0-or-later WITH Texinfo-exception)) AND (MIT AND GPL-2.0-or-later) AND (MIT AND GPL-3.0-or-later) AND (MIT AND HPND-sell-variant AND ICU) AND (MIT AND HPND-sell-variant AND SMLNJ AND MIT-open-group AND X11) AND (MIT AND HPND-sell-variant) AND (MIT AND ISC-Veillard AND W3C) AND (MIT AND LicenseRef-Fedora-Public-Domain) AND (MIT AND MIT-open-group AND X11) AND (MIT AND MIT-open-group) AND (MIT AND PSF-2.0 AND GPL-2.0-or-later) AND (MIT AND Python-2.0.1 AND Apache-2.0 AND BSD-2-Clause AND BSD-3-Clause AND ISC AND MPL-2.0 AND (Apache-2.0 OR BSD-2-Clause)) AND (MIT AND X11 AND HPND AND CC-BY-4.0) AND (MIT AND X11 AND MIT-CMU) AND (MIT AND X11) AND (MIT AND X11-distribute-modifications-variant) AND (MIT-feh AND MIT-Modern-Variant AND BSD-1-Clause AND BSD-3-Clause AND GPL-3.0-or-later WITH Autoconf-exception-macro) AND (MIT-open-group AND HPND-sell-variant AND X11 AND HPND-doc AND HPND-doc-sell) AND (MIT-open-group AND SMLNJ AND MIT) AND (MIT-open-group AND SMLNJ AND X11 AND ISC) AND (MIT-open-group AND X11 AND HPND AND HPND-sell-variant AND SMLNJ AND MIT AND ISC AND HPND-doc AND HPND-doc-sell) AND (MIT-open-group AND X11 AND HPND AND HPND-sell-variant AND SMLNJ AND NTP) AND (Python-2.0.1 AND MIT AND BSD-3-Clause AND MIT-CMU AND HPND-SMC AND BSD-2-Clause AND dtoa) AND (SISSL AND BSD-3-Clause) AND (SMLNJ AND HPND-sell-variant) AND (Unicode-DFS-2016 AND BSD-2-Clause AND BSD-3-Clause AND NAIST-2003 AND LicenseRef-Fedora-Public-Domain) AND (Vim AND LGPL-2.1-or-later AND MIT AND GPL-1.0-only AND (GPL-2.0-only OR Vim) AND Apache-2.0 AND BSD-2-Clause AND BSD-3-Clause AND GPL-2.0-or-later AND GPL-3.0-or-later AND OPUBL-1.0 AND Apache-2.0 WITH Swift-exception) AND (X11-distribute-modifications-variant AND HPND-sell-variant) AND (Zlib AND (LicenseRef-Callaway-Public-Domain OR MIT-0) AND LicenseRef-Callaway-MIT) AND (Zlib AND BSD-3-Clause AND MIT AND IJG) AND (Zlib AND LGPL-2.1-or-later AND (Unlicense OR MIT-0) AND (MIT OR Unlicense) AND LicenseRef-Fedora-Public-Domain) AND (Zlib AND MIT AND Apache-2.0 AND (Apache-2.0 OR MIT)) AND 0BSD AND Apache-2.0 AND Artistic-2.0 AND BSD-2-Clause AND BSD-2-Clause-Patent AND BSD-3-Clause AND BSD-4-Clause AND BSD-Attribution-HPND-disclaimer AND Boehm-GC AND CC0-1.0 AND FSFAP AND GD AND GPL-1.0-or-later AND GPL-2.0-only AND GPL-2.0-or-later AND GPL-3.0-only AND GPL-3.0-or-later AND HPND-sell-variant AND Info-ZIP AND LGPL-2.0-or-later AND LGPL-2.1-only AND LGPL-2.1-or-later AND LGPL-3.0-or-later AND LGPLv2+ AND LicenseRef-Callaway-BSD AND LicenseRef-Callaway-LGPLv2 AND LicenseRef-Callaway-LGPLv2+ AND LicenseRef-Fedora-Public-Domain AND LicenseRef-Liberation AND MIT AND MIT-0 AND MIT-Modern-Variant AND MIT-open-group AND MPL-2.0 AND NCSA AND OFL-1.1 AND OFL-1.1-RFN AND OLDAP-2.8 AND Python-2.0.1 AND TTWL AND X11 AND X11-distribute-modifications-variant AND Zlib AND blessing AND curl AND gpl-2.0-or-later AND libtiff AND tu-berlin-2.0 AND zlib

URL:            https://fex-emu.com/
Source0:        https://rootfs.fex-emu.gg/ArchLinux/2026-08-11/ArchLinux.sqsh
Source1:        armada-guestos-mount
Source2:        armada-guestos.service

BuildRequires:  coreutils
BuildRequires:  squashfs-tools
BuildRequires:  systemd-rpm-macros
Requires:       fex-emu-filesystem
Provides:       fex-emu-rootfs(arch) = %{version}-%{release}

BuildArch:      noarch
# build only on aarch64 as the dependency fex-emu uses `ExclusiveArch: arm64`
ExclusiveArch:  aarch64

%description
This package provides a RootFS based on Arch Linux to be used by the FEX
emulator.

%prep
cp %SOURCE0 .
echo "%{image_sha256}  ArchLinux.sqsh"  | sha256sum -c -

%build
# Steam's FEX compat tool needs the manifest the rootfs ships; a bump to a
# rootfs without one would otherwise fail only at x86 game launch.
unsquashfs -cat ArchLinux.sqsh graphics_provider.json | python3 -m json.tool >/dev/null

%install
install -Dpm0644 ArchLinux.sqsh %{buildroot}%{_datadir}/fex-emu/RootFS/ArchLinux.sqsh
install -Ddpm0755 %{buildroot}%{_datadir}/guestos/fex-mesa
install -Dpm0755 %SOURCE1 %{buildroot}%{_libexecdir}/armada/armada-guestos-mount
install -Dpm0644 %SOURCE2 %{buildroot}%{_unitdir}/armada-guestos.service


%files
%{_datadir}/fex-emu/RootFS/ArchLinux.sqsh
%dir %{_datadir}/guestos/fex-mesa
%{_libexecdir}/armada/armada-guestos-mount
%{_unitdir}/armada-guestos.service

%changelog
## START: Generated by rpmautospec
* Fri Apr 10 2026 Davide Cavalca <dcavalca@fedoraproject.org> - 44^20260410.n.0-1
- Update FEX rootfs to 44-20260410.n.0

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 43^20251127.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Nov 27 2025 Janne Grunau <janne-fdr@jannau.net> - 43^20251127.0-1
- Update FEX rootfs to 43-20251122.0

* Sat Nov 22 2025 Janne Grunau <janne-fdr@jannau.net> - 43^20251122.0-1
- Update FEX rootfs to 43-20251122.0

* Wed Jul 23 2025 Fedora Release Engineering <releng@fedoraproject.org> - 42^1.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Tue Apr 15 2025 Davide Cavalca <dcavalca@fedoraproject.org> - 42^1.1-1
- Update FEX rootfs to 42-1.1

* Fri Feb 14 2025 Davide Cavalca <dcavalca@fedoraproject.org> - 42^0~20250214.n.0-1
- Switch to koji-built artifacts

* Thu Jan 16 2025 Fedora Release Engineering <releng@fedoraproject.org> - 42^0~20241209.2006-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Mon Dec 09 2024 Asahi Lina <lina@asahilina.net> - 42^0~20241209.2006-1
- Update FEX rootfs to 20241209.2006

* Tue Nov 19 2024 Asahi Lina <lina@asahilina.net> - 42^0~20241117.1723-2
- Exclude "pubkey" license

* Tue Nov 19 2024 Asahi Lina <lina@asahilina.net> - 42^0~20241117.1723-1
- Update FEX rootfs to 20241117.1723

* Tue Oct 08 2024 Davide Cavalca <dcavalca@fedoraproject.org> - 42-4
- Update FEX rootfs

* Tue Oct 08 2024 Davide Cavalca <dcavalca@fedoraproject.org> - 42-3
- Update FEX rootfs

* Sat Oct 05 2024 Janne Grunau <janne-fdr@jannau.net> - 42-2
- Require noarch fex-emu-filesystem; Fixes: RHBZ#2316710, RHBZ#2316713,
  RHBZ#2316715

* Thu Oct 03 2024 Davide Cavalca <dcavalca@fedoraproject.org> - 42-1
- Initial import; Fixes: RHBZ#2315991
## END: Generated by rpmautospec
