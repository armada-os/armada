#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "$ROOT" <<'PY'
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
patcher = root / "packages/proton-cachyos/patch-proton-cachyos-dxvk-probe.py"


def run_patcher(source):
    with tempfile.TemporaryDirectory() as temp_dir:
        target = pathlib.Path(temp_dir) / "proton"
        target.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(patcher), str(target)],
            capture_output=True,
            text=True,
        )
        return result, target.read_text(encoding="utf-8")


result, output = run_patcher(
    'before\n    MODERN_DXVK_FEATURES = ["descriptorIndexing"]  # upstream\nafter\n'
)
if result.returncode != 0:
    raise SystemExit(result.stderr)
expected = (
    "before\n"
    "    MODERN_DXVK_FEATURES = ['descriptorIndexing', 'storageBuffer8BitAccess']  # upstream\n"
    "after\n"
)
if output != expected:
    raise SystemExit(f"unexpected patched output:\n{output}")

result, _ = run_patcher("MODERN_DXVK_FEATURES = ['storageBuffer8BitAccess']\n")
if result.returncode == 0 or "found 0" not in result.stderr:
    raise SystemExit("missing probe did not fail closed")

result, _ = run_patcher(
    "MODERN_DXVK_FEATURES = ['descriptorIndexing']\n"
    "MODERN_DXVK_FEATURES = [\"descriptorIndexing\"]\n"
)
if result.returncode == 0 or "found 2" not in result.stderr:
    raise SystemExit("duplicate probes did not fail closed")

print("Proton-CachyOS DXVK probe test passed")
PY
