ARG CHUNKAH_IMAGE=quay.io/coreos/chunkah@sha256:ff8b8b466a942ec6000445d4001fc661e2fc5a952ad9ee29b4de9ab09d1d1708
ARG BASE_IMAGE=quay.io/fedora/fedora-bootc:44

# Package images, resolved by content hash. The Packages workflow publishes each
# as ghcr.io/<owner>/armada/pkg/<name>:<tag>, tagged by packages/package-hash.sh
# from that package's sources, and passes the refs in as build args.

ARG STEAM_BOOTSTRAP_REF
FROM ${STEAM_BOOTSTRAP_REF} AS steam-bootstrap

ARG FEX_REF
FROM ${FEX_REF} AS fex

ARG MESA_REF
FROM ${MESA_REF} AS mesa

ARG MANGOHUD_REF
FROM ${MANGOHUD_REF} AS mangohud

ARG GAMESCOPE_REF
FROM ${GAMESCOPE_REF} AS gamescope

ARG GAMESCOPE_SESSION_REF
FROM ${GAMESCOPE_SESSION_REF} AS gamescope-session

ARG GAMESCOPE_SESSION_STEAM_REF
FROM ${GAMESCOPE_SESSION_STEAM_REF} AS gamescope-session-steam

ARG KWIN_REF
FROM ${KWIN_REF} AS kwin

ARG PLASMA_MOBILE_REF
FROM ${PLASMA_MOBILE_REF} AS plasma-mobile

ARG POWERDEVIL_REF
FROM ${POWERDEVIL_REF} AS powerdevil

ARG PROTONTRICKS_REF
FROM ${PROTONTRICKS_REF} AS protontricks

ARG KERNEL_REF
FROM ${KERNEL_REF} AS kernel

ARG INPUTPLUMBER_REF
FROM ${INPUTPLUMBER_REF} AS inputplumber

ARG STEAMOS_MANAGER_REF
FROM ${STEAMOS_MANAGER_REF} AS steamos-manager

ARG NETWORKMANAGER_REF
FROM ${NETWORKMANAGER_REF} AS networkmanager

ARG WPA_SUPPLICANT_REF
FROM ${WPA_SUPPLICANT_REF} AS wpa_supplicant

ARG JUPITER_HW_SUPPORT_REF
FROM ${JUPITER_HW_SUPPORT_REF} AS jupiter-hw-support

ARG MESA_ANDROID_REF
FROM ${MESA_ANDROID_REF} AS mesa-android

ARG MESA_X86_REF
FROM ${MESA_X86_REF} AS mesa-x86

ARG EXTEST_REF
FROM ${EXTEST_REF} AS extest

ARG ARMADA_SPLASH_REF
FROM ${ARMADA_SPLASH_REF} AS armada-splash

ARG ARMADA_RGB_REF
FROM ${ARMADA_RGB_REF} AS armada-rgb

ARG UMTP_RESPONDER_REF
FROM ${UMTP_RESPONDER_REF} AS umtp-responder

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
    --mount=type=bind,from=steam-bootstrap,source=/steam-bootstrap,target=/packages/steam-bootstrap \
    --mount=type=bind,from=fex,source=/rpms,target=/packages/fex \
    --mount=type=bind,from=mesa,source=/rpms,target=/packages/mesa \
    --mount=type=bind,from=mangohud,source=/rpms,target=/packages/mangohud \
    --mount=type=bind,from=gamescope,source=/rpms,target=/packages/gamescope \
    --mount=type=bind,from=gamescope-session,source=/rpms,target=/packages/gamescope-session \
    --mount=type=bind,from=gamescope-session-steam,source=/rpms,target=/packages/gamescope-session-steam \
    --mount=type=bind,from=kwin,source=/rpms,target=/packages/kwin \
    --mount=type=bind,from=plasma-mobile,source=/rpms,target=/packages/plasma-mobile \
    --mount=type=bind,from=powerdevil,source=/rpms,target=/packages/powerdevil \
    --mount=type=bind,from=protontricks,source=/rpms,target=/packages/protontricks \
    --mount=type=bind,from=kernel,source=/kernel,target=/packages/kernel \
    --mount=type=bind,from=inputplumber,source=/rpms,target=/packages/inputplumber \
    --mount=type=bind,from=steamos-manager,source=/rpms,target=/packages/steamos-manager \
    --mount=type=bind,from=networkmanager,source=/rpms,target=/packages/networkmanager \
    --mount=type=bind,from=wpa_supplicant,source=/rpms,target=/packages/wpa_supplicant \
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
