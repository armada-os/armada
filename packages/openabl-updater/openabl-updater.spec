%global debug_package %{nil}

# Bump with a changelog entry; %%prep checks each image against the release's .sha256.
%global openabl_version 1.2
%global openabl_url https://github.com/OpenHandheldCollective/OpenABL
# Shipped SoCs, has to be updated if Armada adds more SoCs that need OpenABL
%global openabl_socs SM8250 SM8550 SM8650 SM8750

Name:           openabl-updater
Version:        %{openabl_version}
Release:        1%{?dist}.armada
Summary:        OpenABL bootloader payloads and the Armada ABL updater
# Payloads are OpenABL (GPL-3.0-or-later), the updater is Armada's.
License:        GPL-2.0-or-later AND GPL-3.0-or-later
URL:            https://github.com/armada-os/armada
BuildArch:      noarch

Source0:        openabl-updater.tar.gz
Source1:        %{openabl_url}/releases/download/v%{openabl_version}/abl_signed-SM8250.elf
Source2:        %{openabl_url}/releases/download/v%{openabl_version}/abl_signed-SM8550.elf
Source3:        %{openabl_url}/releases/download/v%{openabl_version}/abl_signed-SM8650.elf
Source4:        %{openabl_url}/releases/download/v%{openabl_version}/abl_signed-SM8750.elf
Source10:       https://raw.githubusercontent.com/OpenHandheldCollective/OpenABL/v%{openabl_version}/LICENSE#/OpenABL-LICENSE
Source11:       %{openabl_url}/releases/download/v%{openabl_version}/abl_signed-SM8250.elf.sha256
Source12:       %{openabl_url}/releases/download/v%{openabl_version}/abl_signed-SM8550.elf.sha256
Source13:       %{openabl_url}/releases/download/v%{openabl_version}/abl_signed-SM8650.elf.sha256
Source14:       %{openabl_url}/releases/download/v%{openabl_version}/abl_signed-SM8750.elf.sha256

Requires:       python3
Requires:       util-linux
Requires:       coreutils

%description
OpenABL %{openabl_version} for the chipsets Armada supports and the ABL updater script.

%prep
%autosetup -n work
mkdir payloads
for soc in %{openabl_socs}; do
    cp %{_sourcedir}/abl_signed-${soc}.elf %{_sourcedir}/abl_signed-${soc}.elf.sha256 payloads/
done
(cd payloads && cat *.sha256 | sha256sum --strict -c -)
cp %{SOURCE10} OpenABL-LICENSE

%build
{
    printf 'ARMADA_ABL_NAME=OpenABL\nARMADA_ABL_VERSION=%s\n' %{openabl_version}
    for soc in %{openabl_socs}; do
        printf 'ARMADA_ABL_SHA256_%s=%s\n' "${soc}" \
            "$(sha256sum "payloads/abl_signed-${soc}.elf" | cut -d' ' -f1)"
    done
} > manifest

%install
install -Dpm 0644 -t %{buildroot}%{_prefix}/lib/%{name} payloads/*.elf legacy-releases.tsv manifest
install -Dpm 0755 -t %{buildroot}%{_libexecdir}/%{name} \
    src/abl-version src/armada-abl-update src/armada-abl-finalize
install -Dpm 0644 src/armada-bootimg-sync-openabl-updater.conf \
    %{buildroot}%{_unitdir}/armada-bootimg-sync.service.d/openabl-updater.conf

%files
%license OpenABL-LICENSE
%doc README.md
%{_prefix}/lib/%{name}/
%{_libexecdir}/%{name}/
%{_unitdir}/armada-bootimg-sync.service.d/openabl-updater.conf

%changelog
* Mon Oct 19 2026 Radical <radical@radical.fun> - 1.1-1
- Package the ABL updater and ship OpenABL 1.1 in place of ROCKNIX ABL
