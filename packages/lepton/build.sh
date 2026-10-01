#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
#
# Builds on x86_64 unlike the rest of the repo: Google ships NDK host binaries
# for linux-x86_64 only. The RPM carries no host binaries, so it packages for
# aarch64 here too.
set -euxo pipefail

source ./BASE.env

# Source and patches come from the host mesa package, the two must not drift.
source /src/mesa/BASE.env

SOURCE_URL="${SOURCE_URL:-}"
SOURCE_SHA256="${SOURCE_SHA256:-}"
SOURCE_TARBALL="${SOURCE_URL##*/}"
if [ -n "${SOURCE_URL}" ] && [ -z "${SOURCE_SHA256}" ]; then
    echo "ERROR: mesa/BASE.env sets SOURCE_URL without SOURCE_SHA256." >&2
    exit 1
fi

NDK_ZIP="android-ndk-${NDK_VERSION}-linux.zip"
NDK_URL="https://dl.google.com/android/repository/${NDK_ZIP}"

NAME=lepton-guestos
TREE=/tmp/guestos-android

rm -rf out "${TREE}"
mkdir -p out "${TREE}/vendor/lib64/hw" "${TREE}/vendor/lib64/egl"

dnf -y install --setopt=install_weak_deps=False \
    meson ninja-build python3-mako python3-yaml python3-ply bison flex \
    cmake curl unzip xz patch pkgconf glslang python3-packaging \
    gcc gcc-c++ binutils koji cpio erofs-utils git rpm-build systemd-rpm-macros \
    java-25-openjdk-headless

cd /tmp
curl --fail --location --retry 3 --remote-name "${NDK_URL}"
printf '%s  %s\n' "${NDK_SHA256}" "${NDK_ZIP}" | sha256sum --check --strict
unzip -q "${NDK_ZIP}"

# Prereleases are pinned by URL, which keeps every version reference in mesa/BASE.env.
if [ -n "${SOURCE_URL}" ]; then
    curl --fail --location --retry 3 --remote-name "${SOURCE_URL}"
    printf '%s  %s\n' "${SOURCE_SHA256}" "${SOURCE_TARBALL}" | sha256sum --check --strict
    TARBALL="${SOURCE_TARBALL}"
else
    koji download-build --arch=src "${SRPM}"
    rpm2cpio "${SRPM}.src.rpm" | cpio --extract --make-directories --quiet
    TARBALL=$(ls mesa-*.tar.xz)
fi

