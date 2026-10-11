#!/usr/bin/bash
# Rebuilds prebuilt/ from Valve's Android tree. Run by hand on an x86_64 host
# with podman and about 60 GB free; CI only checks the result's hashes.
set -euxo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
source ./BASE.env

if [ ! -f /run/.containerenv ]; then
    exec podman run --rm --platform linux/amd64 -v "${PWD}:/work:Z" -w /work \
        "${ANDROID_BUILDER_IMAGE}" ./build-android.sh
fi

export DEBIAN_FRONTEND=noninteractive USER=root
apt-get -qq update
apt-get install -y --no-install-recommends ca-certificates git

git clone --depth 1 --branch "${LEPTON_TAG}" "${LEPTON_REPO}" /tmp/lepton
[ "$(git -C /tmp/lepton rev-parse HEAD)" = "${LEPTON_COMMIT}" ]
git -C /tmp/lepton submodule update --init --depth 1 \
    image/android_device_waydroid_waydroid image/android_hardware_waydroid image/android_vendor_waydroid

# Valve's builder image is this base plus this script.
/tmp/lepton/.ci_scripts/install-build-rootfs-dependencies.sh

image=/tmp/lepton/image
run() {
    bash -lc "source ~/.bashrc; set -eo pipefail; cd ${image}; $1"
}

run "./.buildscripts/update_repositories.sh --ci"
run "cd output && ../.buildscripts/copy_vendored_projects.sh >/dev/null &&
     source build/envsetup.sh && apply-waydroid-patches"

git -C "${image}/android_hardware_waydroid" apply /work/patches/android-0001-*.patch
git -C "${image}/output/hardware/interfaces" apply /work/patches/android-0002-*.patch
git -C "${image}/output/packages/apps/DocumentsUI" apply /work/patches/android-0003-*.patch
cp -r /work/rro "${image}/output/vendor/armada-lepton-overlay"

run "cd output && ../.buildscripts/copy_vendored_projects.sh >/dev/null &&
     source build/envsetup.sh &&
     lunch lineage_lepton_arm64_only-userdebug &&
     make hwcomposer.waydroid libhwc2on1adapter DocumentsUI ExternalStorageProvider ArmadaLeptonFrameworkOverlay LatinIME -j\$(nproc)"

product="${image}/output/out/target/product/lepton_arm64_only"
install -Dm0644 "${product}/vendor/lib64/hw/hwcomposer.waydroid.so" -t prebuilt/vendor/lib64/hw
install -Dm0644 "${product}/vendor/lib64/libhwc2on1adapter.so" -t prebuilt/vendor/lib64
# The file picker, which Valve's image leaves out.
install -Dm0644 "${product}/system/priv-app/DocumentsUI/DocumentsUI.apk" -t prebuilt/system/priv-app/DocumentsUI
install -Dm0644 "${product}/system/priv-app/ExternalStorageProvider/ExternalStorageProvider.apk" \
    -t prebuilt/system/priv-app/ExternalStorageProvider
install -Dm0644 "${product}/system/etc/permissions/com.android.documentsui.xml" -t prebuilt/system/etc/permissions
# The on-screen keyboard. Its app lib dir links to the system copy, which a
# file overlay cannot follow, so both get the library.
install -Dm0644 "${product}/system/product/app/LatinIME/LatinIME.apk" -t prebuilt/system/product/app/LatinIME
install -Dm0644 "${product}/system/product/lib64/libjni_latinime.so" -t prebuilt/system/product/lib64
install -Dm0644 "${product}/system/product/lib64/libjni_latinime.so" -t prebuilt/system/product/app/LatinIME/lib/arm64
# The second screen shows only what an app puts there instead of a mirror.
install -Dm0644 "${product}/system/product/overlay/ArmadaLeptonFrameworkOverlay.apk" -t prebuilt/system/product/overlay
(cd prebuilt && find . -type f -printf '%P\0' | sort -z | xargs -0 sha256sum) >prebuilt.sha256
