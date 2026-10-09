#!/bin/bash
# Build aarch64 kernel from kernel.org tarball + patches/ + config overrides into
# the tarball layout armada's 20-install-kernel.sh consumes. FAST=1 reuses the
# work dir. Native on aarch64; cross-compiles via aarch64-linux-gnu-gcc on x86_64.

set -euo pipefail

# ---------- Config ----------
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KERNEL_VERSION="${KERNEL_VERSION:-$(. "${REPO_ROOT}/BASE.env"; echo "$VERSION")}"
KERNEL_MAJOR="${KERNEL_VERSION%%.*}"
WORK_DIR="${WORK_DIR:-/var/tmp/armada-kernel-build}"
OUT_DIR="${OUT_DIR:-${REPO_ROOT}/out}"
SERIES_FILE="${REPO_ROOT}/patches/series"
PATCHES_DIR="${REPO_ROOT}/patches"
DTS_DIR="${REPO_ROOT}/dts"
KCONFIG_OVERRIDES="${REPO_ROOT}/config/armada-kernel.config.overrides"

# ---------- Host arch / cross-compile setup ----------
HOST_ARCH=$(uname -m)
JOBS=$(nproc)
MAKE_ARGS=(-j"${JOBS}")
if [[ "${HOST_ARCH}" == "aarch64" ]]; then
    echo "==> Native aarch64 build (${JOBS} jobs)"
else
    if ! command -v aarch64-linux-gnu-gcc >/dev/null 2>&1; then
        echo "ERROR: aarch64-linux-gnu-gcc not found. Install the cross toolchain:" >&2
        echo "  sudo pacman -S aarch64-linux-gnu-gcc aarch64-linux-gnu-binutils  # CachyOS/Arch" >&2
        echo "  sudo apt install gcc-aarch64-linux-gnu                            # Debian/Ubuntu" >&2
        exit 1
    fi
    MAKE_ARGS+=(ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-)
    echo "==> Cross-compiling from ${HOST_ARCH} to aarch64 (${JOBS} jobs)"
fi

mkdir -p "${WORK_DIR}" "${OUT_DIR}"
export KBUILD_BUILD_USER="${KBUILD_BUILD_USER:-armada}"
export KBUILD_BUILD_HOST="${KBUILD_BUILD_HOST:-builder}"

if command -v ccache >/dev/null 2>&1; then
    ccache -M 2G >/dev/null 2>&1 || true
    ccache -z >/dev/null 2>&1 || true
    if [[ "${HOST_ARCH}" == "aarch64" ]]; then
        MAKE_ARGS+=(CC="ccache gcc")
    else
        MAKE_ARGS+=(CC="ccache aarch64-linux-gnu-gcc")
    fi
fi

# ---------- 1. Fetch upstream source ----------
if [[ "${KERNEL_VERSION}" == *-rc* ]]; then
    SRC_TARBALL="linux-${KERNEL_VERSION}.tar.gz"
    SRC_URL="${KERNEL_SRC_URL:-https://git.kernel.org/torvalds/t/${SRC_TARBALL}}"
    SRC_URL_FALLBACK="https://github.com/torvalds/linux/archive/refs/tags/v${KERNEL_VERSION}.tar.gz"
else
    SRC_TARBALL="linux-${KERNEL_VERSION}.tar.xz"
    # Some build environments cannot fetch from cdn.kernel.org; gregkh/linux
    # mirrors the stable tags and provides a fallback source.
    SRC_URL="${KERNEL_SRC_URL:-https://cdn.kernel.org/pub/linux/kernel/v${KERNEL_MAJOR}.x/${SRC_TARBALL}}"
    SRC_URL_FALLBACK="https://github.com/gregkh/linux/archive/refs/tags/v${KERNEL_VERSION}.tar.gz"
fi

