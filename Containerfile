ARG FEX_PKG=ghcr.io/armada-os/armada-packages/fex@sha256:277a25328499761e570bfb1f7fdce44b29dee074d76462402b0d8c361dacdffc
ARG MESA_PKG=ghcr.io/armada-os/armada-packages/mesa@sha256:559c976d78bcc771f574c18d8fed5debcc3b8856a0ff448e968940480bca1165
ARG MESA_ANDROID_PKG=ghcr.io/armada-os/armada-packages/mesa-android@sha256:1e7d5f5e692c38b7545e0c0774bbee45ab1b634309d9240f0e08b407b3fcc526
ARG MESA_X86_PKG=ghcr.io/armada-os/armada-packages/mesa-x86@sha256:f891d7fc16daf816d68c602655336e5cae1aae8b0aa3e1ef47a6215e4c4b11e5
ARG MANGOHUD_PKG=ghcr.io/armada-os/armada-packages/mangohud@sha256:c68472ba185d91c25ef0d0cb7046058cedf5a86203ab5e073c6f21ec43694c7b
ARG GAMESCOPE_PKG=ghcr.io/armada-os/armada-packages/gamescope@sha256:d774bf38913f6c6e06df85e7b2bbe202ee4ea18947bb5cbb6e2c177802acce2d
ARG GAMESCOPE_SESSION_PKG=ghcr.io/armada-os/armada-packages/gamescope-session@sha256:2f8577c16e5f7ac12b89b1e7d602e399b3d4a52ad4c246f1d28ff1633b43f403
ARG GAMESCOPE_SESSION_STEAM_PKG=ghcr.io/armada-os/armada-packages/gamescope-session-steam@sha256:776fcc4968f0c82f4c8e6a4b643733e52f068d178a974d33fd4062a90cad063c
ARG KWIN_PKG=ghcr.io/armada-os/armada-packages/kwin@sha256:04e3692d5badb820a7251e3f3a8ac3944303b10b906922d895899e8400423d01
ARG POWERDEVIL_PKG=ghcr.io/armada-os/armada-packages/powerdevil@sha256:538904e7895bbe6a3aed0ce1a1122d282fa80f64d650845bf3d606754207f5ca
ARG KERNEL_PKG=ghcr.io/noahcdls/armada-packages/kernel@sha256:50aaf575571d8989d1c985386a7598ecb093767b98e979481cfaa5ed01db7265
ARG INPUTPLUMBER_PKG=ghcr.io/armada-os/armada-packages/inputplumber@sha256:894bcb70919f6182c1b1c3ada40c7389d0ffee4b92d9b7a7088a62f540503f6b
ARG EXTEST_PKG=ghcr.io/armada-os/armada-packages/extest@sha256:13aee022b77eb9212be1debb74cd1d5a5c6ed94aa42bdac7e6b3a6e72e38101b
ARG NETWORKMANAGER_PKG=ghcr.io/armada-os/armada-packages/networkmanager@sha256:cea22dd25c2d033ec14bc9154a87153ef8331ba725bde036dd7a05ad1430747d
ARG JUPITER_HW_SUPPORT_PKG=ghcr.io/armada-os/armada-packages/jupiter-hw-support@sha256:efc0739700ede36ed08c894445973ce2b594c70a0ee487fd5cf209bc07c955ee
ARG ARMADA_SPLASH_PKG=ghcr.io/armada-os/armada-packages/armada-splash@sha256:6b018ab61218ad5b760fc93b27f7f6af4af4fb6301cb1ed4711cd33ded8c0ea0
ARG ARMADA_RGB_PKG=ghcr.io/armada-os/armada-packages/armada-rgb@sha256:a7b66324d7bf8030e260d5f2fc9074ad9ced7c47852187783f5e3e082d0ebc25
ARG UMTP_RESPONDER_PKG=ghcr.io/armada-os/armada-packages/umtp-responder@sha256:0e7f962145b72de85c2a3563d947c6357fc3a1a34797b7106cbff1c8832078ea
ARG CHUNKAH_IMAGE=quay.io/coreos/chunkah@sha256:ff8b8b466a942ec6000445d4001fc661e2fc5a952ad9ee29b4de9ab09d1d1708
ARG BASE_IMAGE=quay.io/fedora/fedora-bootc:44

