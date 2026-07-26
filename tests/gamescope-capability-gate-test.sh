#!/bin/bash
set -euo pipefail

readonly root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly gate="$root/build_files/verify-gamescope-capability.sh"
readonly temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT

mkdir -p "$temporary/bin"
cat >"$temporary/bin/rpm" <<'EOF'
#!/bin/bash
set -euo pipefail
[[ "${MOCK_RPM_QUERY_FAIL:-0}" != 1 ]] || exit 1
printf '%s\n' "${MOCK_PACKAGE_OWNER:-gamescope}"
EOF
chmod 0755 "$temporary/bin/rpm"

make_binary() {
    local path="$1"
    local content="$2"
    printf '%s' "$content" >"$path"
    chmod 0755 "$path"
}

run_gate() {
    PATH="$temporary/bin:$PATH" /bin/bash "$gate" "$@"
}

make_binary "$temporary/gamescope-good.exe" \
    'ELF fixture --expose-client-sampleable-formats'
run_gate "$temporary/gamescope-good.exe"

make_binary "$temporary/gamescope-missing-option.exe" 'ELF fixture --other-option'
if run_gate "$temporary/gamescope-missing-option.exe" 2>/dev/null; then
    echo "ERROR: capability gate accepted a binary without the required option" >&2
    exit 1
fi

if MOCK_PACKAGE_OWNER=not-gamescope run_gate "$temporary/gamescope-good.exe" 2>/dev/null; then
    echo "ERROR: capability gate accepted a binary owned by another package" >&2
    exit 1
fi

if MOCK_RPM_QUERY_FAIL=1 run_gate "$temporary/gamescope-good.exe" 2>/dev/null; then
    echo "ERROR: capability gate accepted a failed package ownership query" >&2
    exit 1
fi

if run_gate "$temporary/does-not-exist" 2>/dev/null; then
    echo "ERROR: capability gate accepted a missing binary" >&2
    exit 1
fi

echo "Gamescope static capability gate tests passed"
