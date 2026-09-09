#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SYNC="$ROOT/system_files/usr/lib/decky-loader/armada-decky-sync"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

mkdir -p "$WORK/bin" "$WORK/bundled" "$WORK/homebrew/services" "$WORK/plugins"
cat > "$WORK/bin/chcon" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$WORK/bin/chcon"

sed \
    -e "s|user_name=armada|user_name=$(id -un)|" \
    -e "s|homebrew=\"/var/home/\${user_name}/homebrew\"|homebrew=\"$WORK/homebrew\"|" \
    -e "s|loader_src=/usr/share/decky-loader/PluginLoader|loader_src=$WORK/bundled/PluginLoader|" \
    -e "s|loader_version_src=/usr/share/decky-loader/.loader.version|loader_version_src=$WORK/bundled/.loader.version|" \
    -e "s|src=/usr/share/decky-plugins|src=$WORK/plugins|" \
    "$SYNC" > "$WORK/sync"
chmod +x "$WORK/sync"

run_case() {
    local name=$1 installed=$2 bundled=$3 expected=$4
    printf '%s\n' "$installed" > "$WORK/homebrew/services/.loader.version"
    printf 'installed %s\n' "$installed" > "$WORK/homebrew/services/PluginLoader"
    chmod +x "$WORK/homebrew/services/PluginLoader"
    printf '%s\n' "$bundled" > "$WORK/bundled/.loader.version"
    printf 'bundled %s\n' "$bundled" > "$WORK/bundled/PluginLoader"
    chmod +x "$WORK/bundled/PluginLoader"

    PATH="$WORK/bin:$PATH" "$WORK/sync"
    actual=$(<"$WORK/homebrew/services/.loader.version")
    [[ "$actual" == "$expected" ]] ||
        fail "$name: expected $expected, got $actual"
    actual=$(<"$WORK/homebrew/services/PluginLoader")
    if [[ "$expected" == "$bundled" && "$installed" != "$bundled" ]]; then
        [[ "$actual" == "bundled $bundled" ]] ||
            fail "$name: expected bundled loader, got $actual"
    else
        [[ "$actual" == "installed $installed" ]] ||
            fail "$name: expected installed loader, got $actual"
    fi
}

run_case final-replaces-prerelease v3.2.8-pre1 v3.2.8 v3.2.8
run_case older-prerelease-does-not-replace-final v3.2.8 v3.2.8-pre1 v3.2.8
run_case newer-prerelease-replaces-final v3.2.8 v3.2.9-pre1 v3.2.9-pre1
run_case older-release-does-not-replace-newer v3.2.9 v3.2.8 v3.2.9
run_case newer-prerelease-replaces-older v3.2.8-pre1 v3.2.8-pre2 v3.2.8-pre2
run_case equal-version-preserves-loader v3.2.8 v3.2.8 v3.2.8

printf 'decky sync tests passed\n'
