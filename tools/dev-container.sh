#!/bin/bash
# Boot an Armada image as a rootless podman container, with sessions in a window.
#
# Usage: tools/dev-container.sh [--image TARGET] [--fresh-home] [command]
#   up                 boot TARGET, replacing a container from another image
#   pull TARGET        download TARGET, or refresh it, without booting it
#   shell              interactive shell as armada (default)
#   steam              up, then the image's gamescope-session-plus steam session
#   desktop            up, then the image's Plasma session, as a nested KWin
#   gamescope [args]   up, then nested gamescope; "-- cmd" runs something in it
#   run <cmd...>       run a command as armada
#   sync               copy this checkout's system_files and Decky plugins
#                      into the running container, whatever its image
#   root [cmd...]      run a command as root (no args: root shell)
#                      (shell, run and root use the running container if any)
#   status             systemd state and failed units
#   logs [args...]     journalctl -f (extra args passed through)
#   down               stop and remove the container
#   clean              down, then delete the persistent home volume
#
# TARGET is an image reference or, as with armada-rebase, a shorthand:
#   testing, beta, <tag>     ghcr.io/armada-os/armada:<tag>
#   user:branch              ghcr.io/user/armada:branch
#   pr/958, PR URL           the PR's CI build (needs gh signed in)
# A target already downloaded is reused until pulled again.
#
# Env: ARMADA_DEV_IMAGE (default localhost/armada:dev, the image just build makes),
#      ARMADA_DEV_SIZE (Steam window in pixels, default 1920x1080),
#      ARMADA_DEV_DESKTOP_SIZE (desktop window in scaled units, default 1280x720).
set -euo pipefail

image="${ARMADA_DEV_IMAGE:-localhost/armada:dev}"
size="${ARMADA_DEV_SIZE:-1920x1080}"
desktop_size="${ARMADA_DEV_DESKTOP_SIZE:-1280x720}"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/armada-dev"
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/armada-dev"
pr_repo=armada-os/armada
name=armada-dev
home_vol=armada-dev-home
fresh_home=0

usage() { sed -n '/^# Usage:/,/^#      ARMADA_DEV_DESKTOP_SIZE/s/^# \{0,1\}//p' "$0" >&2; exit 2; }
die() { echo "dev-container: $*" >&2; exit 1; }

while [ "$#" -gt 0 ]; do
    case "$1" in
        --image) [ "$#" -ge 2 ] || usage; image="$2"; shift 2 ;;
        --image=*) image="${1#*=}"; shift ;;
        --fresh-home) fresh_home=1; shift ;;
        -h|--help) usage ;;
        *) break ;;
    esac
done
cmd="${1:-shell}"
[ "$#" -gt 0 ] && shift
[[ "$size" =~ ^[0-9]+x[0-9]+$ ]] || die "ARMADA_DEV_SIZE must look like 1920x1080"
[[ "$desktop_size" =~ ^[0-9]+x[0-9]+$ ]] || die "ARMADA_DEV_DESKTOP_SIZE must look like 1280x720"
command -v podman >/dev/null || die "podman is not installed"

running() { [ "$(podman container inspect -f '{{.State.Running}}' "$name" 2>/dev/null)" = true ]; }
down() { podman rm -f -t 10 "$name" >/dev/null 2>&1 || true; }

