%global debug_package %{nil}
%global source_date_epoch_from_changelog 0

# Bump with a changelog entry. The image is the Vela release asset "vela-npu-sysext-<version>.raw";
# %%prep checks it against vela_npu_sha256 before anything is unpacked.
%global vela_npu_version 12
%global vela_tag v0.8.16
%global vela_url https://github.com/zrprod9-cmyk/vela
%global vela_npu_sha256 392ba27e276d985221d1d695b782628cffa68ae4165bcb2ec0e7676cfd49a52a

Name:           vela-npu
Version:        %{vela_npu_version}
Release:        1%{?dist}.armada
Summary:        Vela NPU helper: AMD FSR 4 on the Snapdragon 8 Gen 2 Hexagon NPU
# fsr4npud, fsr4npu-check, the units and the FSR 4 graphs are Vela's; cdsprpcd and the
# FastRPC client libraries are quic/fastrpc (BSD-3-Clause), built from source by Vela.
# libQnnHtp.so, libQnnHtpV73Stub.so, libQnnSystem.so, libQnnHtpV73Skel.so, libQairtHtpV73Skel.so,
# libQnnHtpV73.so: the Qualcomm AI Engine Direct SDK runtime 2.47.0.260601, unmodified, under the
# Qualcomm AI Stack License.
# fsr4npud: GPL-3.0-or-later + a GPL-3.0 section 7 additional permission to link with / load the Qualcomm runtime
# (text in Vela's LICENSING.md and its source header); the Qualcomm files: Qualcomm AI Stack License (%license below).
License:        GPL-3.0-or-later WITH AdditionRef-Vela-Qualcomm-QNN-linking-exception AND BSD-3-Clause AND LicenseRef-Qualcomm-AI-Stack-License
URL:            %{vela_url}
ExclusiveArch:  aarch64

Source0:        vela-npu.tar.gz
Source1:        %{vela_url}/releases/download/%{vela_tag}/vela-npu-sysext-%{vela_npu_version}.raw

BuildRequires:  squashfs-tools
BuildRequires:  systemd-rpm-macros

# The units also need the cDSP shell and its C++ runtime (fastrpc_shell_unsigned_3, libc++.so.1,
# libc++abi.so.1 from the device's dsp partition), which this package does not ship (see
# README.md). Without them every unit is skipped.

%description
fsr4npud runs the AMD FSR 4 upscaling network on the Hexagon NPU (HTP v73) of
Snapdragon 8 Gen 2 (SM8550) devices for the Vela Decky plugin: one small daemon per
precompiled graph, without root, reached over an abstract unix socket. Also ships
cdsprpcd (the cDSP listener) and the FastRPC client libraries in a private directory,
the systemd units and a udev rule that gives the render group the cDSP and system
dma-heap nodes, and the Qualcomm AI Engine Direct (QNN) HTP runtime 2.47.0.260601
(unmodified, Qualcomm AI Stack License). All units are conditioned on qcom,sm8550.

%prep
%autosetup -n work
echo "%{vela_npu_sha256}  %{SOURCE1}" | sha256sum --strict -c -
unsquashfs -no-xattrs -d image %{SOURCE1}

%build

%install
img=image/usr/lib64/vela-npu
install -d %{buildroot}%{_libdir}/vela-npu %{buildroot}%{_bindir}
install -pm 0755 -t %{buildroot}%{_libdir}/vela-npu \
    ${img}/fsr4npud ${img}/fsr4npu-check ${img}/cdsprpcd \
    ${img}/libcdsprpc.so.1.0.0 ${img}/libcdsp_default_listener.so.1.0.0
