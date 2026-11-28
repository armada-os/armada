%global debug_package %{nil}
%global source_date_epoch_from_changelog 0
%global flatpak_dri %{_datadir}/armada/flatpak-mesa/lib/dri

Name:           qcom-va-driver
Version:        0
Release:        1%{?dist}.armada
Summary:        VA-API driver for the Qualcomm iris video decoder
License:        MIT
URL:            https://github.com/radxa-pkg/qcom-va-driver
Source0:        %{url}/archive/%{commit}/%{name}-%{commit}.tar.gz

BuildRequires:  binutils
BuildRequires:  gcc-c++
BuildRequires:  meson
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libva)

%description
VA-API decode and encode over the iris V4L2 stateful video driver, for the
host and, through Armada's GL.host extension, for Flatpak apps.

%prep
%autosetup -n %{name}-%{commit}

%build
# Flatpak runtimes load this binary too: link only libdrm and the C/C++ runtime.
%meson -Dgpu_copy=disabled -Dcdsp_vpp=disabled -Dvulkan_vpp=disabled -Dv4l2_symlink=false
%meson_build

%install
%meson_install
rm -r %{buildroot}%{_docdir} %{buildroot}%{_datadir}/licenses
# Flatpak apps see only GL.host.
mkdir -p %{buildroot}%{flatpak_dri}
ln %{buildroot}%{_libdir}/dri/qcom_drv_video.so %{buildroot}%{flatpak_dri}/
ln -s qcom_drv_video.so %{buildroot}%{flatpak_dri}/msm_drv_video.so

%check
# Same ceilings as Mesa's Flatpak build (../mesa/build.sh).
lib=%{buildroot}%{_libdir}/dri/qcom_drv_video.so
if objdump -p "$lib" | awk '$1 == "NEEDED" {print $2}' |
        grep -Ev '^(ld-linux-aarch64|lib(c|m|gcc_s|stdc\+\+|drm))\.so\.[0-9]+$'; then
    echo "ERROR: links libraries Flatpak runtimes lack (listed above)" >&2
    exit 1
fi
for limit in GLIBC_2.42 GLIBCXX_3.4.34 CXXABI_1.3.15; do
    newest=$({ echo "$limit"; objdump -T "$lib" | grep -oE "\b${limit%%_*}_[0-9.]+[0-9]\b" || true; } | sort -V | tail -1)
    [ "$newest" = "$limit" ] || { echo "ERROR: needs $newest, newer than $limit" >&2; exit 1; }
done

%files
%license LICENSE
%doc README.md
%{_libdir}/dri/qcom_drv_video.so
%{_libdir}/dri/msm_drv_video.so
%dir %{flatpak_dri}
%{flatpak_dri}/qcom_drv_video.so
%{flatpak_dri}/msm_drv_video.so

%changelog