# Sets image from TARGET; fetch=1 refreshes it, otherwise a local copy is reused.
resolve() {
    local t=$1 fetch=$2 pr="" owner
    case "$t" in
        pr/*) pr=${t#pr/} ;;
        https://github.com/*/*/pull/*)
            pr_repo=$(cut -d/ -f4,5 <<<"$t")
            pr=$(cut -d/ -f7 <<<"$t") ;;
        */*) image=$t ;;
        *:*) owner=${t%%:*}; image="ghcr.io/${owner,,}/armada:${t#*:}" ;;
        *) image="ghcr.io/armada-os/armada:$t" ;;
    esac
    if [ -n "$pr" ]; then
        [[ "$pr" =~ ^[0-9]+$ ]] || die "not a pull request: $t"
        fetch_pr "$pr" "$fetch"
    elif [[ "$image" == localhost/* ]]; then
        podman image exists "$image" || die "$image does not exist; build it first (just build)"
    elif [ "$fetch" = 1 ] || ! podman image exists "$image"; then
        podman pull "$image"
    fi
}

# PR images are 7-day pr.yml artifacts, not on ghcr; the loaded run is recorded.
fetch_pr() {
    local pr=$1 fetch=$2 sha run record out loaded old
    image="localhost/armada:pr-$pr"
    if [ "$fetch" = 0 ] && podman image exists "$image"; then
        return 0
    fi
    command -v gh >/dev/null || die "PR builds are downloaded with the GitHub CLI (gh)"
    sha=$(gh pr view "$pr" -R "$pr_repo" --json headRefOid --jq .headRefOid) ||
        die "could not look up PR $pr in $pr_repo; is gh signed in (gh auth login)?"
    run=$(gh run list -R "$pr_repo" -w pr.yml -c "$sha" -L 1 --json databaseId --jq '.[0].databaseId // empty')
    [ -n "$run" ] || die "PR $pr has no CI run for its head commit ${sha:0:12}"
    record="$cache_dir/pr-$pr.run"
    if podman image exists "$image" && [ "$(cat "$record" 2>/dev/null)" = "$run" ]; then
        echo "==> Already have PR $pr's build of ${sha:0:12}"
        return 0
    fi
    pr_dir="$cache_dir/pr-$pr"
    rm -rf "$pr_dir"
    trap 'rm -rf "$pr_dir"' EXIT
    echo "==> Downloading PR $pr's build of ${sha:0:12} (several GB)"
    gh run download "$run" -R "$pr_repo" -n "armada-container-pr$pr" -D "$pr_dir" ||
        die "run $run has no container build yet; it may still be running"
    echo "==> Loading it"
    out=$(podman load -i "$pr_dir"/*.tar 2>&1) || { echo "$out" >&2; die "podman load failed"; }
    loaded=$(sed -n 's/^Loaded image[^:]*: //p' <<<"$out" | tail -1)
    [ -n "$loaded" ] || die "podman load found no image in the artifact"
    old=$(podman image inspect -f '{{.Id}}' "$image" 2>/dev/null || true)
    podman tag "$loaded" "$image"
    echo "$run" > "$record"
    rm -rf "$pr_dir"
    if [ -n "$old" ] && [ "$old" != "$(podman image inspect -f '{{.Id}}' "$image")" ]; then
        podman rmi "$old" >/dev/null 2>&1 || true
    fi
}

case "$cmd" in
    down) down; exit 0 ;;
    pull)
        [ "$#" -eq 1 ] || usage
        mkdir -p "$cache_dir"
        resolve "$1" 1
        echo "==> $image is ready; boot it with: just run --image $1"
        exit 0 ;;
    clean)
        down
        podman volume rm -f "$home_vol" >/dev/null
        echo "Removed the container and volume $home_vol"
        exit 0 ;;
esac

preflight() {
    [ "$(uname -m)" = aarch64 ] || die "needs an aarch64 host (the image is arm64)"
    [ "$(id -u)" != 0 ] || die "run as your user; the container is rootless"
    local k
    k=$(uname -r)
    # A user namespace can mount its own binfmt_misc from 6.7, which FEX needs.
    [ "$(printf '%s\n6.7\n' "${k%%[-+]*}" | sort -V | head -1)" = 6.7 ] ||
        die "Linux 6.7 or newer required for a private binfmt_misc (have $k)"
    [ -c /dev/fuse ] || die "/dev/fuse is missing (FEX's RootFS is mounted with FUSE)"
    [ -d /dev/dri ] || die "/dev/dri is missing; no GPU to pass through"
    [ -n "$(podman info -f '{{.Host.Pasta.Executable}}' 2>/dev/null)" ] ||
        die "pasta is not installed (podman's rootless network, passt package)"
    # keep-groups, which passes the GPU's render group through, is crun-only.
    [ "$(podman info -f '{{.Host.OCIRuntime.Name}}' 2>/dev/null)" = crun ] ||
        die "podman's OCI runtime must be crun"
    [ -n "${XDG_RUNTIME_DIR:-}" ] || die "XDG_RUNTIME_DIR is unset; run from your desktop session"
}

write_config() {
    local d="$state_dir/config"
    mkdir -p "$d/resolved.conf.d"
    # No unlimited memlock: rootless can't exceed the host's limit, so logins fail.
    cat > "$d/60-armada-gaming.conf" <<'EOF'
armada soft nofile 524288
armada hard nofile 524288
EOF
    # NetworkManager learns no DNS over pasta; 169.254.1.1 is pasta's resolver.
    cat > "$d/resolved.conf.d/armada-dev.conf" <<'EOF'
[Resolve]
DNS=169.254.1.1
Domains=~.
EOF
}

up() {
    preflight
    mkdir -p "$cache_dir"
    resolve "$image" 0
    local id
    id=$(podman image inspect -f '{{.Id}}' "$image" | cut -c1-12)

    if running; then
        if [ "$fresh_home" = 0 ] &&
            [ "$(podman container inspect -f '{{index .Config.Labels "armada-dev.image-id"}}' "$name")" = "$id" ]; then
            return 0
        fi
        echo "==> Replacing running $name"
    fi
    down
    [ "$fresh_home" = 1 ] && podman volume rm -f "$home_vol" >/dev/null

    write_config
    local d="$state_dir/config"
    local args=(
        # No --rm: a container whose init dies stays around for podman logs.
        -d --name "$name" --hostname "$name"
        # The DNS setup below assumes pasta's forwarder.
        --network pasta
        --label "armada-dev.image-id=$id"
        --systemd=always
        # Map armada (uid 1000) to the host user for Wayland, PipeWire and GPU access.
        --userns=keep-id:uid=1000,gid=1000 --user 0
        --security-opt label=disable
        # Mounts inside the container's namespaces: binfmt_misc, FUSE, overlay.
        --cap-add SYS_ADMIN --device /dev/fuse
        # rtkit keeps these three when it drops privileges.
        --cap-add SYS_NICE --cap-add DAC_READ_SEARCH --cap-add SYS_PTRACE
        --device /dev/dri --group-add keep-groups
        --shm-size 4g
        # Podman's default 2048 starves Steam: systemd caps the user slice at 33%.
        --pids-limit -1
        -v "$d/60-armada-gaming.conf:/etc/security/limits.d/60-armada-gaming.conf:ro"
        -v "$d/resolved.conf.d:/etc/systemd/resolved.conf.d:ro"
        # Named volume: first use copies the image's /var/home/armada.
        -v "$home_vol:/var/home/armada"
        -v /etc/localtime:/etc/localtime:ro
    )
    # Not /run/user/1000: systemd mounts a tmpfs over it when the session starts.
    if [ -n "${WAYLAND_DISPLAY:-}" ]; then
        local wl="$WAYLAND_DISPLAY"
        [ "${wl#/}" = "$wl" ] && wl="$XDG_RUNTIME_DIR/$wl"
        [ -S "$wl" ] && args+=(-v "$wl:/run/host/wayland-0")
    fi
    [ -S "$XDG_RUNTIME_DIR/pipewire-0" ] && args+=(-v "$XDG_RUNTIME_DIR/pipewire-0:/run/host/pipewire-0")
    [ -S "$XDG_RUNTIME_DIR/pulse/native" ] && args+=(-v "$XDG_RUNTIME_DIR/pulse/native:/run/host/pulse-native")

    echo "==> Booting $name from $image ($id)"
    # Own scope, so conmon and pasta outlive the caller's (terminal, IDE) cgroup.
    systemd-run --user --scope --quiet --collect --unit="armada-dev-podman-$$" \
        podman run "${args[@]}" "$image" /sbin/init >/dev/null
    local state=""
    for _ in $(seq 120); do
        running || { podman logs --tail 30 "$name" >&2; die "the container stopped during boot"; }
        state=$(podman exec "$name" systemctl is-system-running 2>/dev/null || true)
        case "$state" in running|degraded|maintenance) break ;; esac
        sleep 0.5
    done
    case "$state" in running|degraded|maintenance) ;; *) die "boot timed out (state: ${state:-unknown}); see just run logs" ;; esac
    # No login session in the container, so linger keeps the user manager up.
    podman exec "$name" loginctl enable-linger armada
    podman exec "$name" systemctl start user@1000.service
    echo "    system: ${state:-unknown}"
    if [ "$state" != running ]; then
        podman exec "$name" systemctl --failed --no-legend --plain | awk '{print "    failed: " $1}'
    fi
}

stop_units=()
user_env=(
    -u armada -w /var/home/armada
    -e XDG_RUNTIME_DIR=/run/user/1000
    -e DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
    -e WAYLAND_DISPLAY=/run/host/wayland-0
    -e PIPEWIRE_REMOTE=/run/host/pipewire-0
    -e PULSE_SERVER=unix:/run/host/pulse-native
    -e "LANG=${LANG:-C.UTF-8}"
)

need_wayland() {
    podman exec "$name" test -S /run/host/wayland-0 ||
        die "the container has no Wayland socket; run 'down', then retry from your desktop session"
}

# podman exec leaves its process running when the client dies, hence the scope.
user_exec() {
    local tty=() scope="armada-dev-exec-$$"
    [ -t 0 ] && [ -t 1 ] && tty=(-it)
    # Sessions start units outside the scope too.
    # shellcheck disable=SC2064  # expand now; locals are gone at EXIT
    trap "podman exec ${user_env[*]@Q} $name systemctl --user stop $scope.scope ${stop_units[*]} 2>/dev/null || true" EXIT
    trap 'exit 130' INT TERM HUP
    podman exec "${tty[@]}" "${user_env[@]}" "$name" \
        systemd-run --user --scope --quiet --unit="$scope" "$@"
}

case "$cmd" in
    # These act on the container that exists; they never boot or replace one.
    status)
        podman container exists "$name" || die "no $name container; start one with just run"
        if running; then
            podman exec "$name" systemctl is-system-running || true
            podman exec "$name" systemctl --failed --no-legend --plain
        else
            echo "stopped; last output:"
            podman logs --tail 30 "$name"
            podman container inspect -f '{{if .State.Error}}error: {{.State.Error}}{{end}}' "$name"
        fi
        exit 0 ;;
    logs)
        podman container exists "$name" || die "no $name container; start one with just run"
        if running; then exec podman exec "$name" journalctl -f "$@"; fi
        exec podman logs "$name" ;;
    sync)
        running || die "$name is not running; start it with just run" ;;
    shell|run|root)
        running || up ;;
    *)
        up
        [ "$cmd" = up ] && exit 0 ;;
esac

w="${size%x*}"
h="${size#*x}"
case "$cmd" in
    shell)     user_exec bash -l ;;
    run)       [ "$#" -gt 0 ] || usage; user_exec "$@" ;;
    steam)
        need_wayland
        if podman exec "${user_env[@]}" "$name" systemctl --user -q is-active gamescope-session-plus@steam.service; then
            die "a Steam session is already running in the container"
        fi
        # The session is a user unit and reads the user manager's environment.
        podman exec "${user_env[@]}" "$name" systemctl --user set-environment \
            WAYLAND_DISPLAY=/run/host/wayland-0 \
            PIPEWIRE_REMOTE=/run/host/pipewire-0 \
            PULSE_SERVER=unix:/run/host/pulse-native \
            BACKEND=wayland SCREEN_WIDTH="$w" SCREEN_HEIGHT="$h"
        stop_units=(gamescope-session-plus@steam.service)
        user_exec gamescope-session-plus steam ;;
    desktop)
        need_wayland
        stop_units=(plasma-workspace.target graphical-session.target)
        # Nested KWin otherwise opens at its 4:3 1024x768 default.
        printf '[Service]\nExecStart=\nExecStart=/usr/bin/kwin_wayland_wrapper --xwayland --width %s --height %s\n' \
            "${desktop_size%x*}" "${desktop_size#*x}" |
            podman exec -i "${user_env[@]}" "$name" sh -c 'd=$XDG_RUNTIME_DIR/systemd/user/plasma-kwin_wayland.service.d &&
                mkdir -p "$d" && cat > "$d/armada-dev-size.conf" && systemctl --user daemon-reload'
        user_exec /usr/libexec/armada/armada-plasma-session standalone ;;
    gamescope) need_wayland; user_exec gamescope -W "$w" -H "$h" -w "$w" -h "$h" "$@" ;;
    root)
        tty=()
        [ -t 0 ] && [ -t 1 ] && tty=(-it)
        podman exec "${tty[@]}" "$name" "${@:-bash}" ;;
    sync)
        repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
        echo "==> system_files"
        # The limits file is this script's own bind mount and can't be replaced.
        tar -C "$repo/system_files" --owner=0 --group=0 --numeric-owner \
            --exclude=./etc/security/limits.d/60-armada-gaming.conf --exclude=__pycache__ -cf - . |
            podman exec -i "$name" tar -C / -xpf - --no-overwrite-dir
        podman exec "$name" sh -c 'chmod 0755 /usr/libexec/armada/* /usr/libexec/os-session-select && systemctl daemon-reload'
        podman exec "${user_env[@]}" "$name" systemctl --user daemon-reload

        echo "==> Decky plugins"
        # The Containerfile's own decky-build stage, tests included.
        limits=()
        out=$("$repo/tools/build-limits.sh")
        [ -z "$out" ] || mapfile -t limits <<<"$out"
        podman build -q "${limits[@]}" --target decky-build -t localhost/armada-decky-build \
            -f "$repo/Containerfile" "$repo" >/dev/null
        stage=$(mktemp -d)
        trap 'rm -rf "$stage"' EXIT
        plugins=(armada-control armada-store)
        podman run --rm --security-opt label=disable -v "$stage:/out" localhost/armada-decky-build \
            sh -c 'for p in "$@"; do cp -r "/build/$p/dist" "/out/$p-dist"; done' sh "${plugins[@]}"
        cp "$repo/build_files/install-decky-plugin.sh" "$stage/"
        tar -C "$repo/decky" -cf "$stage/src.tar" --exclude=node_modules --exclude=__pycache__ "${plugins[@]}"
        podman exec "$name" rm -rf /run/armada-dev-sync
        tar -C "$stage" -cf - . | podman exec -i "$name" sh -c \
            'mkdir -p /run/armada-dev-sync && tar -C /run/armada-dev-sync -xf - && tar -C /run/armada-dev-sync -xf /run/armada-dev-sync/src.tar'
        for p in "${plugins[@]}"; do
            podman exec "$name" bash /run/armada-dev-sync/install-decky-plugin.sh \
                "/run/armada-dev-sync/$p" "/run/armada-dev-sync/$p-dist" "/usr/share/decky-plugins/$p"
        done
        podman exec "$name" sh -c 'rm -rf /run/armada-dev-sync && systemctl restart armada-decky-sync plugin_loader'

        echo "Synced. Decky reloaded; restart other units you changed, e.g.:"
        echo "  just run root systemctl restart <unit>"
        echo "New units, deleted files, other build_files changes and packages need just build." ;;
    *)         usage ;;
esac
