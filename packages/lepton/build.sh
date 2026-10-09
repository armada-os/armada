#!/usr/bin/bash
# Runs inside the builder container. See ../build-local.sh for the contract.
# x86_64 like mesa-android; the RPMs hold no host binaries, so they target aarch64.
set -euxo pipefail

# mesa-android's build script downloads the NDK its BASE.env pins.
source /src/mesa-android/BASE.env
export NDK_VERSION NDK_SHA256
source ./BASE.env

NAME=lepton-guestos
TREE=/tmp/guestos-android

# Lepton renders GL through zink.
GALLIUM_DRIVERS=freedreno,zink MESA_ARGS=-Dandroid-strict=false /src/mesa-android/build.sh

rm -rf "${TREE}"
mkdir -p "${TREE}"
mv out/vendor "${TREE}/vendor"

dnf -y install --setopt=install_weak_deps=False \
    erofs-utils git rpm-build systemd-rpm-macros java-25-openjdk-devel

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
install -Dm0644 build/layer/libVkLayer_fossilize.so "${TREE}/vendor/vulkan_layers/libVkLayer_fossilize.so"

mkdir /tmp/clipstub
cd /tmp/clipstub
curl --fail --location --retry 3 --remote-name \
    "https://dl.google.com/android/repository/${ANDROID_PLATFORM_ZIP}"
curl --fail --location --retry 3 -o r8.jar \
    "https://dl.google.com/android/maven2/com/android/tools/r8/${R8_VERSION}/r8-${R8_VERSION}.jar"
sha256sum --check --strict <<EOF
${ANDROID_PLATFORM_SHA256}  ${ANDROID_PLATFORM_ZIP}
${R8_SHA256}  r8.jar
EOF
unzip -q -j "${ANDROID_PLATFORM_ZIP}" '*/android.jar'
javac --release 11 -cp android.jar -d classes /work/clipstub/ClipStub.java
java -cp r8.jar com.android.tools.r8.D8 --release --min-api "${ANDROID_API}" --lib android.jar \
    --output armada-clipstub.jar classes/*.class
install -Dm0644 armada-clipstub.jar "${TREE}/system/framework/armada-clipstub.jar"

# Lepton bind-mounts each file in the tree over the same path in its container.
cp -a /work/android/. "${TREE}/"

mkdir -p ~/rpmbuild/SOURCES ~/rpmbuild/SPECS
mkfs.erofs -zlz4hc,12 -Eztailpacking ~/rpmbuild/SOURCES/guestos-android.erofs "${TREE}"

cat >/etc/rpm/macros.armada <<EOF
%_buildhost armada-builder
%packager Armada
%vendor Armada
EOF

cat /work/patches/launcher-*.patch >~/rpmbuild/SOURCES/launcher.patch
(cd /work/prebuilt && sha256sum --check --strict ../prebuilt.sha256)
mkdir /tmp/overlay
cp -a /work/overlay/. /work/prebuilt/. /tmp/overlay/
tar -C /tmp/overlay -cf ~/rpmbuild/SOURCES/overlay.tar .
cp /work/files/* ~/rpmbuild/SOURCES/
cp "/work/${NAME}.spec" ~/rpmbuild/SPECS/
rpmbuild -bb --target aarch64 ~/rpmbuild/SPECS/"${NAME}".spec
cp ~/rpmbuild/RPMS/aarch64/*.rpm /work/out/
