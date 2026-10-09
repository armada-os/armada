%global debug_package %{nil}
%global source_date_epoch_from_changelog 0
%global __jar_repack %{nil}
%global __provides_exclude_from ^/usr/lib/armada-aurora/.*$
%global __requires_exclude ^lib(java|jimage|jli|jsig|jvm|net|nio|syslookup|verify|zip)\.so.*$

Name:           armada-aurora
Version:        0.1.0
Release:        1%{?dist}.armada
Summary:        Aurora Google Play helper for Armada Store
License:        GPL-3.0-or-later AND (GPL-2.0-only WITH Classpath-exception-2.0) AND Apache-2.0 AND BSD-3-Clause
URL:            https://github.com/armada-os/armada
ExclusiveArch:  aarch64

%description
On-demand anonymous Google Play search and APK download resolution using
Aurora GPlayAPI, with a bundled Java runtime.

%install
mkdir -p %{buildroot}/usr/lib
cp -a %{_sourcedir}/armada-aurora %{buildroot}/usr/lib/
mkdir -p %{buildroot}%{_bindir}
ln -s ../lib/armada-aurora/bin/armada-aurora %{buildroot}%{_bindir}/armada-aurora

%files
%dir /usr/lib/armada-aurora
%{_bindir}/armada-aurora
/usr/lib/armada-aurora/bin
/usr/lib/armada-aurora/lib
/usr/lib/armada-aurora/runtime
%license /usr/lib/armada-aurora/LICENSE
%license /usr/lib/armada-aurora/LICENSES

%changelog
