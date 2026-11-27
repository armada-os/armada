export image_name := env("IMAGE_NAME", "armada")
export default_tag := env("DEFAULT_TAG", "dev")
export bib_image := env("BIB_IMAGE", "quay.io/centos-bootc/bootc-image-builder@sha256:2b52843ea2bfda73b0a08d97e76b734393b1d3a804681b9fabb26723bd3a2f0b")

import? 'Justfile.local'

[private]
default:
    @just --list

# Run the tests and check the Justfile's formatting
[group('Test')]
check: test
    #!/usr/bin/bash
    find . -type f -name "*.just" | while read -r file; do
    	echo "Checking syntax: $file"
    	just --unstable --fmt --check -f $file
    done
    echo "Checking syntax: Justfile"
    just --unstable --fmt --check -f Justfile

# Run tests/*-test.sh and tests/*-test.py
[group('Test')]
test:
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s nullglob
    for test_file in tests/*-test.sh; do
        echo "Running test: ${test_file}"
        bash "${test_file}"
    done
    for test_file in tests/*-test.py; do
        # A .py test with a same-named .sh wrapper already ran above.
        [[ -e "${test_file%.py}.sh" ]] && continue
        echo "Running test: ${test_file}"
        python3 -B "${test_file}"
    done

[private]
sudoif command *args:
    #!/usr/bin/bash
    function sudoif(){
        if [[ "${UID}" -eq 0 ]]; then
            "$@"
        elif [[ "$(command -v sudo)" && -n "${SSH_ASKPASS:-}" ]] && [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
            /usr/bin/sudo --askpass "$@" || exit 1
        elif [[ "$(command -v sudo)" ]]; then
            /usr/bin/sudo "$@" || exit 1
        else
            exit 1
        fi
    }
    sudoif {{ command }} {{ args }}

# Registry holding published package images (override to use a fork's)
export pkg_registry := env("ARMADA_PKG_REGISTRY", "ghcr.io/armada-os/armada/pkg")

# Build one package and tag it by content hash, the way CI does
[group('Packages')]
package name:
    #!/usr/bin/env bash
    set -euo pipefail
    source packages/toolchain.env
    source packages/mesa-x86/BASE.env
    [ -d "packages/{{ name }}" ] || { echo "unknown package: {{ name }}" >&2; exit 1; }
    hash="$(packages/package-hash.sh {{ name }})"
    # Match CI's runners: these three build on x86_64, the rest are arm64.
    case "{{ name }}" in
        mesa-android|lepton|mesa-x86) platform=linux/amd64 ;;
        *) platform=linux/arm64 ;;
    esac
    if [ "${platform#linux/}" != "$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')" ]; then
        echo "note: building {{ name }} for ${platform} under emulation; expect it to be slow" >&2
    fi
    limits=()
    out=$(tools/build-limits.sh)
    [ -z "${out}" ] || mapfile -t limits <<<"${out}"
    podman build \
        -f packages/Containerfile \
        --platform "${platform}" \
        --target "out-{{ name }}" \
        --layers \
        "${limits[@]}" \
        --build-arg "BUILDER_IMAGE=${BUILDER_IMAGE}" \
        --build-arg "GUEST_BUILDER_IMAGE=${GUEST_BUILDER_IMAGE}" \
        -t "localhost/armada/pkg/{{ name }}:${hash}" \
        packages/
    echo "==> localhost/armada/pkg/{{ name }}:${hash}"

# Build every package (slow from cold, unchanged ones are layer-cache hits)
[group('Packages')]
packages:
    #!/usr/bin/env bash
    set -euo pipefail
    for dir in packages/*/; do
        pkg="$(basename "${dir}")"
        [ -f "${dir}/build.sh" ] || continue
        echo "==> ${pkg}"
        just package "${pkg}"
    done

