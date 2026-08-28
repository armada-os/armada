#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SHIM="$ROOT/system_files/usr/bin/steam"
ENTRY="$ROOT/system_files/usr/share/applications/steam.desktop"
MIMEAPPS="$ROOT/system_files/etc/xdg/mimeapps.list"
VENDOR="$ROOT/build_files/40-vendor-system-files.sh"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

# Steam writes `Exec=steam steam://rungameid/<id>`, so the command has to exist
# on PATH or every generated shortcut dies with ENOENT.
[[ -x "$SHIM" ]] || fail "steam shim is not executable: $SHIM"

# A dropped +x here has broken an image build before.
mode="$(git -C "$ROOT" ls-files -s -- system_files/usr/bin/steam 2>/dev/null | awk '{print $1}')"
if [[ -n "$mode" ]]; then
    [[ "$mode" == 100755 ]] || fail "steam shim tracked as $mode, expected 100755"
fi

# Behaviour: arguments must reach launch-steam intact, spaces included.
stub="$TEST_ROOT/launch-steam"
cat > "$stub" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$@"
STUB
chmod 0755 "$stub"
sed "s#/usr/libexec/armada/launch-steam#$stub#" "$SHIM" > "$TEST_ROOT/steam"
chmod 0755 "$TEST_ROOT/steam"

got="$("$TEST_ROOT/steam" 'steam://rungameid/434050' 'two words')"
expected=$'--desktop\nsteam://rungameid/434050\ntwo words'
[[ "$got" == "$expected" ]] || fail "shim mangled arguments: $(printf '%q' "$got")"

# Bare invocation, which is what a menu launch reduces to: add nothing but the flag.
got="$("$TEST_ROOT/steam")"
[[ "$got" == "--desktop" ]] || fail "bare shim should pass only --desktop, got: $got"

grep -qx 'Exec=/usr/libexec/armada/launch-steam --desktop %U' "$ENTRY" \
    || fail "steam.desktop Exec is missing %U"
grep -qx 'MimeType=x-scheme-handler/steam;' "$ENTRY" \
    || fail "steam.desktop does not advertise x-scheme-handler/steam"

# Advertising the scheme does not make Steam the default; the association does.
grep -qx 'x-scheme-handler/steam=steam.desktop' "$MIMEAPPS" \
    || fail "mimeapps.list has no default for x-scheme-handler/steam"

# system_files is copied after the RPM scriptlets, so the cache needs a rebuild.
grep -q 'update-desktop-database -q /usr/share/applications' "$VENDOR" \
    || fail "build does not refresh mimeinfo.cache after vendoring system_files"

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$ENTRY" || fail "steam.desktop failed validation"
    validated=" and validates"
else
    validated=" (desktop-file-validate absent, skipped)"
fi

echo "steam shortcut: shim forwards args, scheme handler registered${validated}"
