#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SETUP="$ROOT/system_files/usr/libexec/armada/setup-dual-screen"
python3 - <<'PY' "$SETUP"
import importlib.machinery
import importlib.util
import sys
loader = importlib.machinery.SourceFileLoader("setup_dual_screen", sys.argv[1])
spec = importlib.util.spec_from_loader(loader.name, loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)
ok = mod.pin_touchscreen("Missing Touch", "DSI-2", {})
assert ok is True, "missing touchscreen should not fail display layout"
print("missing touchscreen is non-fatal")
PY
