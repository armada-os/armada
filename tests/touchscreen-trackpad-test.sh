#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - \
    "$ROOT/system_files/usr/lib/armada/touchscreen_trackpad.py" \
    "$ROOT/system_files/usr/libexec/armada/touchscreen-trackpad" \
    "$ROOT/system_files/usr/libexec/armada/armada-control" \
    "$ROOT/decky/armada-control/py_modules/armada_control/touchscreen.py" <<'PY'
from pathlib import Path
import sys

for name in sys.argv[1:]:
    source = Path(name).read_text(encoding="utf-8")
    compile(source, name, "exec")
PY
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/tests/touchscreen-trackpad-test.py"

grep -q 'python3-evdev' "$ROOT/build_files/10-base-packages.sh"
grep -q 'enable armada-touchscreen-trackpad.service' "$ROOT/build_files/40-vendor-system-files.sh"

printf 'touchscreen trackpad tests passed\n'
