#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="$ROOT/system_files/usr/libexec/armada/armada-plasma-session"
LIB="$ROOT/system_files/usr/lib/armada/plasma-session-lib"
LOCALE_HELPER="$ROOT/system_files/usr/lib/armada/plasma-locale.py"
SESSION_SELECT="$ROOT/system_files/usr/libexec/os-session-select"
SESSIONS="$ROOT/system_files/usr/share/wayland-sessions"
tmp="$(mktemp -d)"
trap 'kill $(jobs -p) 2>/dev/null || true; rm -rf -- "$tmp"' EXIT

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

source "$LIB"
state="$tmp/state.toml"
[[ "$(armada_plasma_shell "$state")" == desktop ]]
printf 'desktop_session = "armada-plasma.desktop"\n' >"$state"
[[ "$(armada_plasma_shell "$state")" == desktop ]]
printf '[x]\ndesktop_session="armada-plasma-mobile.desktop"\n' >"$state"
[[ "$(armada_plasma_shell "$state")" == mobile ]]
printf 'desktop_session = "plasma.desktop"\n' >"$state"
[[ "$(armada_plasma_shell "$state")" == desktop ]]

grep -qx 'Exec=/usr/libexec/armada/armada-plasma-session standalone' "$SESSIONS/armada-plasma.desktop"
grep -qx 'Exec=/usr/libexec/armada/armada-plasma-session standalone mobile' "$SESSIONS/armada-plasma-mobile.desktop"
grep -qx 'exec /usr/libexec/armada/armada-plasma-session nested' "$ROOT/system_files/usr/bin/armada-nested-desktop"
[[ -x "$ROOT/system_files/usr/bin/armada-nested-desktop" && -x "$SESSION" ]]
[[ "$(<"$ROOT/system_files/usr/share/armada/plasma/nested/kwinrc")" == $'[Wayland]\nVirtualKeyboardMode=2' ]]

mkdir "$tmp/bin" "$tmp/run"
log="$tmp/log"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf '\''systemctl %s\n'\'' "$*" >>"$ARMADA_TEST_LOG"' \
    'case "$2 $4" in' \
    '    "is-active gamescope-session-plus@steam.service") [[ "${ARMADA_TEST_GAME_MODE:-1}" == 1 ]] ;;' \
    '    "is-active armada-plasma-nested-*.service") [[ -n "${ARMADA_TEST_NESTED_UNITS:-}" ]] ;;' \
    '    "is-enabled armada-bottom-screen.service") [[ "${ARMADA_TEST_BOTTOM_ENABLED:-1}" == 1 ]] ;;' \
    'esac || exit 3' \
    '[[ "$2" != stop || "${ARMADA_TEST_STOP_FAILS:-0}" == 0 ]] || exit 1' \
    'if [[ "$2" == list-units ]]; then' \
    '    for unit in ${ARMADA_TEST_NESTED_UNITS:-}; do printf '\''%s loaded active running\n'\'' "$unit"; done' \
    'fi' \
    >"$tmp/bin/systemctl"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    '[[ "${ARMADA_TEST_SYSTEMD_RUN_FAILS:-0}" == 0 ]] || exit 1' \
    'printf '\''systemd-run %s\n'\'' "$*" >>"$ARMADA_TEST_LOG"' \
    >"$tmp/bin/systemd-run"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf '\''%s\0'\'' "$@" >"$ARMADA_TEST_ARGS"' \
    'env | sort >"$ARMADA_TEST_ENV"' \
    >"$tmp/bin/dbus-run-session"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf '\''%s\n'\'' "$* $XDG_CONFIG_DIRS $QT_QPA_PLATFORM" >"$ARMADA_TEST_ENVMANAGER"' \
    >"$tmp/bin/envmanager"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'env | sort >"$ARMADA_TEST_STARTPLASMA_ENV"' \
    'printf '\''%s\n'\'' "$(readlink "$XDG_CONFIG_HOME/plasmashellrc")" "$DESKTOP_SESSION" "$XDG_SESSION_TYPE" "${TEST_UNTOUCHED-unset}" >"$ARMADA_TEST_ARGS"' \
    >"$tmp/bin/startplasma"
# KDE reads plasma-localerc through KConfig; the mock needs no Qt runtime.
cat >"$tmp/bin/kreadconfig6" <<'KREADCONFIG'
#!/usr/bin/env bash
set -eu
file= group= key=
while (($#)); do
    case "$1" in
        --file) file=$2; shift 2 ;;
        --group) group=$2; shift 2 ;;
        --key) key=$2; shift 2 ;;
        *) shift ;;
    esac
