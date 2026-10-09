#!/usr/bin/env bash
# generate.sh runs with no network, so the archive cannot depend on anything
# build.sh did not fetch and checksum. Asserted here for CI and local builds.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PKG="$ROOT/packages/steam-bootstrap"

assert_contains() {
    local file="$1" needle="$2"
    if ! grep -Fq -- "$needle" "$file"; then
        printf 'missing %s in %s\n' "$needle" "$file" >&2
        exit 1
    fi
}

# Asserted as a property, not an exact line, so new mount flags cannot drop it.
python3 - "$ROOT/packages/Containerfile" <<'PYEOF'
import re, sys

joined = re.sub(r'\\\n\s*', ' ', open(sys.argv[1]).read())
runs = [l for l in joined.splitlines() if l.startswith('RUN ') and 'generate.sh' in l]
if len(runs) != 1:
    sys.exit(f"expected exactly one RUN invoking generate.sh, found {len(runs)}")
if '--network=none' not in runs[0]:
    sys.exit("generate.sh must run with --network=none: " + runs[0])
PYEOF

# The same guarantee in local builds.
assert_contains "$ROOT/packages/build-local.sh" 'phase2_args=(--network none)'

# Both paths must install the same builder dependencies.
assert_contains "$ROOT/packages/Containerfile" 'steam-bootstrap/install-builder-deps.sh'
assert_contains "$PKG/Containerfile" 'install-builder-deps.sh'

# build.sh runs test.py, so a test that executes build.sh recurses forever.
if grep -q 'python3 test.py' "$PKG/build.sh"; then
    if grep -Eq '(subprocess|os\.system|check_call|run)\([^)]*build\.sh' "$PKG/test.py"; then
        printf 'packages/steam-bootstrap/test.py executes build.sh, which runs test.py: infinite recursion\n' >&2
        exit 1
    fi
fi

printf 'Steam bootstrap offline generation test passed\n'
