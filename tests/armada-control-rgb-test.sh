#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 -B - "$ROOT" <<'PYEOF'
import importlib.machinery
import importlib.util
from pathlib import Path
import sys

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "system_files/usr/lib/armada"))

control_path = root / "system_files/usr/libexec/armada/armada-control"
loader = importlib.machinery.SourceFileLoader("armada_control_service", str(control_path))
spec = importlib.util.spec_from_loader("armada_control_service", loader)
control = importlib.util.module_from_spec(spec)
loader.exec_module(control)

commands = []


def check_output(command, **kwargs):
    commands.append(command)
    if command[-1] == "get":
        return '{"version":1,"enabled":false,"brightness":25,"color":"FFFFFF"}'
    return '{"version":1,"enabled":true,"brightness":40,"color":"A1B2C3"}'


control.subprocess.check_output = check_output
control.device_env = lambda: {}
assert control.action_get_rgb({}) is None
assert commands == []

control.device_env = lambda: {"ARMADA_RGB_BACKEND": "multicolor"}
state = control.action_get_rgb({})
assert state["color"] == "FFFFFF"
assert commands.pop() == [control.RGB_TOOL, "get"]

state = control.action_set_rgb({"enabled": True, "color": "a1b2c3", "brightness": 40})
assert state["color"] == "A1B2C3"
assert commands.pop() == [
    control.RGB_TOOL,
    "set",
    "--color",
    "a1b2c3",
    "--brightness",
    "40",
]

control.action_set_rgb({"enabled": False})
assert commands.pop() == [control.RGB_TOOL, "off"]

for request in (
    {"enabled": True, "color": "12345", "brightness": 40},
    {"enabled": True, "color": "FFFFFF", "brightness": 101},
):
    try:
        control.action_set_rgb(request)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid RGB state was accepted")

sys.path.insert(0, str(root / "decky/armada-control/py_modules"))
from armada_control import rgb

calls = []
rgb.call = lambda action, **payload: calls.append((action, payload)) or {}
assert rgb.get_rgb() == {}
assert calls.pop() == ("get_rgb", {})
rgb.set_rgb(True, "112233", 50)
assert calls.pop() == (
    "set_rgb",
    {"enabled": True, "color": "112233", "brightness": 50},
)
PYEOF

grep -Fq 'ConditionPathExists=/etc/armada/rgb.json' "$ROOT/system_files/usr/lib/systemd/system/armada-rgb.service"
grep -Fq 'ExecStart=/usr/bin/armada-rgb apply' "$ROOT/system_files/usr/lib/systemd/system/armada-rgb.service"
grep -Fq 'systemctl enable armada-rgb.service' "$ROOT/build_files/40-vendor-system-files.sh"

printf 'Armada Control RGB tests passed\n'