# Show each package's content hash and whether it is built locally
[group('Packages')]
packages-status:
    #!/usr/bin/env bash
    set -euo pipefail
    for dir in packages/*/; do
        pkg="$(basename "${dir}")"
        [ -f "${dir}/build.sh" ] || continue
        hash="$(packages/package-hash.sh "${pkg}")"
        if podman image exists "localhost/armada/pkg/${pkg}:${hash}" 2>/dev/null; then
            printf '  %-24s %s  local\n' "${pkg}" "${hash}"
        else
            printf '  %-24s %s  %s\n' "${pkg}" "${hash}" "${pkg_registry}/${pkg}:${hash}"
        fi
    done

# Build the bootc image, first building any package changed in this checkout
[group('Image')]
build $target_image=image_name $tag=default_tag: _changed-packages
    #!/usr/bin/env bash
    set -euo pipefail

    # Resolve every package to an image: one built locally if present, else
    # the published one for that content hash.
    REFS="$(mktemp)"
    trap 'rm -f "${REFS}"' EXIT
    for dir in packages/*/; do
        pkg="$(basename "${dir}")"
        [ -f "${dir}/build.sh" ] || continue
        hash="$(packages/package-hash.sh "${pkg}")"
        var="$(echo "${pkg}" | tr '[:lower:]-' '[:upper:]_')_REF"
        local_ref="localhost/armada/pkg/${pkg}:${hash}"
        if podman image exists "${local_ref}" 2>/dev/null; then
            echo "${var}=${local_ref}" >> "${REFS}"
        else
            echo "${var}=${pkg_registry}/${pkg}:${hash}" >> "${REFS}"
        fi
    done
    expected=$(grep -c '^ARG [A-Z0-9_]*_REF$' Containerfile)
    got=$(wc -l < "${REFS}")
    [ "${expected}" -eq "${got}" ] || { echo "Containerfile wants ${expected} refs, resolved ${got}" >&2; exit 1; }

    ARMADA_VERSION="$(TZ=America/New_York date +%Y%m%d).$(git rev-parse --short HEAD)"

    SECRET_ARGS=()
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        SECRET_ARGS+=("--secret" "id=GITHUB_TOKEN,env=GITHUB_TOKEN")
    fi

    limits=()
    out=$(tools/build-limits.sh)
    [ -z "${out}" ] || mapfile -t limits <<<"${out}"
    podman build \
        --build-arg "ARMADA_VERSION=${ARMADA_VERSION}" \
        --build-arg-file "${REFS}" \
        "${SECRET_ARGS[@]}" \
        --platform linux/arm64 \
        --pull=newer \
        "${limits[@]}" \
        --target armada-rootfs \
        --tag "${target_image}:${tag}" \
        .

