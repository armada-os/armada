export image_name := env("IMAGE_NAME", "armada")
export default_tag := env("DEFAULT_TAG", "latest")
export bib_image := env("BIB_IMAGE", "quay.io/centos-bootc/bootc-image-builder:latest")

import? 'Justfile.local'

alias build-vm := build-qcow2
alias rebuild-vm := rebuild-qcow2
alias run-vm := run-vm-qcow2

[private]
default:
    @just --list

[group('Just')]
check: test
    #!/usr/bin/bash
    find . -type f -name "*.just" | while read -r file; do
    	echo "Checking syntax: $file"
    	just --unstable --fmt --check -f $file
    done
    echo "Checking syntax: Justfile"
    just --unstable --fmt --check -f Justfile

[group('Test')]
test:
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s nullglob
    for test_file in tests/*-test.sh; do
        echo "Running test: ${test_file}"
        bash "${test_file}"
    done

[group('Just')]
fix:
    #!/usr/bin/bash
    find . -type f -name "*.just" | while read -r file; do
    	echo "Checking syntax: $file"
    	just --unstable --fmt -f $file
    done
    echo "Checking syntax: Justfile"
    just --unstable --fmt -f Justfile || { exit 1; }

[group('Utility')]
clean:
    #!/usr/bin/bash
    set -eoux pipefail
    touch _build
    find *_build* -exec rm -rf {} \;
    rm -f previous.manifest.json
    rm -f changelog.md
    rm -f output.env
    rm -rf output/

[group('Utility')]
[private]
sudo-clean:
    just sudoif just clean

[group('Utility')]
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

build $target_image=image_name $tag=default_tag:
    #!/usr/bin/env bash
    set -euo pipefail

    BUILD_ARGS=()
    ARMADA_VERSION="$(TZ=America/New_York date +%Y%m%d).$(git rev-parse --short HEAD)"
    BUILD_ARGS+=("--build-arg" "ARMADA_VERSION=${ARMADA_VERSION}")

    # Allow local armada-packages images to override pinned package images.
    mapfile -t PKG_VARS < <(sed -n 's/^ARG \([A-Z0-9_]*_PKG\)=.*/\1/p' Containerfile)
    declare -A KNOWN_PKG_VARS=()
    for var in "${PKG_VARS[@]}"; do
        KNOWN_PKG_VARS["${var}"]=1
    done
    for p in ${ARMADA_LOCAL_PKGS:-}; do
        var="$(echo "$p" | tr '[:lower:]-' '[:upper:]_')_PKG"
        if [[ -z "${KNOWN_PKG_VARS[$var]:-}" ]]; then
            echo "unknown package in ARMADA_LOCAL_PKGS: ${p}" >&2
            exit 1
        fi
        export "${var}=localhost/armada-packages/${p}:latest"
    done
    LOCAL_PKG=0
    for var in "${PKG_VARS[@]}"; do
        if [[ -n "${!var:-}" ]]; then
            BUILD_ARGS+=("--build-arg" "${var}=${!var}")
            [[ "${!var}" == localhost/* ]] && LOCAL_PKG=1
            echo "==> using ${var}=${!var}"
        fi
    done

    # localhost package images need --pull=missing.
    PULL_POLICY="newer"
    [[ "${LOCAL_PKG}" == 1 ]] && PULL_POLICY="missing"

    SECRET_ARGS=()
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        SECRET_ARGS+=("--secret" "id=GITHUB_TOKEN,env=GITHUB_TOKEN")
    fi

    podman build \
        "${BUILD_ARGS[@]}" \
        "${SECRET_ARGS[@]}" \
        --platform linux/arm64 \
        --pull="${PULL_POLICY}" \
        --tag "${target_image}:${tag}" \
        .

_rootful_load_image $target_image=image_name $tag=default_tag:
    #!/usr/bin/bash
    set -eoux pipefail

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
    mkdir -p output
    mv -f $BUILDTMP/* output/
    rmdir $BUILDTMP

    # Each rebuild leaves untagged layers in both storages.
    sudo podman image prune -f 2>&1 | tail -3 || true
    podman image prune -f 2>&1 | tail -3 || true

_rebuild-bib $target_image $tag $type $config: (build target_image tag) && (_build-bib target_image tag type config)

[group('Build Virtual Machine Image')]
build-qcow2 $target_image=("localhost/" + image_name) $tag=default_tag: && (_build-bib target_image tag "qcow2" "disk_config/disk.toml")

[group('Build Virtual Machine Image')]
build-raw $target_image=("localhost/" + image_name) $tag=default_tag: && (_build-bib target_image tag "raw" "disk_config/disk.toml")

[group('Build Virtual Machine Image')]
build-iso $target_image=("localhost/" + image_name) $tag=default_tag: && (_build-bib target_image tag "iso" "disk_config/iso.toml")

# Output: ./output/armada-<version>.img.gz  (version = container label, date.sha)
[group('Armada')]
build-armada-image $target_image=("localhost/" + image_name) $tag=default_tag: (build-raw target_image tag)
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Finalizing the freshly-built raw image..."
    version=$(podman inspect -t image "${target_image}:${tag}" \
                | jq -r '.[0].Config.Labels["org.opencontainers.image.version"] // empty')
    ./post_process/preseed-flatpaks.sh output/image/disk.raw
    ./post_process/make-bootimg.sh output/image/disk.raw
    # Name from the container's version so a flashed device traces to its build.
    if [[ -n "$version" && "$version" != unknown ]]; then
        export OUT="output/armada-${version}.img.gz"
    fi
    ./post_process/finalize-armada-image.sh output/image/disk.raw

[group('Build Virtual Machine Image')]
rebuild-qcow2 $target_image=("localhost/" + image_name) $tag=default_tag: && (_rebuild-bib target_image tag "qcow2" "disk_config/disk.toml")

[group('Build Virtual Machine Image')]
rebuild-raw $target_image=("localhost/" + image_name) $tag=default_tag: && (_rebuild-bib target_image tag "raw" "disk_config/disk.toml")

[group('Build Virtual Machine Image')]
rebuild-iso $target_image=("localhost/" + image_name) $tag=default_tag: && (_rebuild-bib target_image tag "iso" "disk_config/iso.toml")

_run-vm $target_image $tag $type $config:
    #!/usr/bin/bash
    set -eoux pipefail

    image_file="output/${type}/disk.${type}"
    if [[ $type == iso ]]; then
        image_file="output/bootiso/install.iso"
    fi

    if [[ ! -f "${image_file}" ]]; then
        just "build-${type}" "$target_image" "$tag"
    fi

    port=8006
    while grep -q :${port} <<< $(ss -tunalp); do
        port=$(( port + 1 ))
    done
    echo "Using Port: ${port}"
    echo "Connect to http://localhost:${port}"

    run_args=()
    run_args+=(--rm --privileged)
    run_args+=(--pull=newer)
    run_args+=(--publish "127.0.0.1:${port}:8006")
    run_args+=(--env "CPU_CORES=4")
    run_args+=(--env "RAM_SIZE=8G")
    run_args+=(--env "DISK_SIZE=64G")
    run_args+=(--env "TPM=Y")
    run_args+=(--env "GPU=Y")
    run_args+=(--device=/dev/kvm)
    run_args+=(--volume "${PWD}/${image_file}":"/boot.${type}")
    run_args+=(docker.io/qemux/qemu)

    (sleep 30 && xdg-open http://localhost:"$port") &
    podman run "${run_args[@]}"

[group('Run Virtual Machine')]
run-vm-qcow2 $target_image=("localhost/" + image_name) $tag=default_tag: && (_run-vm target_image tag "qcow2" "disk_config/disk.toml")

[group('Run Virtual Machine')]
run-vm-raw $target_image=("localhost/" + image_name) $tag=default_tag: && (_run-vm target_image tag "raw" "disk_config/disk.toml")

[group('Run Virtual Machine')]
run-vm-iso $target_image=("localhost/" + image_name) $tag=default_tag: && (_run-vm target_image tag "iso" "disk_config/iso.toml")

[group('Run Virtual Machine')]
spawn-vm rebuild="0" type="qcow2" ram="6G":
    #!/usr/bin/env bash

    set -euo pipefail

    [ "{{ rebuild }}" -eq 1 ] && echo "Rebuilding the ISO" && just build-vm {{ rebuild }} {{ type }}

    systemd-vmspawn \
      -M "bootc-image" \
      --console=gui \
      --cpus=2 \
      --ram=$(echo {{ ram }}| /usr/bin/numfmt --from=iec) \
      --network-user-mode \
      --vsock=false --pass-ssh-key=false \
      -i ./output/**/*.{{ type }}

lint:
    #!/usr/bin/env bash
    set -eoux pipefail
    if ! command -v shellcheck &> /dev/null; then
        echo "shellcheck could not be found. Please install it."
        exit 1
    fi
    /usr/bin/find . -iname "*.sh" -type f -exec shellcheck "{}" ';'

format:
    #!/usr/bin/env bash
    set -eoux pipefail
    if ! command -v shfmt &> /dev/null; then
        echo "shfmt could not be found. Please install it."
        exit 1
    fi
    /usr/bin/find . -iname "*.sh" -type f -exec shfmt --write "{}" ';'
