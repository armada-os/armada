#!/bin/bash
# Armada's changes to Valve's Lepton launcher, as wrappers around its functions and commands.

source "$(dirname -- "${BASH_SOURCE[0]}")/liblepton.valve.sh"

function armada_log()
{
    echo "armada: $*" >&2
}

function armada_wrap()
{
    if ! declare -F "$1" >/dev/null; then
        armada_log "Lepton $(cat "${LEPTON_DIR}/../version.txt" 2>/dev/null) has no $1; skipping: $2"
        return 1
    fi
    eval "valve_$(declare -f "$1")"
}

# Automatic forwarding publishes every container port on all host addresses, and adb accepts anyone.
function podman()
{
    if [[ "${1:-}" != run ]]; then
        command podman "$@"
        return
    fi
    local ARG PORT ARGS=() NETWORKS=0
    for ARG in "$@"; do
        case "${ARG}" in
            --network=none)
                NETWORKS=$((NETWORKS + 1))
                ;;
            --network=pasta:*)
                NETWORKS=$((NETWORKS + 1))
                PORT="$(adb_port)"
                if [[ ! "${PORT}" =~ ^[0-9]+$ ]]; then
                    armada_log "no adb port; refusing to start the container"
                    return 1
                fi
                ARG="$(sed -E 's/,(-[tuTU]|--(tcp|udp)-ports),[^,]+//g' <<< "${ARG}"),-t,127.0.0.1/${PORT}"
                ;;
            --network|--network=*|--net|--net=*|-p|-p=*|--publish|--publish=*|-P|--publish-all|--publish-all=*)
                armada_log "unexpected podman argument ${ARG}; refusing to start the container"
                return 1
                ;;
        esac
        ARGS+=("${ARG}")
    done
    if [[ "${NETWORKS}" != 1 ]]; then
        armada_log "expected one --network argument, found ${NETWORKS}; refusing to start the container"
        return 1
    fi
    command podman "${ARGS[@]}"
}

# SDL ignores Steam's virtual gamepad unless Steam's hint for it reaches the game.
if [[ -n "${SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD:-}" ]]; then
    LEPTON_ENV_SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD="${SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD}"
fi

function armada_ext_display()
{
    [[ -n "${ARMADA_EXT_WAYLAND_DISPLAY:-}" && -e "${XDG_RUNTIME_DIR}/${ARMADA_EXT_WAYLAND_DISPLAY}" ]]
}

if armada_wrap setup_podman_mounts "gamepads and the second display"; then
    function setup_podman_mounts()
    {
        valve_setup_podman_mounts "$@"

        # Steam Input presents every controller as a virtual pad, vendor 28de.
        local SYS_EV EV
        for SYS_EV in /sys/devices/virtual/input/input*/event*; do
            [[ "$(cat "${SYS_EV}/device/id/vendor" 2>/dev/null)" == "28de" ]] || continue
            EV="/dev/input/${SYS_EV##*/}"
            if [[ -r "${EV}" ]]; then
                podman_mount_entry "${EV}" "${EV}" rw
            fi
        done

        if armada_ext_display; then
            podman_mount_entry "${XDG_RUNTIME_DIR}/${ARMADA_EXT_WAYLAND_DISPLAY}" "/waydroid/xdg/wayland-1" rw,U
        fi
    }
fi

if armada_wrap setup_props "phone density and the second display"; then
    function setup_props()
    {
        valve_setup_props "$@"

        local PROPS_FILE="$(props_file)"
        # Without a density the display HAL falls back to 180 dpi and Android's own UI is half size.
        echo "ro.sf.lcd_density=320" >> "${PROPS_FILE}"
        if armada_ext_display && grep -q '^waydroid.wayland_display=' "${PROPS_FILE}"; then
            echo "waydroid.wayland_display_ext=wayland-1" >> "${PROPS_FILE}"
        fi
    }
fi