tar xf "$TARBALL"
cd "$(tar tf "$TARBALL" | head -1 | cut -d/ -f1)"
for patch in /src/mesa/patches/*.patch; do
    patch -p1 <"$patch"
done

TOOL=/tmp/android-ndk-${NDK_VERSION}/toolchains/llvm/prebuilt/linux-x86_64/bin
cat >/tmp/cross-android <<EOF
[binaries]
c = '${TOOL}/aarch64-linux-android${ANDROID_API}-clang'
cpp = '${TOOL}/aarch64-linux-android${ANDROID_API}-clang++'
ar = '${TOOL}/llvm-ar'
strip = '${TOOL}/llvm-strip'
c_ld = 'lld'
cpp_ld = 'lld'

[built-in options]
cpp_args = ['-fno-exceptions', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables']
cpp_link_args = ['-static-libstdc++']

[host_machine]
system = 'android'
cpu_family = 'aarch64'
cpu = 'aarch64'
endian = 'little'
EOF

# gbm-backends-path is baked in at build time, the default sends
# libgbm_mesa to /usr/local/lib/gbm and gralloc then fails to init.
meson setup build-android \
    --cross-file /tmp/cross-android \
    --buildtype release \
    -Dplatforms=android \
    -Dplatform-sdk-version=${ANDROID_API} \
    -Dandroid-stub=true \
    -Dandroid-libbacktrace=disabled \
    -Dandroid-strict=false \
    -Dgallium-drivers=freedreno,zink \
    -Dvulkan-drivers=freedreno \
    -Dfreedreno-kmds=msm \
    -Degl=enabled \
    -Dgbm=enabled \
    -Dgbm-backends-path=/vendor/lib64 \
    -Dllvm=disabled \
    -Dallow-fallback-for=libdrm

ninja -C build-android

# Lepton bind-mounts each file here over the same path in its container.
# Android's loaders match on filename, not soname.
B=build-android
install -m 0644 $B/src/freedreno/vulkan/libvulkan_freedreno.so ${TREE}/vendor/lib64/hw/vulkan.freedreno.so
install -m 0644 $B/src/gallium/targets/dri/libgallium_dri.so    ${TREE}/vendor/lib64/libgallium_dri.so
install -m 0644 $B/src/gbm/libgbm_mesa.so                       ${TREE}/vendor/lib64/libgbm_mesa.so
install -m 0644 $B/src/gbm/backends/dri/dri_gbm.so              ${TREE}/vendor/lib64/dri_gbm.so
install -m 0644 $B/src/egl/libEGL.so                            ${TREE}/vendor/lib64/egl/libEGL_mesa.so
install -m 0644 $B/src/mesa/glapi/es2api/libGLESv2.so           ${TREE}/vendor/lib64/egl/libGLESv2_mesa.so
install -m 0644 $B/src/mesa/glapi/es1api/libGLESv1_CM.so        ${TREE}/vendor/lib64/egl/libGLESv1_CM_mesa.so

# Lepton looks up layers in vendor/vulkan_layers and aborts without Fossilize.
git init -q /tmp/fossilize
cd /tmp/fossilize
git fetch -q --depth 1 https://github.com/ValveSoftware/Fossilize.git "${FOSSILIZE_COMMIT}"
git checkout -q FETCH_HEAD
git submodule update -q --init --depth 1 rapidjson
cmake -S . -B build -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=/tmp/android-ndk-${NDK_VERSION}/build/cmake/android.toolchain.cmake \
    -DANDROID_ABI=arm64-v8a \
    -DANDROID_PLATFORM=${ANDROID_API} \
    -DANDROID_STL=c++_static \
    -DCMAKE_BUILD_TYPE=Release \
    -DFOSSILIZE_CLI=OFF \
    -DFOSSILIZE_TESTS=OFF
ninja -C build
install -Dm0644 build/layer/libVkLayer_fossilize.so ${TREE}/vendor/vulkan_layers/libVkLayer_fossilize.so

# The composer shows one window, so a declared freeform feature leaves titles in a
# small floating window. Per-file bind mounts can't delete it, only shadow it.
mkdir -p ${TREE}/system/etc/permissions
printf '<?xml version="1.0" encoding="utf-8"?>\n<permissions>\n</permissions>\n' \
    >${TREE}/system/etc/permissions/android.software.freeform_window_management.xml

# lz4, no zstd :(
mkdir -p ~/rpmbuild/SOURCES ~/rpmbuild/SPECS
mkfs.erofs -zlz4hc,12 -Eztailpacking ~/rpmbuild/SOURCES/guestos-android.erofs "${TREE}"

cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF

# The device has no JVM, so smali runs as dex under the guest's ART.
cd /tmp
SMALI_URL=https://bitbucket.org/JesusFreke/smali/downloads
curl --fail --location --retry 3 -o smali.jar "${SMALI_URL}/smali-${SMALI_VERSION}.jar"
curl --fail --location --retry 3 -o baksmali.jar "${SMALI_URL}/baksmali-${SMALI_VERSION}.jar"
curl --fail --location --retry 3 -o r8.jar \
    "https://dl.google.com/android/maven2/com/android/tools/r8/${R8_VERSION}/r8-${R8_VERSION}.jar"
sha256sum --check --strict <<EOF
${SMALI_SHA256}  smali.jar
${BAKSMALI_SHA256}  baksmali.jar
${R8_SHA256}  r8.jar
EOF
for t in smali baksmali; do
    java -cp r8.jar com.android.tools.r8.D8 --release --min-api "${ANDROID_API}" \
        --output ~/rpmbuild/SOURCES/"${t}.dex.jar" "${t}.jar"
done

cp /work/files/* ~/rpmbuild/SOURCES/
cp "/work/${NAME}.spec" ~/rpmbuild/SPECS/
rpmbuild -bb --target aarch64 ~/rpmbuild/SPECS/"${NAME}".spec
cp ~/rpmbuild/RPMS/aarch64/*.rpm /work/out/
