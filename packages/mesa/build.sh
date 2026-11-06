#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
# ccache at /ccache: a cache mount in the stage, a bind mount locally.
set -euxo pipefail

source ./BASE.env
source /src/toolchain.env

SRPM_NVR="$SRPM"
SRPM_VER="${SRPM_NVR#mesa-}"
SRPM_VER="${SRPM_VER%%-*}"
MESA_VER="${VERSION:-${SRPM_VER}}"
SOURCE_URL="${SOURCE_URL:-}"
SOURCE_SHA256="${SOURCE_SHA256:-}"
SOURCE_TARBALL="${SOURCE_URL##*/}"

# The pinned Rawhide SRPM supplies Fedora's packaging; SOURCE_URL can replace its
# Mesa source for prereleases. Packages target the fedora:44 runtime ABI.
DIST=".fc44.armada"
SUBPKGS="mesa-filesystem mesa-libgbm mesa-dri-drivers mesa-vulkan-drivers mesa-libGL mesa-libEGL"

export CCACHE_DIR="${CCACHE_DIR:-/ccache}"
export CCACHE_MAXSIZE=2G
mkdir -p "${CCACHE_DIR}"

rm -rf out
mkdir -p out

export HOME=/tmp
dnf -y install rpm-build rpmdevtools koji 'dnf-command(builddep)' ccache curl
export PATH=/usr/lib64/ccache:$PATH CC=gcc CXX=g++
ccache -z
rpmdev-setuptree
cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF
cd /tmp
koji download-build --arch=src "${SRPM_NVR}"
rpm -i "${SRPM_NVR}.src.rpm"
SPEC=$HOME/rpmbuild/SPECS/mesa.spec

sed -i "s/^Version:.*/Version:        ${MESA_VER}/" "$SPEC"
sed -i 's/^Release:.*%autorelease.*/Release:        1%{?dist}/' "$SPEC"
sed -i '/^%autochangelog/d' "$SPEC"

if [ -n "${SOURCE_URL}" ]; then
    [ -n "${SOURCE_SHA256}" ] || { echo 'ERROR: SOURCE_SHA256 is required with SOURCE_URL'; exit 1; }
    curl --fail --location --retry 3 "${SOURCE_URL}" \
        --output "$HOME/rpmbuild/SOURCES/${SOURCE_TARBALL}"
    printf '%s  %s\n' "${SOURCE_SHA256}" \
        "$HOME/rpmbuild/SOURCES/${SOURCE_TARBALL}" | \
        sha256sum --check --status --strict
fi

LAST=$(grep -nE '^(Patch|Source)[0-9]*:' "$SPEC" | tail -1 | cut -d: -f1)
[ -n "$LAST" ] || { echo 'ERROR: no Source/Patch line to anchor the patch on'; exit 1; }
n=9000
for patch in /work/patches/*.patch; do
    n=$((n + 1))
    cp "$patch" $HOME/rpmbuild/SOURCES/
    sed -i "${LAST}a Patch${n}:       ${patch##*/}" "$SPEC"
    LAST=$((LAST + 1))
done
sed -i "/^%build$/i %global build_cflags %{build_cflags} ${ARMADA_MARCH}" "$SPEC"
sed -i "/^%build$/i %global build_cxxflags %{build_cxxflags} ${ARMADA_MARCH}" "$SPEC"

# two-pass: %generate_buildrequires emits a nosrc; install its BRs then build for real
dnf -y builddep "$SPEC"