if armada_wrap setup_mounts "home folder, SD cards and split APKs"; then
    function setup_mounts()
    {
        valve_setup_mounts "$@"

        # Every split carries the app's id, so Valve's search can settle on one of them.
        if is_app; then
            BASE_APK="$(lepton_basename "$(get_apk_path)")"
        fi

        if is_sysbake; then
            return 0
        fi

        # Apps that turn a picked folder back into a file path only accept shared storage.
        local SHARED="$(readlink -f "$(data_mount_path)/media/0")"
        if [[ ! -d "${SHARED}" || "${SHARED}" == / ]]; then
            armada_log "no shared storage at $(data_mount_path)/media/0; skipping: home folder and SD cards"
            return 0
        fi
        rm -rf "${SHARED}/Home"
        ln -s "${HOME}" "${SHARED}/Home"
        if [[ -d "/run/media/${USER}" ]]; then
            rm -rf "${SHARED}/SD cards"
            ln -s "/run/media/${USER}" "${SHARED}/SD cards"
        fi
        podman_mount_entry "${HOME}" "${HOME}" rw
        podman_mount_entry_optional "/run/media/${USER}" "/run/media/${USER}" rw
    }
fi

# Valve clears the baked app after a run under 30 seconds, which drops its folder grants.
if armada_wrap clear_baked_app_data "keeping the baked app after an early exit"; then
    function clear_baked_app_data()
    {
        if [[ "${1:-}" == "early exit" ]]; then
            println "Keeping baked app data after an early exit"
            return 0
        fi
        valve_clear_baked_app_data "$@"
    }
fi

# Split APKs: base.apk plus the splits listed in .armada-apks beside it.
function get_app_apks()
{
    local APK_PATH="${1:-$(get_apk_path)}"
    local APK_DIR="$(dirname "${APK_PATH}")"
    if [[ "$(basename "${APK_PATH}")" != base.apk || ! -f "${APK_DIR}/.armada-apks" ]]; then
        printf '%s\n' "${APK_PATH}"
        return
    fi
    local NAMES=() FILES=() NAME
    mapfile -t NAMES < "${APK_DIR}/.armada-apks"
    [[ "${NAMES[0]:-}" == base.apk ]] || return 1
    for NAME in "${NAMES[@]}"; do
        [[ "${NAME}" =~ ^[A-Za-z0-9_.-]+\.apk$ && -f "${APK_DIR}/${NAME}" ]] || return 1
        FILES+=("${APK_DIR}/${NAME}")
    done
    printf '%s\n' "${FILES[@]}"
}

if armada_wrap get_apk_path "split APKs"; then
    function get_apk_path()
    {
        if [[ -z "${APP_PATH}" && -f "${APP_DIR}/base.apk" ]]; then
            APP_PATH="${APP_DIR}/base.apk"
        fi
        valve_get_apk_path "$@"
    }
fi

if armada_wrap extract_app_hash "split APK change tracking"; then
    function extract_app_hash()
    {
        local APKS=()
        mapfile -t APKS < <(get_app_apks "${1:-$(get_apk_path)}")
        [[ "${#APKS[@]}" -gt 0 ]] || return 1
        if [[ "${#APKS[@]}" == 1 ]]; then
            valve_extract_app_hash "$@"
        else
            sha256sum "${APKS[@]}" | sha256sum | awk '{print $1}'
        fi
    }
fi

# Valve installs one APK with `adb install`; a split set needs install-multiple.
ARMADA_ADB="${ADB:-adb}"
function armada_adb()
{
    local I LAST=$(($# - 1)) ARGS=("$@") APKS=()
    for ((I = 0; I < LAST; I++)); do
        [[ "${ARGS[I]}" == install ]] || continue
        mapfile -t APKS < <(get_app_apks "${ARGS[LAST]}")
        if [[ "${#APKS[@]}" == 0 ]]; then
            armada_log "bad APK list beside ${ARGS[LAST]}"
            return 1
        fi
        if [[ "${#APKS[@]}" -gt 1 ]]; then
            ARGS[I]=install-multiple
            ARGS=("${ARGS[@]:0:LAST}" "${APKS[@]}")
        fi
        break
    done
    "${ARMADA_ADB}" "${ARGS[@]}"
}
ADB=armada_adb