done
config_home=${XDG_CONFIG_HOME:-${HOME:-/nonexistent}/.config}
case "$file" in
    */*) path=$file ;;
    *) path="$config_home/$file" ;;
esac
printf '%s %s %s\n' "$path" "$group" "$key" >>"$ARMADA_TEST_KREADCONFIG_LOG"
[[ -f "$path" ]] || exit 0
awk -v group="$group" -v key="$key" '
    /^\[/ { section = substr($0, 2, length($0) - 2); next }
    section == group && index($0, key "=") == 1 { print substr($0, length(key) + 2); exit }
' "$path"
KREADCONFIG
chmod +x "$tmp/bin"/*

session() {
    local home=$1
    shift
    env -i \
        HOME=/test/home USER=armada LANG=C.UTF-8 LANGUAGE=de LC_TIME=de_DE.UTF-8 LC_NUMERIC=de_DE.UTF-8 "${display[@]}" \
        XDG_RUNTIME_DIR="$tmp/run" XDG_CONFIG_HOME="$home" XDG_DATA_DIRS=/test/share XDG_SESSION_ID=9 \
        PATH="/steam/runtime/bin:$PATH" LD_PRELOAD= LC_ALL=C QT_QPA_PLATFORM=xcb QT_IM_MODULE=steam \
        GTK_IM_MODULE=Steam SteamAppId=1 STEAM_COMPAT_APP_ID=1 XCURSOR_THEME=steam VK_INSTANCE_LAYERS=x \
        XDG_CONFIG_DIRS=/steam/xdg XDG_CURRENT_DESKTOP=gamescope XDG_SESSION_TYPE=x11 \
        GAMESCOPE_WAYLAND_DISPLAY=gamescope-0 DBUS_SESSION_BUS_ADDRESS=unix:path=/steam/bus \
        'BASH_FUNC_short_session_recover%%=() { :; }' TEST_UNTOUCHED=1 \
        ARMADA_SYSTEMCTL="$tmp/bin/systemctl" ARMADA_SYSTEMD_RUN="$tmp/bin/systemd-run" \
        ARMADA_DBUS_RUN_SESSION="$tmp/bin/dbus-run-session" ARMADA_KWIN_WAYLAND=/test/kwin \
        ARMADA_PLASMA_MOBILE_ENVMANAGER="$tmp/bin/envmanager" ARMADA_STARTPLASMA="$tmp/bin/startplasma" \
        ARMADA_LOGGER=/usr/bin/true ARMADA_PLASMA_SESSION_LIB="$LIB" \
        ARMADA_TEST_LOG="$log" ARMADA_TEST_ARGS="$tmp/args" ARMADA_TEST_ENV="$tmp/env" \
        ARMADA_TEST_STARTPLASMA_ENV="$tmp/startplasma-env" \
        ARMADA_TEST_ENVMANAGER="$tmp/envmanager" ARMADA_DEVICE_ID=test-device \
        ARMADA_KREADCONFIG="$tmp/bin/kreadconfig6" ARMADA_TEST_KREADCONFIG_LOG="$tmp/kreadconfig" \
        ARMADA_PLASMA_LOCALE_HELPER="$LOCALE_HELPER" \
        "${extra[@]}" \
        "$SESSION" "$@"
}
display=(DISPLAY=:7)
extra=()
args() {
    mapfile -d '' -t actual <"$tmp/args"
}
envval() {
    sed -n "s/^$1=//p" "$tmp/env"
}
expect_env() {
    local actual
    actual="$(envval "$1")"
    [[ "$actual" == "$2" ]] || fail "expected $1=$2, got '$actual'"
}
startplasma_envval() {
    sed -n "s/^$1=//p" "$tmp/startplasma-env"
}
expect_startplasma_env() {
    local actual
    actual="$(startplasma_envval "$1")"
    [[ "$actual" == "$2" ]] || fail "startplasma: expected $1=$2, got '$actual'"
}
expect_args() {
    args
    [[ "${#actual[@]}" == "$#" ]] || fail "expected $# arguments, got ${#actual[@]}: ${actual[*]}"
    local i=0 want
    for want in "$@"; do
        [[ "${actual[$i]}" == "$want" ]] || fail "argument $i: expected '$want', got '${actual[$i]}'"
        i=$((i + 1))
    done
}

if session "$tmp/none" 2>/dev/null; then fail 'accepted a missing surface'; fi
if session "$tmp/none" desktop 2>/dev/null; then fail 'accepted an unknown surface'; fi
if session "$tmp/none" bottom tablet 2>/dev/null; then fail 'accepted an unknown shell'; fi

home="$tmp/standalone"
session "$home" standalone
[[ "$(<"$tmp/args")" == $'plasmashellrc.desktop\nplasma\nwayland\n1' ]]
session "$home" standalone mobile
[[ "$(<"$tmp/args")" == $'plasmashellrc.mobile\nplasma-mobile\nwayland\n1' ]]
session "$home" standalone desktop
[[ "$(<"$tmp/args")" == $'plasmashellrc.desktop\nplasma\nwayland\n1' ]]
[[ ! -e "$home/armada" ]]

home="$tmp/bottom"
mkdir -p "$home"
printf 'shared kwin settings\n' >"$home/kwinrc"
printf 'shared outputs\n' >"$home/kwinoutputconfig.json"
: >"$log"
session "$home" bottom
child_env="/usr/bin/env XDG_CONFIG_HOME='$home'"
expect_args \
    /usr/bin/env "XDG_CONFIG_HOME=$home/armada/plasma/bottom" /test/kwin \
    --x11-display :7 --socket armada-plasma-bottom --fullscreen --no-lockscreen --xwayland \
    --exit-with-session "$child_env /usr/bin/plasmashell -p org.kde.plasma.mobileshell" \
    "$child_env /usr/libexec/kf6/polkit-kde-authentication-agent-1"
[[ ! -s "$log" ]] || fail "bottom touched other units: $(<"$log")"
[[ "$(readlink "$home/plasmashellrc")" == plasmashellrc.mobile ]]
[[ "$(<"$tmp/envmanager")" == "--apply-settings /test/home/.config/plasma-mobile:/etc/xdg offscreen" ]]
[[ "$(envval XDG_CONFIG_DIRS)" == /test/home/.config/plasma-mobile:/etc/xdg ]]
[[ "$(envval PATH)" == /test/home/.local/bin:/test/home/bin:/usr/local/bin:/usr/bin ]]
[[ "$(envval XDG_CURRENT_DESKTOP)" == KDE && "$(envval XDG_SESSION_TYPE)" == wayland ]]
[[ "$(envval PLASMA_PLATFORM)" == phone:handset && "$(envval DISABLE_GAMESCOPE_WSI)" == 1 ]]
[[ "$(envval DISPLAY)" == :7 && "$(envval XDG_DATA_DIRS)" == /usr/share/armada/plasma/bus:/test/share && "$(envval XDG_SESSION_ID)" == 9 ]]
[[ "$(envval ARMADA_DEVICE_ID)" == test-device && "$(envval LANG)" == C.UTF-8 ]]
# No preference means English; Game Mode's inherited LANGUAGE is not reused.
[[ "$(envval LANGUAGE)" == en && "$(envval LC_TIME)" == de_DE.UTF-8 ]]
for leaked in LD_PRELOAD LC_ALL QT_QPA_PLATFORM QT_IM_MODULE GTK_IM_MODULE SteamAppId STEAM_COMPAT_APP_ID \
        XCURSOR_THEME VK_INSTANCE_LAYERS GAMESCOPE_WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS TEST_UNTOUCHED \
        ARMADA_PLASMA_NESTED; do
    ! grep -q "^$leaked=" "$tmp/env" || fail "$leaked reached the bottom session"
done
! grep -q '^BASH_FUNC_' "$tmp/env" || fail 'an exported shell function reached the bottom session'
kwin="$home/armada/plasma/bottom"
[[ "$(<"$kwin/kwinoutputconfig.json")" == 'shared outputs' && ! -L "$kwin/kwinoutputconfig.json" ]]
for file in kwinrc kwinrulesrc kdeglobals kxkbrc kcminputrc kglobalshortcutsrc; do
    [[ "$(readlink "$kwin/$file")" == "../../../$file" ]]
done
[[ "$(<"$kwin/kwinrc")" == 'shared kwin settings' ]]

printf 'bottom scale\n' >"$kwin/kwinoutputconfig.json"
printf 'changed later\n' >"$home/kwinoutputconfig.json"
session "$home" bottom
[[ "$(<"$kwin/kwinoutputconfig.json")" == 'bottom scale' ]]
rm "$kwin/kwinoutputconfig.json"
printf 'garbage\n' >"$kwin/kwinoutputconfig.json.new"
session "$home" bottom
[[ "$(<"$kwin/kwinoutputconfig.json")" == 'changed later' && ! -e "$kwin/kwinoutputconfig.json.new" ]]

extra=(ARMADA_PLASMA_MOBILE_ENVMANAGER=/usr/bin/false)
session "$home" bottom
extra=()
args
[[ "${actual[2]}" == /test/kwin ]] || fail 'a failing settings helper kept the mobile session from starting'

session "$home" bottom desktop
args
[[ "${actual[11]}" == "$child_env /usr/bin/plasmashell" ]]
[[ "$(readlink "$home/plasmashellrc")" == plasmashellrc.desktop ]]
[[ "$(envval XDG_CONFIG_DIRS)" == /etc/xdg ]]
! grep -q '^PLASMA_PLATFORM=' "$tmp/env"

display=()
if session "$tmp/no-display" bottom 2>"$tmp/no-display.err"; then
    fail 'bottom started without DISPLAY'
fi
grep -q 'nested Gamescope did not provide an X11 display' "$tmp/no-display.err"
display=(DISPLAY=:7)

home="$tmp/nested"
mkdir -p "$home/steamos-manager"
printf 'desktop_session = "armada-plasma.desktop"\n' >"$home/steamos-manager/state.toml"
: >"$log"
session "$home" nested
child_env="/usr/bin/env XDG_CONFIG_HOME='$home'"
kwin="$home/armada/plasma/nested"
expect_args \
    /usr/bin/env "XDG_CONFIG_HOME=$kwin" /test/kwin \
    --x11-display :7 --socket armada-plasma-nested --fullscreen --no-lockscreen --xwayland \
    --inputmethod /usr/bin/plasma-keyboard \
    --exit-with-session "$child_env /usr/bin/plasmashell" \
    "$child_env /usr/libexec/kf6/polkit-kde-authentication-agent-1" \
    '/usr/bin/kscreen-doctor output.X11-0.scale.1.5'
nested_id="$(envval ARMADA_PLASMA_NESTED)"
[[ "$nested_id" =~ ^[0-9]+$ ]]
[[ "$(<"$log")" == "systemctl --user is-active --quiet armada-plasma-nested-*.service
systemd-run --user --quiet --collect --unit=armada-plasma-nested-$nested_id $SESSION --restore-bottom $nested_id
systemctl --user stop armada-bottom-screen.service" ]] || fail "unexpected handoff: $(<"$log")"
[[ "$(envval XDG_CONFIG_DIRS)" == /usr/share/armada/plasma/nested:/etc/xdg ]]
! grep -q '^QT_QPA_PLATFORM=\|^SteamAppId=' "$tmp/env"
for file in kwinrc kwinrulesrc kdeglobals kxkbrc kcminputrc kglobalshortcutsrc; do
    [[ "$(readlink "$kwin/$file")" == "../../../$file" ]]
done

printf 'desktop_session = "armada-plasma-mobile.desktop"\n' >"$home/steamos-manager/state.toml"
session "$home" nested
expect_args \
    /usr/bin/env "XDG_CONFIG_HOME=$kwin" /test/kwin \
    --x11-display :7 --socket armada-plasma-nested --fullscreen --no-lockscreen --xwayland \
    --exit-with-session "$child_env /usr/bin/plasmashell -p org.kde.plasma.mobileshell" \
    "$child_env /usr/libexec/kf6/polkit-kde-authentication-agent-1" \
    '/usr/bin/kscreen-doctor output.X11-0.scale.1.5'
[[ "$(envval XDG_CONFIG_DIRS)" == /usr/share/armada/plasma/nested:/test/home/.config/plasma-mobile:/etc/xdg ]]
printf 'saved layout\n' >"$kwin/kwinoutputconfig.json"
session "$home" nested desktop
args
[[ "${#actual[@]}" == 15 && "${actual[13]}" == "$child_env /usr/bin/plasmashell" ]]

: >"$log"
extra=(ARMADA_TEST_NESTED_UNITS=armada-plasma-nested-1.service)
if session "$home" nested 2>"$tmp/dup.err"; then
    fail 'a second nested session started'
fi
grep -q 'already running' "$tmp/dup.err"
! grep -q 'stop\|systemd-run' "$log"
: >"$log"
extra=(ARMADA_TEST_SYSTEMD_RUN_FAILS=1)
if session "$home" nested 2>/dev/null; then
    fail 'nested started without its unit'
fi
extra=()
! grep -q stop "$log" || fail 'the bottom shell was stopped with nothing to bring it back'
: >"$log"
extra=(ARMADA_TEST_STOP_FAILS=1)
if session "$home" nested 2>/dev/null; then
    fail 'nested started although the bottom shell did not stop'
fi
grep -q -- '--restore-bottom' "$log" || fail 'a failed stop left nothing to bring the bottom shell back'
extra=()

# Locale selections apply to the shells that bypass startplasma.
locale_zh="$tmp/locale-zh"
mkdir -p "$locale_zh"
printf '%s\n' \
    '[Formats]' \
    'LANG=zh_CN.UTF-8' \
    'LC_NUMERIC=zh_CN.UTF-8' \
    'LC_TIME=zh_CN.UTF-8' \
    '' \
    '[Translations]' \
    'LANGUAGE=zh_CN' \
    >"$locale_zh/plasma-localerc"
: >"$tmp/kreadconfig"
session "$locale_zh" bottom
expect_env LANGUAGE zh_CN
expect_env LANG zh_CN.UTF-8
expect_env LC_NUMERIC zh_CN.UTF-8
expect_env LC_TIME zh_CN.UTF-8
! grep -q '^LC_ALL=' "$tmp/env" || fail 'LC_ALL reached the localized bottom session'
grep -qx "$locale_zh/plasma-localerc Formats LANG" "$tmp/kreadconfig" ||
    fail 'the bottom session did not read LANG from the shared plasma-localerc'
grep -qx "$locale_zh/plasma-localerc Translations LANGUAGE" "$tmp/kreadconfig" ||
    fail 'the bottom session did not read LANGUAGE from the shared plasma-localerc'
! grep -q "$locale_zh/armada" "$tmp/kreadconfig" ||
    fail 'the bottom session read locale from the per-surface config'

locale_nested="$tmp/locale-nested"
mkdir -p "$locale_nested/steamos-manager"
printf 'desktop_session = "armada-plasma.desktop"\n' >"$locale_nested/steamos-manager/state.toml"
cp "$locale_zh/plasma-localerc" "$locale_nested/plasma-localerc"
: >"$log"
: >"$tmp/kreadconfig"
session "$locale_nested" nested
expect_env LANGUAGE zh_CN
expect_env LANG zh_CN.UTF-8
expect_env LC_NUMERIC zh_CN.UTF-8
expect_env LC_TIME zh_CN.UTF-8

# Formats and translations are independent, like startplasma's startup config.
# Without a translation preference the approved policy selects English.
locale_formats="$tmp/locale-formats"
mkdir -p "$locale_formats"
printf '%s\n' '[Formats]' 'LANG=fr_FR.UTF-8' 'LC_TIME=fr_FR.UTF-8' >"$locale_formats/plasma-localerc"
session "$locale_formats" bottom
expect_env LANGUAGE en
expect_env LANG fr_FR.UTF-8
expect_env LC_TIME fr_FR.UTF-8

# A non-Chinese selection proves the helper does not hardcode zh_CN.
locale_ja="$tmp/locale-ja"
mkdir -p "$locale_ja"
printf '%s\n' '[Formats]' 'LANG=ja_JP.UTF-8' '' '[Translations]' 'LANGUAGE=ja' >"$locale_ja/plasma-localerc"
session "$locale_ja" bottom
expect_env LANGUAGE ja
expect_env LANG ja_JP.UTF-8
expect_env LC_TIME de_DE.UTF-8

# A real device saved Chinese translations but kept a C formats locale. GNU
# gettext ignores LANGUAGE under a C message locale, so the surfaces that bypass
# startplasma need an installed carrier for messages only; formats stay as saved.
locale_device="$tmp/locale-device"
mkdir -p "$locale_device/steamos-manager"
printf 'desktop_session = "armada-plasma.desktop"\n' >"$locale_device/steamos-manager/state.toml"
printf '%s\n' '[Formats]' 'LANG=C.UTF-8' '' '[Translations]' 'LANGUAGE=zh_CN' >"$locale_device/plasma-localerc"
session "$locale_device" bottom
expect_env LANGUAGE zh_CN
expect_env LANG C.UTF-8
expect_env LC_MESSAGES en_US.UTF-8
expect_env LC_TIME de_DE.UTF-8
expect_env LC_NUMERIC de_DE.UTF-8
session "$locale_device" nested
expect_env LANGUAGE zh_CN
expect_env LANG C.UTF-8
expect_env LC_MESSAGES en_US.UTF-8
expect_env LC_TIME de_DE.UTF-8
expect_env LC_NUMERIC de_DE.UTF-8

# The device has no LC_ALL at all; the carrier must survive the startplasma handoff.
locale_device_standalone="$tmp/locale-device-standalone"
mkdir -p "$locale_device_standalone"
cp "$locale_device/plasma-localerc" "$locale_device_standalone/plasma-localerc"
extra=(LC_ALL=)
session "$locale_device_standalone" standalone
extra=()
[[ "$(<"$tmp/args")" == $'plasmashellrc.desktop\nplasma\nwayland\n1' ]]
expect_startplasma_env LANGUAGE zh_CN
expect_startplasma_env LANG C.UTF-8
expect_startplasma_env LC_MESSAGES en_US.UTF-8
expect_startplasma_env LC_TIME de_DE.UTF-8
expect_startplasma_env LC_NUMERIC de_DE.UTF-8

# The carrier is generic; Chinese is not special-cased.
locale_device_ja="$tmp/locale-device-ja"
mkdir -p "$locale_device_ja"
printf '%s\n' '[Formats]' 'LANG=C.UTF-8' '' '[Translations]' 'LANGUAGE=ja' >"$locale_device_ja/plasma-localerc"
session "$locale_device_ja" bottom
expect_env LANGUAGE ja
expect_env LANG C.UTF-8
expect_env LC_MESSAGES en_US.UTF-8

# Explicit message settings win, including the C and POSIX locales.
locale_explicit="$tmp/locale-explicit"
mkdir -p "$locale_explicit"
printf '%s\n' '[Formats]' 'LANG=C.UTF-8' 'LC_MESSAGES=fr_FR.UTF-8' '' '[Translations]' 'LANGUAGE=zh_CN' >"$locale_explicit/plasma-localerc"
session "$locale_explicit" bottom
expect_env LANGUAGE zh_CN
expect_env LANG C.UTF-8
expect_env LC_MESSAGES fr_FR.UTF-8
for value in C POSIX; do
    home="$tmp/locale-explicit-$value"
    mkdir -p "$home"
    printf '%s\n' '[Formats]' 'LANG=C.UTF-8' "LC_MESSAGES=$value" '' '[Translations]' 'LANGUAGE=zh_CN' >"$home/plasma-localerc"
    session "$home" bottom
    expect_env LANGUAGE zh_CN
    expect_env LANG C.UTF-8
    expect_env LC_MESSAGES "$value"
done

# An explicit LC_ALL is preserved and already selects a translated locale.
locale_all_explicit="$tmp/locale-all-explicit"
mkdir -p "$locale_all_explicit"
printf '%s\n' '[Formats]' 'LANG=C.UTF-8' 'LC_ALL=fr_FR.UTF-8' '' '[Translations]' 'LANGUAGE=zh_CN' >"$locale_all_explicit/plasma-localerc"
session "$locale_all_explicit" bottom
expect_env LANGUAGE zh_CN
expect_env LC_ALL fr_FR.UTF-8
! grep -q '^LC_MESSAGES=' "$tmp/env" || fail 'a message carrier was added under an explicit LC_ALL'

# A non-C LANG already selects translations, so no carrier is needed.
locale_non_c="$tmp/locale-non-c"
mkdir -p "$locale_non_c"
printf '%s\n' '[Formats]' 'LANG=fr_FR.UTF-8' '' '[Translations]' 'LANGUAGE=zh_CN' >"$locale_non_c/plasma-localerc"
session "$locale_non_c" bottom
expect_env LANGUAGE zh_CN
expect_env LANG fr_FR.UTF-8
! grep -q '^LC_MESSAGES=' "$tmp/env" || fail 'a message carrier was added for a non-C message locale'

# A leading C or POSIX LANGUAGE item asks gettext not to translate.
for language in C:zh_CN POSIX:de; do
    home="$tmp/locale-language-${language%%:*}"
    mkdir -p "$home"
    printf '%s\n' '[Formats]' 'LANG=C.UTF-8' '' '[Translations]' "LANGUAGE=$language" >"$home/plasma-localerc"
    session "$home" bottom
    expect_env LANGUAGE "$language"
    expect_env LANG C.UTF-8
    ! grep -q '^LC_MESSAGES=' "$tmp/env" || fail "LANGUAGE=$language gained a message carrier"
done

# Empty or missing keys now mean "unset": English wins when Steam has no choice.
locale_empty="$tmp/locale-empty"
mkdir -p "$locale_empty"
printf '%s\n' '[Formats]' 'LANG=' '' '[Translations]' 'LANGUAGE=' >"$locale_empty/plasma-localerc"
session "$locale_empty" bottom
expect_env LANGUAGE en
expect_env LANG C.UTF-8
expect_env LC_TIME de_DE.UTF-8

# No Translations group no longer keeps the inherited selection.
locale_no_translations="$tmp/locale-no-translations"
mkdir -p "$locale_no_translations"
printf '%s\n' '[Formats]' 'LANG=C.UTF-8' >"$locale_no_translations/plasma-localerc"
session "$locale_no_translations" bottom
expect_env LANGUAGE en
expect_env LANG C.UTF-8

# Standalone still hands off to upstream startplasma, but imports the shared
# locale first so a saved translation has a carrier when startplasma applies
# the explicit preferences again.
locale_standalone="$tmp/locale-standalone"
mkdir -p "$locale_standalone"
cp "$locale_zh/plasma-localerc" "$locale_standalone/plasma-localerc"
: >"$tmp/kreadconfig"
extra=(LC_ALL=)
session "$locale_standalone" standalone
extra=()
[[ "$(<"$tmp/args")" == $'plasmashellrc.desktop\nplasma\nwayland\n1' ]]
grep -qx "$locale_standalone/plasma-localerc Formats LANG" "$tmp/kreadconfig" ||
    fail 'standalone did not import the shared locale before startplasma'
grep -qx "$locale_standalone/plasma-localerc Translations LANGUAGE" "$tmp/kreadconfig" ||
    fail 'standalone did not import the saved translation'
expect_startplasma_env LANGUAGE zh_CN
expect_startplasma_env LANG zh_CN.UTF-8

# Approved priority: explicit Plasma LANGUAGE, then the Steam UI language, then
# English. Steam is only read here; the fallback lands in the locale helper.
steam_registry() {
    local home=$1 language=${2-}
    mkdir -p "$home/.steam"
    {
        printf '"Registry"\n{\n\t"HKCU"\n\t{\n\t\t"Software"\n\t\t{\n\t\t\t"Valve"\n\t\t\t{\n\t\t\t\t"Steam"\n\t\t\t\t{\n'
        [[ -z "$language" ]] || printf '\t\t\t\t\t"language"\t\t"%s"\n' "$language"
        printf '\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n'
    } >"$home/.steam/registry.vdf"
}

mkdir -p "$tmp/home-none" "$tmp/locale-policy"
printf '%s\n' '[Formats]' 'LANG=fr_FR.UTF-8' 'LC_TIME=fr_FR.UTF-8' 'LC_NUMERIC=fr_FR.UTF-8' >"$tmp/locale-policy/plasma-localerc"
# No Plasma preference and no Steam registry: inherited LANGUAGE=de must not leak.
extra=(HOME="$tmp/home-none")
session "$tmp/locale-policy" bottom
expect_env LANGUAGE en
expect_env LANG fr_FR.UTF-8
expect_env LC_TIME fr_FR.UTF-8
expect_env LC_NUMERIC fr_FR.UTF-8

# Steam's own UI language is the second choice, with formats untouched.
steam_registry "$tmp/home-zh" schinese
extra=(HOME="$tmp/home-zh")
cp "$tmp/home-zh/.steam/registry.vdf" "$tmp/registry.before"
cp "$tmp/locale-policy/plasma-localerc" "$tmp/localerc.before"
session "$tmp/locale-policy" bottom
expect_env LANGUAGE zh_CN
expect_env LANG fr_FR.UTF-8
expect_env LC_TIME fr_FR.UTF-8
cmp -s "$tmp/registry.before" "$tmp/home-zh/.steam/registry.vdf" ||
    fail 'the Steam registry was modified'
cmp -s "$tmp/localerc.before" "$tmp/locale-policy/plasma-localerc" ||
    fail 'plasma-localerc was modified'

# Every surface imports the same selection.
mkdir -p "$tmp/locale-policy/steamos-manager"
printf 'desktop_session = "armada-plasma.desktop"\n' >"$tmp/locale-policy/steamos-manager/state.toml"
session "$tmp/locale-policy" nested
expect_env LANGUAGE zh_CN
session "$tmp/locale-policy" standalone
expect_startplasma_env LANGUAGE zh_CN

steam_registry "$tmp/home-en" english
extra=(HOME="$tmp/home-en")
session "$tmp/locale-policy" bottom
expect_env LANGUAGE en

# An explicit Plasma choice outranks Steam in both directions.
locale_policy_en="$tmp/locale-policy-en"
mkdir -p "$locale_policy_en"
printf '%s\n' '[Translations]' 'LANGUAGE=en' >"$locale_policy_en/plasma-localerc"
extra=(HOME="$tmp/home-zh")
session "$locale_policy_en" bottom
expect_env LANGUAGE en

locale_policy_zh="$tmp/locale-policy-zh"
mkdir -p "$locale_policy_zh"
printf '%s\n' '[Translations]' 'LANGUAGE=zh_CN' >"$locale_policy_zh/plasma-localerc"
extra=(HOME="$tmp/home-en")
session "$locale_policy_zh" bottom
expect_env LANGUAGE zh_CN

# An empty LANGUAGE means unset, so Steam is consulted.
locale_policy_empty="$tmp/locale-policy-empty"
mkdir -p "$locale_policy_empty"
printf '%s\n' '[Translations]' 'LANGUAGE=' >"$locale_policy_empty/plasma-localerc"
extra=(HOME="$tmp/home-zh")
session "$locale_policy_empty" bottom
expect_env LANGUAGE zh_CN

# A game's language is not the Steam UI language.
mkdir -p "$tmp/home-game/.steam"
printf '"Registry"\n{\n\t"HKCU"\n\t{\n\t\t"Software"\n\t\t{\n\t\t\t"Valve"\n\t\t\t{\n\t\t\t\t"Steam"\n\t\t\t\t{\n\t\t\t\t\t"apps"\n\t\t\t\t\t{\n\t\t\t\t\t\t"570"\n\t\t\t\t\t\t{\n\t\t\t\t\t\t\t"language"\t\t"schinese"\n\t\t\t\t\t\t}\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n' \
    >"$tmp/home-game/.steam/registry.vdf"
extra=(HOME="$tmp/home-game")
session "$tmp/locale-policy" bottom
expect_env LANGUAGE en

# Malformed or unrecognized registry languages fall back to English.
mkdir -p "$tmp/home-malformed/.steam"
printf 'not a registry\n' >"$tmp/home-malformed/.steam/registry.vdf"
extra=(HOME="$tmp/home-malformed")
session "$tmp/locale-policy" bottom
expect_env LANGUAGE en
steam_registry "$tmp/home-unknown" klingon
extra=(HOME="$tmp/home-unknown")
session "$tmp/locale-policy" bottom
expect_env LANGUAGE en
extra=()

home="$tmp/legacy"
mkdir -p "$home"
printf 'legacy desktop settings\n' >"$home/plasmashellrc"
session "$home" bottom
[[ "$(<"$home/plasmashellrc.desktop")" == 'legacy desktop settings' && ! -s "$home/plasmashellrc.mobile" ]]
home="$tmp/conflict"
mkdir -p "$home"
printf 'active settings\n' >"$home/plasmashellrc"
printf 'saved settings\n' >"$home/plasmashellrc.desktop"
session "$home" bottom
[[ "$(readlink "$home/plasmashellrc")" == plasmashellrc.mobile ]]
[[ "$(<"$home/plasmashellrc.conflict")" == 'active settings' && "$(<"$home/plasmashellrc.desktop")" == 'saved settings' ]]
session "$home" standalone
[[ "$(<"$tmp/args")" == $'plasmashellrc.desktop\nplasma\nwayland\n1' ]]

restore() {
    : >"$log"
    env XDG_RUNTIME_DIR="$tmp/run" ARMADA_SYSTEMCTL="$tmp/bin/systemctl" ARMADA_PLASMA_SESSION_LIB="$LIB" \
        ARMADA_TEST_LOG="$log" "$@"
}
started() {
    grep -qx 'systemctl --user start armada-bottom-screen.service' "$log"
}
exited_pid=$(bash -c 'echo $$')
restore "$SESSION" --restore-bottom "$exited_pid"
started || fail 'the bottom shell was not restored'
restore ARMADA_TEST_NESTED_UNITS="armada-plasma-nested-$exited_pid.service" "$SESSION" --restore-bottom "$exited_pid"
started || fail 'its own unit kept the bottom shell from restoring'
restore ARMADA_TEST_NESTED_UNITS="armada-plasma-nested-$exited_pid.service armada-plasma-nested-7.service" "$SESSION" --restore-bottom "$exited_pid"
! started || fail 'the bottom shell was restored under a relaunched nested session'
restore ARMADA_TEST_GAME_MODE=0 "$SESSION" --restore-bottom "$exited_pid"
! started || fail 'the bottom shell was restored outside Game Mode'
restore ARMADA_TEST_BOTTOM_ENABLED=0 "$SESSION" --restore-bottom "$exited_pid"
! started || fail 'a disabled bottom shell was restored'

ARMADA_PLASMA_NESTED="$exited_pid" sleep 3 &
straggler=$!
sleep 0.3
restore "$SESSION" --restore-bottom "$exited_pid" &
watcher=$!
sleep 1
! started || fail 'the bottom shell was restored while the nested session still had processes'
wait "$straggler" "$watcher"
started || fail 'the bottom shell was not restored after the nested session drained'

sleep 2 &
launcher=$!
restore "$SESSION" --restore-bottom "$launcher" &
watcher=$!
sleep 1
! started || fail 'the bottom shell was restored while the launcher was still running'
wait "$launcher" "$watcher"
started || fail 'the bottom shell was not restored after the launcher exited'

restore "$SESSION" --start-bottom
started
: >"$log"
( exec 9<>"$tmp/run/armada-plasma-session.lock"; flock 9; sleep 2 ) &
holder=$!
sleep 0.3
env XDG_RUNTIME_DIR="$tmp/run" ARMADA_SYSTEMCTL="$tmp/bin/systemctl" ARMADA_PLASMA_SESSION_LIB="$LIB" \
    ARMADA_TEST_LOG="$log" "$SESSION" --start-bottom &
waiter=$!
sleep 1
[[ ! -s "$log" ]] || fail 'a bottom start did not wait for the handoff lock'
wait "$holder" "$waiter"
started || fail 'the bottom start did not run once the lock was free'
restore ARMADA_TEST_NESTED_UNITS=armada-plasma-nested-7.service "$SESSION" --start-bottom
! started || fail 'the bottom shell was started under a nested session'

printf '%s\n' '#!/usr/bin/env bash' 'printf '\''%s\n'\'' "$* ${DBUS_SESSION_BUS_ADDRESS-unset}" >"$SELECT_LOG"' >"$tmp/bin/steamosctl"
chmod +x "$tmp/bin/steamosctl"
select_session() {
    : >"$tmp/select-log"
    env -u ARMADA_PLASMA_NESTED DBUS_SESSION_BUS_ADDRESS=unix:path=/private XDG_RUNTIME_DIR=/run/user/test \
        SELECT_LOG="$tmp/select-log" ARMADA_STEAMOSCTL="$tmp/bin/steamosctl" ARMADA_PLASMA_SESSION_LIB="$LIB" "$@"
}
marker="test-$$-$RANDOM"
ARMADA_PLASMA_NESTED="$marker" sleep 60 &
inside=$!
ARMADA_PLASMA_NESTED="other-$marker" sleep 60 &
outside=$!
sleep 0.2
select_session ARMADA_PLASMA_NESTED="$marker" bash "$SESSION_SELECT" gamescope
[[ ! -s "$tmp/select-log" ]]
wait "$inside" && fail 'a nested process survived Return to Game Mode'
kill -0 "$outside"
kill "$outside"
select_session bash "$SESSION_SELECT" gamescope
[[ "$(<"$tmp/select-log")" == 'switch-to-game-mode unix:path=/private' ]]
select_session ARMADA_PLASMA_NESTED="$marker" bash "$SESSION_SELECT" desktop
[[ "$(<"$tmp/select-log")" == 'switch-to-desktop-mode unix:path=/run/user/test/bus' ]]

echo 'plasma session tests passed'
