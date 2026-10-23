%global debug_package %{nil}
%global source_date_epoch_from_changelog 0

Name:           armada-ssc
Version:        0.1.0
Release:        1%{?dist}.armada
Summary:        Per-board Snapdragon Sensor Core data for Armada
License:        LicenseRef-Proprietary
URL:            https://github.com/armada-os/armada
BuildArch:      noarch

Source0:        armada-ssc.tar.gz

%description
Sensor configuration and registry data the ADSP reads through hexagonrpcd,
one directory per supported board.

%prep
%autosetup -n work

%install
for archive in data/*.tar.gz; do
    dest=%{buildroot}%{_datadir}/armada/ssc/$(basename "${archive}" .tar.gz)
    mkdir -p "${dest}"
    tar -xzf "${archive}" -C "${dest}" --no-same-owner
done

%files
%doc README.md
%{_datadir}/armada/ssc

%changelog
