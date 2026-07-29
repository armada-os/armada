#!/usr/bin/bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
launcher="${repo_root}/system_files/usr/libexec/armada/nested-gaming"
bash -n "$launcher"

require() {
    local contract=$1 literal=$2
    grep -Fq -- "$literal" "$launcher" || {
        printf 'missing MangoApp contract: %s\n' "$contract" >&2
        exit 1
    }
}

require 'Steam uses MangoApp' 'export STEAM_USE_MANGOAPP=1'
require 'Steam exposes MangoApp presets' 'export STEAM_MANGOAPP_PRESETS_SUPPORTED=1'
require 'Steam exposes horizontal MangoApp' 'export STEAM_MANGOAPP_HORIZONTAL_SUPPORTED=1'
require 'Steam uses MangoApp overlay property handling' 'export STEAM_DISABLE_MANGOAPP_ATOM_WORKAROUND=1'
require 'nested clients select X11' 'export XDG_SESSION_TYPE=x11'
# These are literal source contracts, not expressions to expand in this test.
# shellcheck disable=SC2016
require 'session creates a private MangoHud config' 'MANGOHUD_CONFIGFILE=$(mktemp /tmp/mangohud.XXXXXXXX)'
require 'session exports its MangoHud config' 'export MANGOHUD_CONFIGFILE'
# shellcheck disable=SC2016
require 'MangoApp starts hidden' 'echo "no_display" >"$MANGOHUD_CONFIGFILE"'
# shellcheck disable=SC2016
require 'session removes the private MangoHud config' 'trap '\''rm -f -- "$socket" "$MANGOHUD_CONFIGFILE"'\'' EXIT'
require 'MangoApp is supervised' 'while true; do'
require 'MangoApp failures do not defeat supervision' 'mangoapp || true'
require 'MangoApp restart is rate limited' 'sleep 1'