install -pm 0644 -t %{buildroot}%{_libdir}/vela-npu ${img}/nf4*.bin
# Qualcomm QNN runtime, host part (RPATH $ORIGIN = this directory).
install -pm 0755 -t %{buildroot}%{_libdir}/vela-npu     ${img}/libQnnHtp.so ${img}/libQnnHtpV73Stub.so ${img}/libQnnSystem.so
# The image's only library search path is /usr/lib64/vela-npu (fsr4npud, libcdsp_default_listener)
# and $ORIGIN on the Qualcomm libraries: nothing to strip.
ln -s libcdsprpc.so.1.0.0 %{buildroot}%{_libdir}/vela-npu/libcdsprpc.so.1
ln -s libcdsprpc.so.1 %{buildroot}%{_libdir}/vela-npu/libcdsprpc.so
ln -s libcdsp_default_listener.so.1.0.0 %{buildroot}%{_libdir}/vela-npu/libcdsp_default_listener.so.1
ln -s libcdsp_default_listener.so.1 %{buildroot}%{_libdir}/vela-npu/libcdsp_default_listener.so
ln -s ../lib64/vela-npu/fsr4npu-check %{buildroot}%{_bindir}/fsr4npu-check
# Where the cDSP loads its shell and skel libraries from (ADSP_LIBRARY_PATH): the QNN HTP v73 part.
install -d %{buildroot}%{_prefix}/lib/rfsa/adsp
install -pm 0644 -t %{buildroot}%{_prefix}/lib/rfsa/adsp     image/usr/lib/rfsa/adsp/libQnnHtpV73Skel.so image/usr/lib/rfsa/adsp/libQairtHtpV73Skel.so     image/usr/lib/rfsa/adsp/libQnnHtpV73.so
install -Dpm 0644 -t %{buildroot}%{_unitdir} \
    src/vela-npu@.service src/vela-npu-listener.service src/vela-npu-setup.service
install -Dpm 0644 src/70-vela-npu.rules %{buildroot}%{_udevrulesdir}/70-vela-npu.rules
install -Dpm 0644 src/vela-npu.conf %{buildroot}%{_modulesloaddir}/vela-npu.conf
install -Dpm 0644 image/usr/share/licenses/armada-vela-npu/fastrpc-BSD-3-Clause.txt fastrpc-BSD-3-Clause.txt
# Qualcomm's licence and Notice File, unchanged (AI Stack License s2(b), s10(h))
install -Dpm 0644 image/usr/share/licenses/armada-vela-npu/Qualcomm-AI-Stack-LICENSE.pdf Qualcomm-AI-Stack-LICENSE.pdf
install -Dpm 0644 image/usr/share/licenses/armada-vela-npu/QNN_NOTICE.txt QNN_NOTICE.txt
(cd %{buildroot}%{_libdir}/vela-npu && sha256sum fsr4npud fsr4npu-check cdsprpcd lib*.so.1.0.0 libQnn*.so nf4*.bin) > MANIFEST.sha256
install -pm 0644 MANIFEST.sha256 %{buildroot}%{_libdir}/vela-npu/MANIFEST.sha256

%files
%license fastrpc-BSD-3-Clause.txt
%license Qualcomm-AI-Stack-LICENSE.pdf
%license QNN_NOTICE.txt
%doc README.md
%{_libdir}/vela-npu/
%{_bindir}/fsr4npu-check
%dir %{_prefix}/lib/rfsa
%dir %{_prefix}/lib/rfsa/adsp
%{_prefix}/lib/rfsa/adsp/libQnnHtpV73Skel.so
%{_prefix}/lib/rfsa/adsp/libQairtHtpV73Skel.so
%{_prefix}/lib/rfsa/adsp/libQnnHtpV73.so
%{_unitdir}/vela-npu@.service
%{_unitdir}/vela-npu-listener.service
%{_unitdir}/vela-npu-setup.service
%{_udevrulesdir}/70-vela-npu.rules
%{_modulesloaddir}/vela-npu.conf

%changelog
* Mon Nov 02 2026 Vela <vela@users.noreply.github.com> - 12-1
- Package the Vela NPU helper (package 12: 7 FSR 4 graphs, quic/fastrpc a56e9d4,
  Qualcomm QNN runtime 2.47.0.260601 with Qualcomm's licence and Notice File;
  system-only library search paths)
