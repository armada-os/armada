ARG FEX_PKG=ghcr.io/virtudude/armada-packages/fex@sha256:5efff7dd05124e0653fd31a62bba78a68c87bd28f54ad12f6d0079acb3f07f7e
ARG MESA_PKG=ghcr.io/virtudude/armada-packages/mesa@sha256:00f45355cd5259413ec7463c9accaf69858e8472558441095883fc5ad71fd1a9
ARG MANGOHUD_PKG=ghcr.io/virtudude/armada-packages/mangohud@sha256:685ec69671d23188cfaf93a9d898da2356eca2ee80d3205a7445b200c6774c47
ARG GAMESCOPE_PKG=ghcr.io/virtudude/armada-packages/gamescope@sha256:ddced54dd1b9ef10caaa042357f35f0fabca41c284e3c196ce26fdd99a8815f9
ARG KERNEL_PKG=ghcr.io/virtudude/armada-packages/kernel@sha256:9739ef79cd4bbc96ace5377012baeae538183d7842328746a352599ae879b519
ARG INPUTPLUMBER_PKG=ghcr.io/virtudude/armada-packages/inputplumber@sha256:5dc8cab79df7ded6c9b2c043694182faa02d5396b6521ce2e92216729b3a0f26
ARG EXTEST_PKG=ghcr.io/virtudude/armada-packages/extest@sha256:bdd44824ebbff167e007fd44df794713e2340e8fe94247d9e231f3ce10ff1844
ARG NETWORKMANAGER_PKG=ghcr.io/virtudude/armada-packages/networkmanager@sha256:ed0b1c9877fbeba38067f3b0de663c9483000019e0a0a968740f231bcfe3d095
ARG JUPITER_HW_SUPPORT_PKG=ghcr.io/virtudude/armada-packages/jupiter-hw-support@sha256:3d555f9d9ac79e7fbca2e59a45df97782fb5bee7ce3f65613703122b93b8a866

FROM ${FEX_PKG} AS fex
FROM ${MESA_PKG} AS mesa
FROM ${MANGOHUD_PKG} AS mangohud
FROM ${GAMESCOPE_PKG} AS gamescope
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
    --mount=type=bind,from=mesa,source=/rpms,target=/packages/mesa \
    --mount=type=bind,from=mangohud,source=/rpms,target=/packages/mangohud \
    --mount=type=bind,from=gamescope,source=/rpms,target=/packages/gamescope \
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