cd "${WORK_DIR}"
if [ ! -f "${SRC_TARBALL}" ]; then
    echo "==> Downloading ${SRC_URL}"
    curl -fsSL -o "${SRC_TARBALL}" "${SRC_URL}" \
        || { echo "==> primary source failed, trying ${SRC_URL_FALLBACK}"; curl -fsSL -o "${SRC_TARBALL}" "${SRC_URL_FALLBACK}"; }
else
    echo "==> Using cached ${SRC_TARBALL}"
fi

SRC_DIR="${WORK_DIR}/linux-${KERNEL_VERSION}"
if [ -n "${FAST:-}" ] && [ -d "${SRC_DIR}" ]; then
    echo "==> FAST=1: reusing existing ${SRC_DIR} (skipping extract + patches)"
else
    rm -rf "${SRC_DIR}"
    echo "==> Extracting ${SRC_TARBALL}"
    tar -xf "${SRC_TARBALL}"
    # github archives name the top dir after the tag, not linux-<version>
    [ -d "${SRC_DIR}" ] || mv "${WORK_DIR}/$(tar -tf "${SRC_TARBALL}" | head -1 | cut -d/ -f1)" "${SRC_DIR}"
fi
cd "${SRC_DIR}"
PREFIX_MAP_FLAGS="-ffile-prefix-map=${SRC_DIR}=linux-${KERNEL_VERSION} -fdebug-prefix-map=${SRC_DIR}=linux-${KERNEL_VERSION} -fmacro-prefix-map=${SRC_DIR}=linux-${KERNEL_VERSION} -ffile-prefix-map=${WORK_DIR}=armada-kernel-build -fdebug-prefix-map=${WORK_DIR}=armada-kernel-build -fmacro-prefix-map=${WORK_DIR}=armada-kernel-build"
export KCFLAGS="${KCFLAGS:-} ${PREFIX_MAP_FLAGS}"
export HOSTCFLAGS="${HOSTCFLAGS:-} ${PREFIX_MAP_FLAGS}"
export KAFLAGS="${KAFLAGS:-} ${PREFIX_MAP_FLAGS}"

# ---------- 2. Apply patches ----------
# Precount for the .armada-source metadata; FAST=1 skips the apply loop below.
APPLIED=$(sed 's/#.*//' "${SERIES_FILE}" | awk 'NF { count++ } END { print count+0 }')
if [ -z "${FAST:-}" ]; then
    echo "==> Applying patches from $(basename ${SERIES_FILE})"
    APPLIED=0
    FAILED=0
    while IFS= read -r line; do
        line="${line%%#*}"
        line="${line## }"
        line="${line%% *}"
        [ -z "${line}" ] && continue
        PATCH="${PATCHES_DIR}/${line}"
        if [ ! -f "${PATCH}" ]; then
            echo "  WARN: ${line} not in patches/ (skipping)"
            continue
        fi

        # GNU patch can return success after consuming only the first hunk of a
        # malformed patch and labelling the rest "trailing garbage". Preflight
        # verbosely and require every hunk header in the payload to be applied.
        patch_log=$(mktemp)
        expected_hunks=$(grep -c '^@@ ' "${PATCH}" || true)
        if ! patch -p1 --batch --forward -F0 --dry-run --verbose \
                < "${PATCH}" > "${patch_log}" 2>&1; then
            cat "${patch_log}"
            rm -f "${patch_log}"
            FAILED=$((FAILED+1))
            echo "  ✗ ${line}  (preflight failed in ${SRC_DIR})"
            continue
        fi
        applied_hunks=$(grep -c '^Hunk #[0-9].*succeeded' "${patch_log}" || true)
        if [ "${applied_hunks}" -ne "${expected_hunks}" ]; then
            cat "${patch_log}"
            rm -f "${patch_log}"
            FAILED=$((FAILED+1))
            echo "  ✗ ${line}  (${applied_hunks}/${expected_hunks} hunks parsed)"
            continue
        fi
        rm -f "${patch_log}"

        if patch -p1 --batch --forward -F0 --no-backup-if-mismatch --quiet \
                < "${PATCH}"; then
            APPLIED=$((APPLIED+1))
            echo "  ✓ ${line}"
        else
            FAILED=$((FAILED+1))
            echo "  ✗ ${line}  (rejects in ${SRC_DIR})"
        fi
    done < "${SERIES_FILE}"
    echo "==> Patches: ${APPLIED} applied, ${FAILED} failed"
    if [ "${FAILED}" -gt 0 ]; then
        echo "ERROR: some patches failed. Look for *.rej files in ${SRC_DIR} and either:"
        echo "  - refresh the patch against ${KERNEL_VERSION}"
        echo "  - drop it from patches/series (comment out)"
        echo "  - try an older KERNEL_VERSION that matches the patch base"
        exit 1
    fi
