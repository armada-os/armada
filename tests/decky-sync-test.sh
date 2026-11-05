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

# Fake loader: ELF e_machine byte at offset 18, label on the last line.
write_loader() {
    { printf '%018d' 0; printf "\\x$2\n%s\n" "$3"; } > "$1"
    chmod +x "$1"
}

run_case() {
    local name=$1 installed=$2 installed_arch=$3 bundled=$4 winner=$5
    printf '%s\n' "$installed" > "$WORK/homebrew/services/.loader.version"
    write_loader "$WORK/homebrew/services/PluginLoader" "$installed_arch" "installed $installed"
    printf '%s\n' "$bundled" > "$WORK/bundled/.loader.version"
    write_loader "$WORK/bundled/PluginLoader" b7 "bundled $bundled"

    PATH="$WORK/bin:$PATH" "$WORK/sync"
    local expected=$installed
    [[ "$winner" == installed ]] || expected=$bundled
    actual=$(<"$WORK/homebrew/services/.loader.version")
    [[ "$actual" == "$expected" ]] ||
        fail "$name: expected version $expected, got $actual"
    actual=$(tail -n1 "$WORK/homebrew/services/PluginLoader")
    [[ "$actual" == "$winner $expected" ]] ||
        fail "$name: expected $winner loader, got $actual"
}

run_case final-replaces-prerelease v3.2.8-pre1 b7 v3.2.8 bundled
run_case older-prerelease-does-not-replace-final v3.2.8 b7 v3.2.8-pre1 installed
run_case newer-prerelease-replaces-final v3.2.8 b7 v3.2.9-pre1 bundled
run_case older-release-does-not-replace-newer v3.2.9 b7 v3.2.8 installed
run_case newer-prerelease-replaces-older v3.2.8-pre1 b7 v3.2.8-pre2 bundled
run_case equal-version-preserves-loader v3.2.8 b7 v3.2.8 installed
run_case arm64-replaces-equal-x86 v3.3.1 3e v3.3.1 bundled
run_case arm64-replaces-newer-x86 v3.3.2 3e v3.3.1 bundled

printf 'decky sync tests passed\n'