# The SRPM adds the spec's own patches and options. No compiler version: it changes unprompted.
TOOLCHAIN_ID="${BUILDER_IMAGE} ${ARMADA_MARCH}"
stable_source=$(/work/turnip-build-id.sh source "${SRPM_NVR}" "${SOURCE_SHA256}" /work/patches/*.patch)
stable_id=$(/work/turnip-build-id.sh aarch64 "${TOOLCHAIN_ID}" "${stable_source}")
sed -i "/^%meson \\\\$/a \\  -Dtu-build-id=${stable_id} \\\\" "$SPEC"
grep -q -- "-Dtu-build-id=${stable_id}" "$SPEC"
rpmbuild -bb --define "dist ${DIST}" "$SPEC" || true
NOSRC=$(find "$HOME/rpmbuild/SRPMS" -maxdepth 1 -type f \
    -name "mesa-${MESA_VER}-*${DIST}.buildreqs.nosrc.rpm" -print -quit)
[ -n "$NOSRC" ] && dnf -y builddep "$NOSRC"
rpmbuild -bb --define "dist ${DIST}" "$SPEC"
ccache -s

for p in ${SUBPKGS}; do
    cp $HOME/rpmbuild/RPMS/*/${p}-${MESA_VER}-*${DIST}.*.rpm /work/out/
done

# Flatpak apps see only the GL.host extension (out/flatpak-gl, mounted at
# FLATPAK_GL_PREFIX), so the image hard-links TURNIP_DIR into it as turnip/.
TURNIP_DIR=/usr/share/armada/turnip
FLATPAK_GL_PREFIX=/usr/lib/aarch64-linux-gnu/GL/host
FLATPAK_TURNIP_DIR=${FLATPAK_GL_PREFIX}/turnip
build_ids="${stable_id}"
# Turnip-only builds that also load inside Flatpak runtimes, which have neither
# libdisplay-info (direct-display EDID parsing) nor SPIRV-Tools (SPIR-V dumps).
turnip_meson=(--buildtype release --prefix /usr
    -Dgallium-drivers= -Dvulkan-drivers=freedreno -Dfreedreno-kmds=msm
    -Dplatforms=x11,wayland -Dglx=disabled -Degl=disabled -Dgbm=disabled
    -Dopengl=false -Dllvm=disabled -Ddisplay-info=disabled -Dspirv-tools=disabled)
# Flatpak builds may link only what every runtime ships (plus their own libgallium) and
# need nothing newer than the oldest branch in tmpfiles.d/armada-flatpak-drivers.conf.
# Unversioned symbols (wayland, xcb, drm) aren't checked here: armada-flatpak-drivers and
# armada-game-launch catch those on the device with ldd -r.
FLATPAK_NEEDED='^(ld-linux-aarch64\.so\.1|libgallium-[0-9a-z.-]+-armada\.so|lib(c|m|gcc_s|stdc\+\+|z|zstd|expat|drm|gbm|udev|wayland-client|X11|X11-xcb|Xext|Xxf86vm|xshmfence|xcb(-[a-z0-9]+)?)\.so\.[0-9]+)$'
FLATPAK_VERSIONS="GLIBC_2.42 GLIBCXX_3.4.34 CXXABI_1.3.15"
# Fedora's libm re-versions some functions (acosf@GLIBC_2.43); bind those to their
# newest version within the ceiling. [u]fromfp is skipped because C23 changed its ABI.
# Anything else too new fails the check below.
flatpak_pins=/tmp/flatpak-glibc-pins.h
flatpak_glibc=${FLATPAK_VERSIONS%% *}
objdump -T /usr/lib64/libm.so.6 | awk -v max="${flatpak_glibc#GLIBC_2.}" '
    NF > 1 && $(NF-1) ~ /^\(?GLIBC_2\.[0-9]+\)?$/ && $NF !~ /^u?fromfp/ {
        v = $(NF-1); gsub(/[()]/, "", v); n = substr(v, 9) + 0; s = $NF
        if (n > newest[s]) newest[s] = n
        if (n <= max && n > best[s]) best[s] = n
    }
    END {
        for (s in newest)
            if (newest[s] > max && s in best)
                printf "__asm__(\".symver %s,%s@GLIBC_2.%d\");\n", s, s, best[s]
    }' | sort >"${flatpak_pins}"
FLATPAK_CFLAGS="-O2 ${ARMADA_MARCH} -include ${flatpak_pins}"
check_flatpak_portable() {
    local lib limit newest
    for lib in "$@"; do
        if objdump -p "$lib" | awk '$1 == "NEEDED" {print $2}' | grep -Ev "${FLATPAK_NEEDED}"; then
            echo "ERROR: ${lib} links libraries Flatpak runtimes lack (listed above)" >&2
            exit 1
        fi
        for limit in ${FLATPAK_VERSIONS}; do
            newest=$({ echo "$limit"; objdump -T "$lib" | grep -oE "\b${limit%%_*}_[0-9.]+[0-9]\b" || true; } | sort -V | tail -1)
            if [ "$newest" != "$limit" ]; then
                echo "ERROR: ${lib} needs ${newest}, newer than Flatpak runtimes' ${limit}" >&2
                exit 1
            fi
        done
    done
}
build_turnip() {
    local id=$1 src=$2 source_id=$3 out=/work/out/turnip/$1 variant_id lib icd
    variant_id=$(/work/turnip-build-id.sh aarch64 "${TOOLCHAIN_ID} -O2 ${turnip_meson[*]}" "${source_id}")
    build_ids+=$'\n'"${variant_id}"
    CFLAGS="${FLATPAK_CFLAGS}" CXXFLAGS="${FLATPAK_CFLAGS}" \
        meson setup "$src/build" "$src" "${turnip_meson[@]}" -Dtu-build-id="${variant_id}"
    ninja -C "$src/build"
    lib=$src/build/src/freedreno/vulkan/libvulkan_freedreno.so
    icd=$src/build/src/freedreno/vulkan/freedreno_icd.aarch64.json
    check_flatpak_portable "$lib"
    install -D -m 0755 "$lib" "$out/aarch64/libvulkan_freedreno.so"
    write_icd "$icd" "${FLATPAK_TURNIP_DIR}/${id}/aarch64/libvulkan_freedreno.so" "$out/flatpak.aarch64.json"
    # Stable's host manifest stays the RPM's: selecting it overrides nothing.
    [ "$id" = stable ] && return
    write_icd "$icd" "${TURNIP_DIR}/${id}/aarch64/libvulkan_freedreno.so" "$out/icd.aarch64.json"
}
write_icd() {  # <meson's manifest> <library path> <output>
    sed -E "s|\"library_path\": *\"[^\"]*\"|\"library_path\": \"$2\"|" "$1" >"$3"
    grep -q "\"$2\"" "$3"
}
for variant in /work/variants/*/; do
    id=$(basename "$variant")
    src=/tmp/turnip-$id
    /work/prepare-variant.sh "$id" "$src"
    build_turnip "$id" "$src" "$(cat "$src/source-id")"
    install -m 0644 "$src/variant.json" "/work/out/turnip/$id/variant.json"
done

# Flatpak build of stable: the RPM's source and Armada patches, without its host-only deps.
stable_src=/tmp/turnip-stable
rm -rf "$stable_src"
mkdir -p "$stable_src"
tar xf "$HOME/rpmbuild/SOURCES/${SOURCE_TARBALL:-mesa-${MESA_VER}.tar.xz}" -C "$stable_src" --strip-components=1
for patch in /work/patches/*.patch; do
    patch -d "$stable_src" -p1 --fuzz=0 --forward --no-backup-if-mismatch <"$patch"
done
build_turnip stable "$stable_src" "${stable_source}"
printf '{"label": "Stable", "version": "%s"}\n' "${MESA_VER}" >/work/out/turnip/stable/variant.json

# freedreno GL/EGL/gbm for Flatpak apps (Flathub's Mesa lacks Armada's patches and gives
# the A722 llvmpipe), in the GL.host extension.
# Runs after stable's Turnip: the VERSION edit below would change that build.
gl_build=/tmp/flatpak-gl-build
gl_destdir=/tmp/flatpak-gl-root
rm -rf "$gl_build" "$gl_destdir"
# libgallium-<ver>-armada.so and the "armada" glvnd vendor keep it apart from GL.default's Mesa.
sed -i '1s/$/-armada/' "$stable_src/VERSION"
# Flatpak may reuse an ld.so cache made before a Mesa bump, which lacks the new libgallium
# name, so set an absolute rpath. $ORIGIN won't work: gbm loads its backend through a
# symlink in the merged GL/lib/gbm.
CFLAGS="${FLATPAK_CFLAGS}" CXXFLAGS="${FLATPAK_CFLAGS}" LDFLAGS="-Wl,-rpath,${FLATPAK_GL_PREFIX}/lib" \
    meson setup "$gl_build" "$stable_src" --buildtype release --prefix "${FLATPAK_GL_PREFIX}" --libdir lib \
    -Dgallium-drivers=freedreno -Dvulkan-drivers= -Dfreedreno-kmds=msm \
    -Dplatforms=x11,wayland -Dglx=dri -Degl=enabled -Dgbm=enabled -Dglvnd=enabled \
    -Dglvnd-vendor-name=armada -Dgles1=disabled -Dgles2=enabled -Dllvm=disabled \
    -Ddisplay-info=disabled -Dspirv-tools=disabled -Dvideo-codecs= -Dlmsensors=disabled \
    -Dvalgrind=disabled -Dlibunwind=disabled -Dxlib-lease=disabled -Dgallium-va=disabled \
    -Dgallium-extra-hud=false -Dteflon=false
ninja -C "$gl_build"
DESTDIR="$gl_destdir" ninja -C "$gl_build" install
gl_root=${gl_destdir}${FLATPAK_GL_PREFIX}
gl_out=/work/out/flatpak-gl
mkdir -p "$gl_out/lib/gbm" "$gl_out/glvnd/egl_vendor.d" "$gl_out/share"
cp -a "$gl_root"/lib/libEGL_armada.so.0* "$gl_root"/lib/libGLX_armada.so.0* \
    "$gl_root"/lib/libgallium-*-armada.so "$gl_out/lib/"
# The runtime's libgbm tries <kernel driver>_gbm.so before GL.default's dri_gbm.so,
# so the backend alone (not libgbm) takes msm devices.
install -m 0755 "$gl_root/lib/gbm/dri_gbm.so" "$gl_out/lib/gbm/msm_gbm.so"
# glvnd tries EGL vendors in file name order: Armada first, then GL.default's 50_mesa.
# Full path: Flatpak's ld.so cache misses GL.host changes.
sed -E "s|\"library_path\" *: *\"[^\"]*\"|\"library_path\" : \"${FLATPAK_GL_PREFIX}/lib/libEGL_armada.so.0\"|" \
    "$gl_root/share/glvnd/egl_vendor.d/50_armada.json" >"$gl_out/glvnd/egl_vendor.d/10_armada.json"
grep -q "\"${FLATPAK_GL_PREFIX}/lib/libEGL_armada.so.0\"" "$gl_out/glvnd/egl_vendor.d/10_armada.json"
# Takes the runtime's Turnip manifest's place in Flatpak's merged vulkan/icd.d.
install -D -m 0644 /work/out/turnip/stable/flatpak.aarch64.json \
    "$gl_out/vulkan/icd.d/freedreno_icd.aarch64.json"
cp -a "$gl_root/share/drirc.d" "$gl_out/share/"
check_flatpak_portable "$gl_out"/lib/*.so.0.0.0 "$gl_out"/lib/libgallium-*-armada.so "$gl_out/lib/gbm/msm_gbm.so"

# Two drivers sharing an identity would share a shader cache.
[ -z "$(sort <<<"${build_ids}" | uniq -d)" ]
