#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 - "$ROOT" "$WORK" <<'PYEOF'
import importlib.machinery
import importlib.util
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
work = pathlib.Path(sys.argv[2])
lib = root / "system_files/usr/lib/armada"
sys.path.insert(0, str(lib))
import armada_perf  # noqa: F401

control_path = root / "system_files/usr/libexec/armada/armada-control"
loader = importlib.machinery.SourceFileLoader("armada_control", str(control_path))
spec = importlib.util.spec_from_loader("armada_control", loader)
control = importlib.util.module_from_spec(spec)
loader.exec_module(control)

control.SLEEP_CONFIG = work / "sleep.conf"
control.device_env = lambda: {"ARMADA_SOC_CLASS": "SM8550"}

assert control.sm8550_sleep_enabled() is False

control.SLEEP_CONFIG.write_text("future_sleep_setting=keep\n")
assert control.action_set_sm8550_sleep_enabled({"enabled": True}) == {"enabled": True}
assert control.SLEEP_CONFIG.read_text() == (
    "future_sleep_setting=keep\nsm8550_native_sleep=1\n"
)
assert control.sm8550_sleep_enabled() is True

assert control.action_set_sm8550_sleep_enabled({"enabled": False}) == {"enabled": False}
assert control.SLEEP_CONFIG.read_text() == (
    "future_sleep_setting=keep\nsm8550_native_sleep=0\n"
)
assert control.sm8550_sleep_enabled() is False

control.SLEEP_CONFIG.write_text("sm8550_native_sleep=invalid\n")
assert control.sm8550_sleep_enabled() is False

control.device_env = lambda: {"ARMADA_SOC_CLASS": "SM8650"}
try:
    control.action_set_sm8550_sleep_enabled({"enabled": True})
except RuntimeError:
    pass
else:
    raise AssertionError("native sleep setting accepted on a non-SM8550 device")
PYEOF

echo "Armada Control settings tests passed"
