#!/bin/bash
set -euo pipefail

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

curl_args=(--retry 4 --retry-delay 2 -fsSL)
github_curl_args=("${curl_args[@]}" -H 'Accept: application/vnd.github+json')
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    github_curl_args+=(-H "Authorization: Bearer ${GITHUB_TOKEN}")
fi

emit() {
    local name=$1 value=$2
    [[ -n "${value}" && "${value}" != *$'\n'* ]] || {
        echo "ERROR: failed to resolve ${name}" >&2
        exit 1
    }
    printf '%s=%s\n' "${name}" "${value}"
}

require_match() {
    local name=$1 value=$2 pattern=$3
    [[ "${value}" =~ ${pattern} ]] || {
        echo "ERROR: ${name} had an unexpected value: ${value}" >&2
        exit 1
    }
}

steam_runtime_base=https://repo.steampowered.com/steamrt3c/images
steam_runtime_snapshot="$(
    curl "${curl_args[@]}" "${steam_runtime_base}/latest-public-beta.txt" |
        tr -d '[:space:]'
)"
steam_manifest_url=https://client-update.steamstatic.com/steam_client_steamdeck_publicbeta_linuxarm64
curl "${curl_args[@]}" -o "${tmpdir}/steam.manifest" "${steam_manifest_url}"
steam_manifest_sha256="$(sha256sum "${tmpdir}/steam.manifest" | cut -d ' ' -f 1)"

curl "${curl_args[@]}" -o "${tmpdir}/rootfs.json" \
    https://rootfs.fex-emu.gg/RootFS_links.json
arch_rootfs_url="$(jq -er '.v1["ArchLinux (SquashFS)"].URL' "${tmpdir}/rootfs.json")"
arch_rootfs_xxh3="$(jq -er '.v1["ArchLinux (SquashFS)"].Hash' "${tmpdir}/rootfs.json")"

curl "${github_curl_args[@]}" -o "${tmpdir}/proton.json" \
    'https://api.github.com/repos/CachyOS/proton-cachyos/releases?per_page=20'
proton_release="$(
    jq -ec 'first(
        .[] |
        select(.draft | not) |
        select(.tag_name | startswith("cachyos-11.0-")) |
        select(any(.assets[]; .name | endswith("-arm64.tar.xz")))
    )' "${tmpdir}/proton.json"
)"
proton_version="$(jq -er '.tag_name | sub("^cachyos-"; "")' <<<"${proton_release}")"
proton_asset="$(
    jq -ec 'first(.assets[] | select(.name | endswith("-arm64.tar.xz")))' \
        <<<"${proton_release}"
)"
proton_asset_name="$(jq -er '.name' <<<"${proton_asset}")"
proton_sha256="$(jq -er '.digest | select(startswith("sha256:")) | sub("^sha256:"; "")' <<<"${proton_asset}")"
expected_proton_asset="proton-cachyos-${proton_version}-arm64.tar.xz"
[[ "${proton_asset_name}" == "${expected_proton_asset}" ]] || {
    echo "ERROR: expected Proton asset ${expected_proton_asset}, got ${proton_asset_name}" >&2
    exit 1
}

curl "${github_curl_args[@]}" -o "${tmpdir}/decky.json" \
    'https://api.github.com/repos/SteamDeckHomebrew/decky-loader/releases?per_page=20'
decky_release="$(
    jq -ec 'first(
        .[] |
        select(.draft | not) |
        select(any(.assets[]; .name == "PluginLoader"))
    )' "${tmpdir}/decky.json"
)"
decky_version="$(jq -er '.tag_name' <<<"${decky_release}")"
decky_asset="$(jq -ec 'first(.assets[] | select(.name == "PluginLoader"))' <<<"${decky_release}")"
decky_sha256="$(jq -er '.digest | select(startswith("sha256:")) | sub("^sha256:"; "")' <<<"${decky_asset}")"
decky_service_url=https://raw.githubusercontent.com/SteamDeckHomebrew/decky-loader/main/dist/plugin_loader-prerelease.service
curl "${curl_args[@]}" -o "${tmpdir}/decky.service" "${decky_service_url}"
decky_service_sha256="$(sha256sum "${tmpdir}/decky.service" | cut -d ' ' -f 1)"

# These values are interpolated into the build shell by the Containerfile.
# Constrain them to the expected upstream formats as well as checking hashes.
require_match STEAM_ARM_RUNTIME_SNAPSHOT "${steam_runtime_snapshot}" '^[A-Za-z0-9._-]+$'
require_match STEAM_ARM_MANIFEST_SHA256 "${steam_manifest_sha256}" '^[0-9a-f]{64}$'
require_match ARCH_ROOTFS_URL "${arch_rootfs_url}" '^https://rootfs\.fex-emu\.gg/ArchLinux/[0-9-]+/ArchLinux\.sqsh$'
require_match ARCH_ROOTFS_XXH3 "${arch_rootfs_xxh3}" '^[0-9a-f]{16}$'
require_match PROTON_VERSION "${proton_version}" '^11\.0-[A-Za-z0-9._-]+$'
require_match PROTON_SHA256 "${proton_sha256}" '^[0-9a-f]{64}$'
require_match DECKY_VERSION "${decky_version}" '^v[0-9A-Za-z._-]+$'
require_match DECKY_SHA256 "${decky_sha256}" '^[0-9a-f]{64}$'
require_match DECKY_SERVICE_SHA256 "${decky_service_sha256}" '^[0-9a-f]{64}$'

emit STEAM_ARM_RUNTIME_SNAPSHOT "${steam_runtime_snapshot}"
emit STEAM_ARM_MANIFEST_SHA256 "${steam_manifest_sha256}"
emit ARCH_ROOTFS_URL "${arch_rootfs_url}"
emit ARCH_ROOTFS_XXH3 "${arch_rootfs_xxh3}"
emit PROTON_VERSION "${proton_version}"
emit PROTON_SHA256 "${proton_sha256}"
emit DECKY_VERSION "${decky_version}"
emit DECKY_SHA256 "${decky_sha256}"
emit DECKY_SERVICE_SHA256 "${decky_service_sha256}"

echo "Resolved Steam ${steam_runtime_snapshot}, FEX ${arch_rootfs_url##*/ArchLinux/}, Proton ${proton_version}, and Decky ${decky_version}" >&2