_rootful_load_image $target_image=image_name $tag=default_tag:
    #!/usr/bin/bash
    set -eoux pipefail

    if [[ -n "${ARMADA_IMAGE_DIGEST:-}" ]]; then
        if ! [[ "${ARMADA_IMAGE_DIGEST}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
            echo "Invalid ARMADA_IMAGE_DIGEST: expected sha256 followed by 64 lowercase hex digits" >&2
            exit 1
        fi
        just sudoif podman pull "${target_image}@${ARMADA_IMAGE_DIGEST}"
        # Pin build content while keeping the installed system on its channel.
        just sudoif podman tag "${target_image}@${ARMADA_IMAGE_DIGEST}" "${target_image}:${tag}"
        exit 0
    fi

    if [[ -n "${SUDO_USER:-}" || "${UID}" -eq "0" ]]; then
        # Always re-pull a remote tag so the disk uses the freshly published
        # image, not a stale cached one; localhost builds are already loaded.
        if [[ "${target_image}" != localhost/* ]]; then
            sudo podman pull "${target_image}:${tag}"
        fi
        exit 0
    fi

    set +e
    resolved_tag=$(podman inspect -t image "${target_image}:${tag}" | jq -r '.[].RepoTags.[0]')
    return_code=$?
    set -e

    USER_IMG_ID=$(podman images --filter reference="${target_image}:${tag}" --format "'{{ '{{.ID}}' }}'")

    if [[ $return_code -eq 0 ]]; then
        ID=$(just sudoif podman images --filter reference="${target_image}:${tag}" --format "'{{ '{{.ID}}' }}'")
        if [[ "$ID" != "$USER_IMG_ID" ]]; then
            # BIB runs as root, so rootful podman needs the image.
            just sudoif podman image scp ${UID}@localhost::"${target_image}:${tag}" root@localhost::"${target_image}:${tag}"
        fi
    else
        just sudoif podman pull "${target_image}:${tag}"
    fi

_build-bib $target_image $tag $type $config: (_rootful_load_image target_image tag)
    #!/usr/bin/env bash
    set -euo pipefail

    args="--type ${type} "
    args+="--use-librepo=True "
    args+="--rootfs=btrfs "
    args+="--target-arch arm64"

    # BIB leaves /var/tmp scratch when overlay umount races --rm.
    sudo rm -rf /var/tmp/podman[0-9]* /var/tmp/buildah-cache-[0-9]* || true
    # A failed build leaves its ~12G BUILDTMP behind (removed only on success).
    sudo rm -rf "${PWD}"/_build-bib.* || true

    BUILDTMP=$(mktemp -p "${PWD}" -d -t _build-bib.XXXXXXXXXX)

    # x86_64 qemu-user hosts need runc; crun trips a memfd bug there.
    EXTRA_MOUNTS=()
    if [ -d /etc/containers/containers.conf.d ]; then
        EXTRA_MOUNTS+=("-v" "/etc/containers/containers.conf.d:/etc/containers/containers.conf.d:ro")
    fi
    if [ -f /tmp/armada-runc/runc-arm64 ]; then
        EXTRA_MOUNTS+=("-v" "/tmp/armada-runc/runc-arm64:/usr/bin/runc:ro")
    fi

    # Ubuntu 24.04 AppArmor blocks mknod in nested crun.
    tty_args=()
    if [[ -t 0 ]]; then
        tty_args+=("-it")
    fi

    sudo podman run \
      --rm \
      "${tty_args[@]}" \
      --privileged \
      --pull=newer \
      --net=host \
      --platform linux/arm64 \
      --security-opt label=type:unconfined_t \
      --security-opt apparmor=unconfined \
      --cap-add=CAP_MKNOD \
      -v $(pwd)/${config}:/config.toml:ro \
      -v $BUILDTMP:/output \
      -v /var/lib/containers/storage:/var/lib/containers/storage \
      "${EXTRA_MOUNTS[@]}" \
      "${bib_image}" \
      ${args} \
      "${target_image}:${tag}"

    # BIB writes output as root.
    if [ -x /opt/armada/bin/reown ]; then
        sudo /opt/armada/bin/reown "$BUILDTMP"
    else
        sudo chown -R "$(id -u):$(id -g)" "$BUILDTMP"
    fi
    # mv cannot overwrite a non-empty dir from the previous build.
    mkdir -p output
    rm -rf output/image
    mv -f $BUILDTMP/* output/
    rmdir $BUILDTMP

    # Each rebuild leaves untagged layers in both storages.
    sudo podman image prune -f 2>&1 | tail -3 || true
    podman image prune -f 2>&1 | tail -3 || true

# Flashable ./output/armada-<version>.img.gz from localhost/armada
[group('Disk Image')]
disk $target_image=("localhost/" + image_name) $tag=default_tag: (_build-bib target_image tag "raw" "disk_config/disk.toml")
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Finalizing the freshly-built raw image..."
    version=$(podman inspect -t image "${target_image}:${tag}" \
                | jq -r '.[0].Config.Labels["org.opencontainers.image.version"] // empty')
    ./post_process/make-bootimg.sh output/image/disk.raw
    # Name from the container's version so a flashed device traces to its build.
    if [[ -n "$version" && "$version" != unknown ]]; then
        export OUT="output/armada-${version}.img.gz"
    fi
    ./post_process/finalize-armada-image.sh output/image/disk.raw "${target_image}:${tag}"

# Build the packages with no published build for this checkout's sources
[private]
_changed-packages:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v skopeo >/dev/null || { echo "skopeo is required" >&2; exit 1; }
    todo=()
    for dir in packages/*/; do
        pkg="$(basename "${dir}")"
        [ -f "${dir}/build.sh" ] || continue
        hash="$(packages/package-hash.sh "${pkg}")"
        podman image exists "localhost/armada/pkg/${pkg}:${hash}" && continue
        # Only a definite "not published" means build, never a network error.
        if err=$(skopeo inspect --raw "docker://${pkg_registry}/${pkg}:${hash}" 2>&1 >/dev/null); then
            continue
        fi
        case "${err}" in
            # ghcr answers 401/403, not 404, for a package it never published.
            *"manifest unknown"*|*"HTTP status: 401"*|*"HTTP status: 403"*) todo+=("${pkg}") ;;
            *) echo "cannot check ${pkg_registry}/${pkg}:${hash}: ${err}" >&2; exit 1 ;;
        esac
    done
    [ "${#todo[@]}" -eq 0 ] && exit 0
    echo "Not published for these sources, building locally: ${todo[*]}"
    for pkg in "${todo[@]}"; do
        just package "${pkg}"
    done

# Copy this checkout's system_files and Decky plugins into the running container, no rebuild
[group('Container')]
sync:
    @tools/dev-container.sh sync

# Download or refresh an image for run --image: testing, user:branch, pr/<number>, or a reference
[group('Container')]
[positional-arguments]
pull target:
    @tools/dev-container.sh pull "$@"

# Boot the image and run steam, desktop, status, logs, down (default: shell); --image <target> for another
[group('Container')]
[positional-arguments]
run *args:
    @ARMADA_DEV_IMAGE="${ARMADA_DEV_IMAGE:-localhost/${image_name}:${default_tag}}" tools/dev-container.sh "$@"
