ARG FEX_PKG=ghcr.io/virtudude/armada-packages/fex@sha256:5ac08826823c1228e5d25681c0508b79b01ff301e8c32d2cd5bbe72687615e7a
ARG LSFG_VK_PKG=ghcr.io/virtudude/armada-packages/lsfg-vk@sha256:3912b6e8d5c98b973df85746ca58aa5c2188e33e3f8abc7e7618bfe284f4ad70
ARG MESA_PKG=ghcr.io/virtudude/armada-packages/mesa@sha256:1b5bb7dec2d5cbcdbd3f895d3cdb6751c6a3a508b1fcc40e30cf83ad72229bcb
ARG MANGOHUD_PKG=ghcr.io/virtudude/armada-packages/mangohud@sha256:583278eb4f9b55f6ee25bc1040ad8066d897e75b947ec8f2c73e01a360368e0c
ARG GAMESCOPE_PKG=ghcr.io/virtudude/armada-packages/gamescope@sha256:d5f2b5ab57ef94e86b58dfbbe9b5ed6e92c20db1732d9a79b466f82dd31fde92
ARG POWERDEVIL_PKG=ghcr.io/virtudude/armada-packages/powerdevil@sha256:996937f85b561eccfd006ac1c5e7dbd0a0a1b21846ca518fdb5938c215878d81
ARG KERNEL_PKG=ghcr.io/virtudude/armada-packages/kernel@sha256:6c47e935e1d3ef1a3d7059c2a81b96b8db11868dc19a3a4062e1bf850559af71
ARG INPUTPLUMBER_PKG=ghcr.io/virtudude/armada-packages/inputplumber@sha256:a09eb3ec26be622b05b4cbe32c01570478b742e33fcc610790b57d3c4d05bd52
ARG EXTEST_PKG=ghcr.io/virtudude/armada-packages/extest@sha256:a9396ff10ebf647b1a20782e308a7c05d7e0511c7479b4305969e3bdd03c3dd5
ARG NETWORKMANAGER_PKG=ghcr.io/virtudude/armada-packages/networkmanager@sha256:14606714f9721e638cebc8dad942bd4792579ad58d310a401675d30553d10ee2
ARG JUPITER_HW_SUPPORT_PKG=ghcr.io/virtudude/armada-packages/jupiter-hw-support@sha256:ff4e36a762e3488e1510b45aed1b0ba800962f3d4f9a5c143b483a6530fc27f3

FROM ${FEX_PKG} AS fex
FROM ${LSFG_VK_PKG} AS lsfg-vk
FROM ${MESA_PKG} AS mesa
FROM ${MANGOHUD_PKG} AS mangohud
FROM ${GAMESCOPE_PKG} AS gamescope
FROM ${POWERDEVIL_PKG} AS powerdevil
FROM ${KERNEL_PKG} AS kernel
FROM ${INPUTPLUMBER_PKG} AS inputplumber
FROM ${NETWORKMANAGER_PKG} AS networkmanager
FROM ${JUPITER_HW_SUPPORT_PKG} AS jupiter-hw-support
FROM ${EXTEST_PKG} AS extest

FROM docker.io/library/node:22-slim AS decky-build
WORKDIR /build
COPY decky/armada-control/package.json decky/armada-control/package-lock.json ./
RUN npm ci
COPY decky/armada-control/ ./
RUN npm run build

FROM scratch AS ctx
COPY build_files /build_files/
COPY decky /decky/
COPY system_files /system_files/

FROM quay.io/fedora/fedora-bootc:44
ARG ARMADA_VERSION=unknown
LABEL org.opencontainers.image.version="${ARMADA_VERSION}"

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=bind,from=fex,source=/rpms,target=/packages/fex \
    --mount=type=bind,from=lsfg-vk,source=/,target=/packages/lsfg-vk \
    --mount=type=bind,from=mesa,source=/rpms,target=/packages/mesa \
    --mount=type=bind,from=mangohud,source=/rpms,target=/packages/mangohud \
    --mount=type=bind,from=gamescope,source=/rpms,target=/packages/gamescope \
    --mount=type=bind,from=powerdevil,source=/rpms,target=/packages/powerdevil \
    --mount=type=bind,from=kernel,source=/kernel,target=/packages/kernel \
    --mount=type=bind,from=inputplumber,source=/rpms,target=/packages/inputplumber \
    --mount=type=bind,from=networkmanager,source=/rpms,target=/packages/networkmanager \
    --mount=type=bind,from=jupiter-hw-support,source=/rpms,target=/packages/jupiter-hw-support \
    --mount=type=bind,from=extest,source=/,target=/packages/extest \
    --mount=type=bind,from=decky-build,source=/build/dist,target=/packages/decky-dist \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    mkdir -p /usr/lib/armada && \
    printf '%s\n' "${ARMADA_VERSION}" >/usr/lib/armada/version && \
    /ctx/build_files/build.sh

RUN bootc container lint
