ARG FEX_PKG=ghcr.io/armada-os/armada-packages/fex@sha256:7ad92a80e6698245ade709b4f357988dd1520aca25203f7d39659585f2b9948f
ARG MESA_PKG=ghcr.io/armada-os/armada-packages/mesa@sha256:ae13f3753c69d6a27f61fe9e8fc6e10ea0418b4c51bcbf2e7815241d7e0c9745
ARG MESA_ANDROID_PKG=ghcr.io/armada-os/armada-packages/mesa-android@sha256:a12f87ff69b9f58f4c0672924d622243d9c3dee505324358f2c52110b7f8f6dc
ARG MANGOHUD_PKG=ghcr.io/armada-os/armada-packages/mangohud@sha256:6ed92b44d267a8d2e1339968b59c2679cfd30e81494d4990dcc2c92e0be4fc10
ARG GAMESCOPE_PKG=ghcr.io/armada-os/armada-packages/gamescope@sha256:e8e4fadda15b597584c61cc790a887b63007727df88831319c937bc8adb4571e
ARG GAMESCOPE_SESSION_PKG=ghcr.io/armada-os/armada-packages/gamescope-session@sha256:d17006f02124427f91c70e3c841c7819ca1721ad1d4033659f3656a674f8ee35
ARG KWIN_PKG=ghcr.io/armada-os/armada-packages/kwin@sha256:0f9bfcb4d0da4cab4a049cba7d90eb9936b3d4be610ceb00f25ec0f58d0dc812
ARG POWERDEVIL_PKG=ghcr.io/armada-os/armada-packages/powerdevil@sha256:f6d25143dca84f5f71076a3c992e06de87f7ae25fd046cfeb21999df989c4f8b
ARG KERNEL_PKG=ghcr.io/armada-os/armada-packages/kernel@sha256:ad007a45077e0c8b9aade0668635106f65fbc93873cb1fadfa24b853dab755ad
ARG INPUTPLUMBER_PKG=ghcr.io/armada-os/armada-packages/inputplumber@sha256:6196556fe04882547f16302763e3556b434e37e007b6f260d5f2e3f95fd43dea
ARG EXTEST_PKG=ghcr.io/armada-os/armada-packages/extest@sha256:c68bd452dd8f9a20527862e87fd446045b86811dc222a2a1744ede8d8b858dfa
ARG NETWORKMANAGER_PKG=ghcr.io/armada-os/armada-packages/networkmanager@sha256:043eae7f6f236945bc66466337391384949f56ad19807f21fe2e9b6f5c488b5f
ARG JUPITER_HW_SUPPORT_PKG=ghcr.io/armada-os/armada-packages/jupiter-hw-support@sha256:9bb3b94ced508eccb11ae4ed98b00657c202bf78ad797bf6ece345d1ec19b552
ARG ARMADA_SPLASH_PKG=ghcr.io/armada-os/armada-packages/armada-splash@sha256:2425356403d2826fdaaa0f73ae350d09bcae08c26bb9e087268c2221cd965098

FROM ${FEX_PKG} AS fex
FROM ${MESA_PKG} AS mesa
FROM ${MANGOHUD_PKG} AS mangohud
FROM ${GAMESCOPE_PKG} AS gamescope
FROM ${GAMESCOPE_SESSION_PKG} AS gamescope-session
FROM ${KWIN_PKG} AS kwin
FROM ${POWERDEVIL_PKG} AS powerdevil
FROM ${KERNEL_PKG} AS kernel
FROM ${INPUTPLUMBER_PKG} AS inputplumber
FROM ${NETWORKMANAGER_PKG} AS networkmanager
FROM ${JUPITER_HW_SUPPORT_PKG} AS jupiter-hw-support
FROM ${MESA_ANDROID_PKG} AS mesa-android
FROM ${EXTEST_PKG} AS extest
FROM ${ARMADA_SPLASH_PKG} AS armada-splash

FROM docker.io/library/node:22-slim AS decky-build
WORKDIR /build
COPY decky/armada-control/package.json decky/armada-control/package-lock.json ./
RUN npm ci
COPY decky/armada-control/ ./
RUN npm run build

FROM scratch AS ctx
COPY abl /abl/
COPY build_files /build_files/
COPY decky /decky/
COPY system_files /system_files/

FROM quay.io/fedora/fedora-bootc:44
ARG ARMADA_VERSION=unknown
ARG ARMADA_FEDORA_MIRROR=
LABEL org.opencontainers.image.version="${ARMADA_VERSION}"

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=bind,from=fex,source=/rpms,target=/packages/fex \
    --mount=type=bind,from=mesa,source=/rpms,target=/packages/mesa \
    --mount=type=bind,from=mangohud,source=/rpms,target=/packages/mangohud \
    --mount=type=bind,from=gamescope,source=/rpms,target=/packages/gamescope \
    --mount=type=bind,from=gamescope-session,source=/rpms,target=/packages/gamescope-session \
    --mount=type=bind,from=kwin,source=/rpms,target=/packages/kwin \
    --mount=type=bind,from=powerdevil,source=/rpms,target=/packages/powerdevil \
    --mount=type=bind,from=kernel,source=/kernel,target=/packages/kernel \
    --mount=type=bind,from=inputplumber,source=/rpms,target=/packages/inputplumber \
    --mount=type=bind,from=networkmanager,source=/rpms,target=/packages/networkmanager \
    --mount=type=bind,from=jupiter-hw-support,source=/rpms,target=/packages/jupiter-hw-support \
    --mount=type=bind,from=mesa-android,source=/,target=/packages/mesa-android \
    --mount=type=bind,from=extest,source=/,target=/packages/extest \
    --mount=type=bind,from=armada-splash,source=/rpms,target=/packages/armada-splash \
    --mount=type=bind,from=decky-build,source=/build/dist,target=/packages/decky-dist \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    mkdir -p /usr/lib/armada && \
    printf '%s\n' "${ARMADA_VERSION}" >/usr/lib/armada/version && \
    export ARMADA_FEDORA_MIRROR="${ARMADA_FEDORA_MIRROR}" && \
    /ctx/build_files/build.sh

RUN bootc container lint