FROM ${FEX_PKG} AS fex
FROM ${MESA_PKG} AS mesa
FROM ${MANGOHUD_PKG} AS mangohud
FROM ${GAMESCOPE_PKG} AS gamescope
FROM ${GAMESCOPE_SESSION_PKG} AS gamescope-session
FROM ${GAMESCOPE_SESSION_STEAM_PKG} AS gamescope-session-steam
FROM ${KWIN_PKG} AS kwin
FROM ${POWERDEVIL_PKG} AS powerdevil
FROM ${KERNEL_PKG} AS kernel
FROM ${INPUTPLUMBER_PKG} AS inputplumber
FROM ${NETWORKMANAGER_PKG} AS networkmanager
FROM ${JUPITER_HW_SUPPORT_PKG} AS jupiter-hw-support
FROM ${MESA_ANDROID_PKG} AS mesa-android
FROM ${MESA_X86_PKG} AS mesa-x86
FROM ${EXTEST_PKG} AS extest
FROM ${ARMADA_SPLASH_PKG} AS armada-splash
FROM ${ARMADA_RGB_PKG} AS armada-rgb
FROM ${UMTP_RESPONDER_PKG} AS umtp-responder

FROM docker.io/library/node:22-slim AS decky-build
WORKDIR /build/armada-control
COPY decky/armada-control/package.json decky/armada-control/package-lock.json ./
RUN npm ci
COPY decky/armada-control/ ./
RUN npm test && npm run build
WORKDIR /build/armada-store
COPY decky/armada-store/package.json decky/armada-store/package-lock.json ./
RUN npm ci
COPY decky/armada-store/ ./
RUN npm run build

FROM scratch AS ctx
COPY abl /abl/
COPY build_files /build_files/
COPY decky /decky/
COPY system_files /system_files/

FROM ${BASE_IMAGE} AS armada-rootfs
ARG ARMADA_VERSION=unknown
LABEL org.opencontainers.image.version="${ARMADA_VERSION}"

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=bind,from=fex,source=/rpms,target=/packages/fex \
    --mount=type=bind,from=mesa,source=/rpms,target=/packages/mesa \
    --mount=type=bind,from=mangohud,source=/rpms,target=/packages/mangohud \
    --mount=type=bind,from=gamescope,source=/rpms,target=/packages/gamescope \
    --mount=type=bind,from=gamescope-session,source=/rpms,target=/packages/gamescope-session \
    --mount=type=bind,from=gamescope-session-steam,source=/rpms,target=/packages/gamescope-session-steam \
    --mount=type=bind,from=kwin,source=/rpms,target=/packages/kwin \
    --mount=type=bind,from=powerdevil,source=/rpms,target=/packages/powerdevil \
    --mount=type=bind,from=kernel,source=/kernel,target=/packages/kernel \
    --mount=type=bind,from=inputplumber,source=/rpms,target=/packages/inputplumber \
    --mount=type=bind,from=networkmanager,source=/rpms,target=/packages/networkmanager \
    --mount=type=bind,from=jupiter-hw-support,source=/rpms,target=/packages/jupiter-hw-support \
    --mount=type=bind,from=mesa-android,source=/,target=/packages/mesa-android \
    --mount=type=bind,from=mesa-x86,source=/,target=/packages/mesa-x86 \
    --mount=type=bind,from=extest,source=/,target=/packages/extest \
    --mount=type=bind,from=armada-splash,source=/rpms,target=/packages/armada-splash \
    --mount=type=bind,from=armada-rgb,source=/rpms,target=/packages/armada-rgb \
    --mount=type=bind,from=umtp-responder,source=/rpms,target=/packages/umtp-responder \
    --mount=type=bind,from=decky-build,source=/build/armada-control/dist,target=/packages/decky-dist \
    --mount=type=bind,from=decky-build,source=/build/armada-store/dist,target=/packages/decky-store-dist \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    mkdir -p /usr/lib/armada && \
    printf '%s\n' "${ARMADA_VERSION}" >/usr/lib/armada/version && \
    /ctx/build_files/build.sh

RUN bootc container lint

FROM ${CHUNKAH_IMAGE} AS chunkah
ARG CHUNKAH_CONFIG_STR
RUN --mount=from=armada-rootfs,target=/chunkah,ro \
    /bin/bash -o pipefail -c ' \
        set -e; \
        start=${SECONDS}; \
        chunkah build --verbose --compressed --compression-level 6 \
            --arch arm64 --max-layers 128 --source-date-epoch 0 \
            --prune /sysroot/ \
            --label ostree.commit- --label ostree.final-diffid- \
            --config-str "${CHUNKAH_CONFIG_STR}" \
            --output oci:/run/src/chunked 2>&1 | tee /run/src/chunkah.log; \
        echo "Chunkah completed in $((SECONDS - start)) seconds" \
    '

FROM armada-rootfs AS armada
