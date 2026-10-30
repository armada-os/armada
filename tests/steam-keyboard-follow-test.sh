#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
FOLLOW="$ROOT/system_files/usr/libexec/armada/steam-keyboard-follow"
tmp="$(mktemp -d)"
trap 'kill $(jobs -p) 2>/dev/null || true; rm -rf -- "$tmp"' EXIT

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

[[ -x "$FOLLOW" ]]
grep -qx 'Exec=/usr/libexec/armada/steam-keyboard-follow' "$ROOT/system_files/etc/xdg/autostart/armada-steam-keyboard.desktop"
grep -qx 'armadasteamkeyboardEnabled=true' "$ROOT/system_files/usr/share/armada/plasma/desktop/kwinrc"
grep -q '"Id": "armadasteamkeyboard"' "$ROOT/system_files/usr/share/kwin/scripts/armadasteamkeyboard/metadata.json"
[[ -f "$ROOT/system_files/usr/share/kwin/scripts/armadasteamkeyboard/contents/code/main.js" ]]

mkdir "$tmp/bin"
# Each focus state is announced once, after the property already holds it.
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'if [[ "$1" == monitor ]]; then' \
    '    for state in $TEST_STATES; do' \
    '        printf "%s\n" "$state" >"$TEST_DIR/active"' \
    '        echo "/VirtualKeyboard: org.kde.kwin.VirtualKeyboard.activeChanged ()"' \
    '        sleep 0.4' \
    '    done' \
    'else' \
    '    printf "(<%s>,)\n" "$(<"$TEST_DIR/active")"' \
    'fi' \
    >"$tmp/bin/gdbus"
printf '%s\n' '#!/usr/bin/env bash' 'printf "%s\n" "$*" >>"$TEST_DIR/steam.log"' >"$tmp/bin/steam"
chmod +x "$tmp/bin"/*
# A process named steam stands in for the client.
mkdir "$tmp/client"
cp "$(command -v sleep)" "$tmp/client/steam"
"$tmp/client/steam" 60 &
printf '%s\n' "$!" >"$tmp/steam.pid"

follow() {
    rm -f "$tmp/steam.log"
    env PATH="$tmp/bin:$PATH" TEST_DIR="$tmp" ARMADA_GDBUS="$tmp/bin/gdbus" ARMADA_STEAM="$tmp/bin/steam" \
        ARMADA_STEAM_PID="$tmp/steam.pid" "$@" "$FOLLOW"
}

follow XDG_CONFIG_DIRS=/home/u/.config/kdedefaults:/usr/share/armada/plasma/desktop:/etc/xdg \
    ARMADA_CLOSE_DELAY=0.1 TEST_STATES="true true false false true"
[[ "$(<"$tmp/steam.log")" == $'steam://open/keyboard\nsteam://close/keyboard\nsteam://open/keyboard' ]] \
    || fail "unexpected Steam calls: $(<"$tmp/steam.log")"

# Clicking into another field must not close and reopen the keyboard.
follow XDG_CONFIG_DIRS=/home/u/.config/kdedefaults:/usr/share/armada/plasma/desktop:/etc/xdg \
    ARMADA_CLOSE_DELAY=1 TEST_STATES="true false true"
[[ "$(<"$tmp/steam.log")" == 'steam://open/keyboard' ]] || fail "focus blip reopened the keyboard: $(<"$tmp/steam.log")"

follow XDG_CONFIG_DIRS=/home/u/.config/kdedefaults:/usr/share/armada/plasma/desktop:/etc/xdg \
    TEST_STATES="true false" ARMADA_STEAM_PID="$tmp/missing.pid"
[[ ! -e "$tmp/steam.log" ]] || fail "started Steam to open its keyboard"

# Plasma Mobile keeps its own keyboard.
follow XDG_CONFIG_DIRS=/etc/xdg TEST_STATES="true"
[[ ! -e "$tmp/steam.log" ]] || fail "opened Steam's keyboard outside the desktop shell"