fi

# ---------- 3. Vendor DTS files (kernel only builds DTBs listed in its Makefile) ----------
echo "==> Copying DTS files into arch/arm64/boot/dts/qcom/"
DTS_TARGET="${SRC_DIR}/arch/arm64/boot/dts/qcom"
mkdir -p "${DTS_TARGET}"
cp -v "${DTS_DIR}"/*.dts "${DTS_DIR}"/*.dtsi "${DTS_TARGET}/" 2>&1 | sed 's/^/  /'

# Apply armada's DTS edits (dts/*.dts(i) are vendored verbatim; the deltas are
# dts/*.patch). Board DTS aren't in the tree at patch time, so they patch here,
# after the copy above.
echo "==> Applying DTS edit patches"
for p in "${DTS_DIR}"/*.patch; do
    [ -e "${p}" ] || continue
    if patch -p1 -d "${SRC_DIR}" -F0 --no-backup-if-mismatch -s < "${p}"; then
        echo "  ✓ $(basename "${p}")"
    else
        echo "  ✗ $(basename "${p}") failed (see *.rej in ${DTS_TARGET})"; exit 1
    fi
done

# Append DTB entries to the qcom Makefile so they get built
QCOM_MAKEFILE="${DTS_TARGET}/Makefile"
echo "==> Adding DTB entries to qcom Makefile"
# grep marker keeps this idempotent across FAST=1 re-runs
if ! grep -q "# armada-kernel DTBs" "${QCOM_MAKEFILE}" 2>/dev/null; then
    {
        echo ""
        echo "# armada-kernel DTBs"
        for dts in "${DTS_DIR}"/*.dts; do
            base=$(basename "${dts}" .dts)
            echo "dtb-\$(CONFIG_ARCH_QCOM) += ${base}.dtb"
        done
    } >> "${QCOM_MAKEFILE}"
    echo "  added $(ls ${DTS_DIR}/*.dts | wc -l) DTB entries"
fi

# ---------- 4. Generate config ----------
# defconfig + fragment via merge_config.sh. Explicit =y requests are checked
# after Kconfig resolution so a dependency cannot silently demote them to =m.
if [ -z "${FAST:-}" ]; then
    echo "==> Generating .config from defconfig"
    make "${MAKE_ARGS[@]}" defconfig >/dev/null
else
    echo "==> FAST=1: reusing existing .config (fragment re-merged below)"
fi

if [ -f "${KCONFIG_OVERRIDES}" ]; then
    echo "==> Merging config fragment $(basename "${KCONFIG_OVERRIDES}")"
    # merge_config.sh's internal `make` reads ARCH/CROSS_COMPILE from the env
    export ARCH="${ARCH:-arm64}"
    [ "${HOST_ARCH}" = "aarch64" ] || export CROSS_COMPILE="${CROSS_COMPILE:-aarch64-linux-gnu-}"
    frag=$(mktemp); merge_log=$(mktemp)
    # kconfig's conf can't parse trailing inline comments; strip them off assignments
    sed -E '/^[[:space:]]*CONFIG_[A-Z0-9_]+=/ s/[[:space:]]*#.*$//' "${KCONFIG_OVERRIDES}" > "${frag}"
    bash scripts/kconfig/merge_config.sh .config "${frag}" 2>&1 | tee "${merge_log}"
    config_error=0
    while IFS= read -r requested; do
        case "${requested}" in
            CONFIG_*=y)
                symbol="${requested%%=*}"
                if ! grep -qx "${symbol}=y" .config; then
                    actual=$(grep -E "^${symbol}=" .config || true)
                    echo "ERROR: ${requested} did not survive Kconfig dependencies; actual: ${actual:-not set}"
                    config_error=1
                fi
                ;;
        esac
    done < "${frag}"
    if [ "${config_error}" -ne 0 ] || grep -q "not in final .config" "${merge_log}"; then
        rm -f "${frag}" "${merge_log}"
        echo "ERROR: a requested CONFIG didn't survive Kconfig deps (see above); check the depends-on chain."
        exit 1
    fi
    rm -f "${frag}" "${merge_log}"
fi

KVER=$(make "${MAKE_ARGS[@]}" -s kernelrelease)
echo "==> Kernel version: ${KVER}"
echo "==> Compiler: $(sed -n 's/^CONFIG_CC_VERSION_TEXT="\(.*\)"$/\1/p' .config)"

# ---------- 5. Build ----------
echo "==> Building Image + dtbs + modules"
make "${MAKE_ARGS[@]}" Image dtbs modules
command -v ccache >/dev/null 2>&1 && ccache -s || true
size vmlinux 2>/dev/null || true

# ---------- 6. Stage outputs ----------
STAGE="${WORK_DIR}/staging-${KVER}"
rm -rf "${STAGE}"
mkdir -p "${STAGE}/lib/modules/${KVER}/dtb/qcom"

echo "==> Staging vmlinuz + modules + DTBs"
cp arch/arm64/boot/Image "${STAGE}/lib/modules/${KVER}/vmlinuz"
make "${MAKE_ARGS[@]}" INSTALL_MOD_PATH="${STAGE}" INSTALL_MOD_STRIP=1 modules_install >/dev/null
rm -f "${STAGE}/lib/modules/${KVER}/build" "${STAGE}/lib/modules/${KVER}/source"

for dts in "${DTS_DIR}"/*.dts; do
    base=$(basename "${dts}" .dts)
    dtb_src="arch/arm64/boot/dts/qcom/${base}.dtb"
    if [ -f "${dtb_src}" ]; then
        cp "${dtb_src}" "${STAGE}/lib/modules/${KVER}/dtb/qcom/"
    else
        echo "  WARN: built DTB missing: ${dtb_src}"
    fi
done

cat > "${STAGE}/lib/modules/${KVER}/.armada-source" <<EOF
Source: linux-${KERNEL_VERSION} (kernel.org stable)
Built: armada-builder on ${HOST_ARCH}
Patches applied: ${APPLIED:-?} (from patches/series)
DTBs included: $(ls ${DTS_DIR}/*.dts | wc -l) boards (SM8250 + SM8550 + SM8650 + SM8750)
Repackaged for: armada
EOF

# ---------- 7. Package ----------
OUT_NAME="armada-kernel-${KVER}.tar.zst"
OUT_PATH="${OUT_DIR}/${OUT_NAME}"
echo "==> Compressing → ${OUT_PATH}"
cd "${STAGE}"
tar --owner=0 --group=0 -cf - lib | zstd -f -10 -T0 -o "${OUT_PATH}"
cd "${REPO_ROOT}"
(
    cd "${OUT_DIR}"
    sha256sum "${OUT_NAME}" > "${OUT_NAME}.sha256"
)

echo ""
echo "==> Done."
ls -lh "${OUT_PATH}" "${OUT_PATH}.sha256"
cat "${OUT_PATH}.sha256"
