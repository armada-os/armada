ARG FEX_PKG=ghcr.io/armada-os/armada-packages/fex@sha256:7ad92a80e6698245ade709b4f357988dd1520aca25203f7d39659585f2b9948f
ARG MESA_PKG=ghcr.io/armada-os/armada-packages/mesa@sha256:713eddabb61575b1d9fed5e1c63a7e4459447d34e21d3c0b95f307f9cf54d716
ARG MESA_ANDROID_PKG=ghcr.io/armada-os/armada-packages/mesa-android@sha256:57b03a625ebdfa12d67210c9642f24f8389c22b319e86ab32715eedfd7ee963b
ARG MESA_X86_PKG=ghcr.io/armada-os/armada-packages/mesa-x86@sha256:17ca26c35250ce0cd6a98bd13b6a21e06ca44f9e51f299fd008b1e79c4cabfc4
ARG MANGOHUD_PKG=ghcr.io/armada-os/armada-packages/mangohud@sha256:6ed92b44d267a8d2e1339968b59c2679cfd30e81494d4990dcc2c92e0be4fc10
ARG GAMESCOPE_PKG=ghcr.io/justradical/armada-packages/gamescope@sha256:11f4d185778d7f35938ec20896bf62701cc2522aae1a7406bf9e615b22538eef
ARG GAMESCOPE_SESSION_PKG=ghcr.io/justradical/armada-packages/gamescope-session@sha256:a9472f4baaf4499e5d863970ad870f8443c7ef4f074d48e3e75f713bc0fb771f
ARG GAMESCOPE_SESSION_STEAM_PKG=ghcr.io/justradical/armada-packages/gamescope-session-steam@sha256:b50952557d7e5eb42fc8951d0dc94d00a7b894877560c7063e1d5c8bfcbbc347
ARG KWIN_PKG=ghcr.io/armada-os/armada-packages/kwin@sha256:0f9bfcb4d0da4cab4a049cba7d90eb9936b3d4be610ceb00f25ec0f58d0dc812
ARG POWERDEVIL_PKG=ghcr.io/armada-os/armada-packages/powerdevil@sha256:f6d25143dca84f5f71076a3c992e06de87f7ae25fd046cfeb21999df989c4f8b
ARG KERNEL_PKG=ghcr.io/armada-os/armada-packages/kernel@sha256:039277d74007a7c4d766d2cec4e6cd1c9d0cb351c8458f47f33789af442fed5c
ARG INPUTPLUMBER_PKG=ghcr.io/armada-os/armada-packages/inputplumber@sha256:6196556fe04882547f16302763e3556b434e37e007b6f260d5f2e3f95fd43dea
ARG EXTEST_PKG=ghcr.io/armada-os/armada-packages/extest@sha256:c68bd452dd8f9a20527862e87fd446045b86811dc222a2a1744ede8d8b858dfa
ARG NETWORKMANAGER_PKG=ghcr.io/armada-os/armada-packages/networkmanager@sha256:043eae7f6f236945bc66466337391384949f56ad19807f21fe2e9b6f5c488b5f
ARG JUPITER_HW_SUPPORT_PKG=ghcr.io/armada-os/armada-packages/jupiter-hw-support@sha256:9bb3b94ced508eccb11ae4ed98b00657c202bf78ad797bf6ece345d1ec19b552
ARG ARMADA_SPLASH_PKG=ghcr.io/armada-os/armada-packages/armada-splash@sha256:6b018ab61218ad5b760fc93b27f7f6af4af4fb6301cb1ed4711cd33ded8c0ea0
ARG UMTP_RESPONDER_PKG=ghcr.io/armada-os/armada-packages/umtp-responder@sha256:b0fe59bf87bccdde7273d7ade9f824171a5b4ac5f132b4670b32a73bb1f871b3

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
FROM ${UMTP_RESPONDER_PKG} AS umtp-responder

FROM docker.io/library/node:22-slim AS decky-build
WORKDIR /build/armada-control
COPY decky/armada-control/package.json decky/armada-control/package-lock.json ./
RUN npm ci
COPY decky/armada-control/ ./
RUN npm run build
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

FROM quay.io/fedora/fedora-bootc:44
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
