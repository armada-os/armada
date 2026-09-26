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
rgb_environments = []
supported = False


def check_output(command, **kwargs):
    commands.append(command)
    if command and command[0] == control.RGB_TOOL:
        rgb_environments.append(kwargs.get("env", {}))
    if command[-1] == "get":
        return '{"version":1,"enabled":false,"linkBrightness":false,"brightness":25,"maxBrightness":25,"color":"FFFFFF","saturation":100}'
    return '{"version":1,"enabled":true,"linkBrightness":true,"brightness":40,"maxBrightness":60,"color":"A1B2C3","saturation":50}'


def run(command, **kwargs):
    assert command == [control.RGB_TOOL, "supported"]
    return control.subprocess.CompletedProcess(command, 0 if supported else 1)


control.subprocess.check_output = check_output
control.subprocess.run = run
# Unsupported devices return no RGB state and do not invoke the RGB tool.
assert control.action_get_rgb({}) is None
assert commands == []

supported = True
# Supported devices return the saved RGB configuration through the get command.
state = control.action_get_rgb({})
assert state["color"] == "FFFFFF"
assert commands.pop() == [control.RGB_TOOL, "get"]

control.device_env = lambda: {"ARMADA_PRIMARY_BACKLIGHT": "panel0"}
# A complete payload forwards enabled, smart brightness, saturation, and brightness settings.
state = control.action_set_rgb({
    "enabled": True,
    "linkBrightness": True,
    "color": "a1b2c3",
    "saturation": 50,
    "maxBrightness": 60,
    "brightness": 40,
})
assert state["color"] == "A1B2C3"
assert rgb_environments[-1]["ARMADA_PRIMARY_BACKLIGHT"] == "panel0"
assert commands.pop() == [
    control.RGB_TOOL,
    "set",
    "--enabled",
    "true",
    "--link-brightness",
    "true",
    "--max-brightness",
    "60",
    "--color",
    "a1b2c3",
    "--saturation",
    "50",
    "--brightness",
    "40",
]

# Smart-brightness fields are independently optional so omitted values remain
# preserved by armada-rgb's saved configuration.
# Supplying only linkBrightness forwards that flag without inventing maxBrightness.
state = control.action_set_rgb({
    "enabled": True,
    "linkBrightness": True,
    "color": "a1b2c3",
    "brightness": 40,
})
assert state["color"] == "A1B2C3"
assert commands.pop() == [
    control.RGB_TOOL,
    "set",
    "--enabled",
    "true",
    "--link-brightness",
    "true",
    "--color",
    "a1b2c3",
    "--brightness",
    "40",
]

# Supplying only maxBrightness forwards that ceiling while preserving other saved settings.
state = control.action_set_rgb({
    "enabled": True,
    "color": "a1b2c3",
    "saturation": 75,
    "maxBrightness": 35,
    "brightness": 40,
})
assert state["color"] == "A1B2C3"
assert commands.pop() == [
    control.RGB_TOOL,
    "set",
    "--enabled",
    "true",
    "--max-brightness",
    "35",
    "--color",
    "a1b2c3",
    "--saturation",
    "75",
    "--brightness",
    "40",
]

# Legacy callers that omit smart brightness and saturation preserve the saved values.
# The legacy payload forwards only the fields it actually supplied.
state = control.action_set_rgb({"enabled": True, "color": "a1b2c3", "brightness": 40})
assert state["color"] == "A1B2C3"
assert commands.pop() == [
    control.RGB_TOOL,
    "set",
    "--enabled",
    "true",
    "--color",
    "a1b2c3",
    "--brightness",
    "40",
]

# Disabling RGB with a full settings payload still persists the disabled state.
# A complete disabled payload uses set so the configuration fields are retained.
state = control.action_set_rgb({
    "enabled": False,
    "linkBrightness": True,
    "color": "a1b2c3",
    "saturation": 50,
    "maxBrightness": 60,
    "brightness": 40,
})
assert state["color"] == "A1B2C3"
assert commands.pop() == [
    control.RGB_TOOL,
    "set",
    "--enabled",
    "false",
    "--link-brightness",
    "true",
    "--max-brightness",
    "60",
    "--color",
    "a1b2c3",
    "--saturation",
    "50",
    "--brightness",
    "40",
]

# The legacy enabled=false payload still maps to the off command.
control.action_set_rgb({"enabled": False})
assert commands.pop() == [control.RGB_TOOL, "off"]

# Invalid smart-brightness, color, saturation, and brightness values are rejected.
invalid_requests = (
    {"enabled": True, "linkBrightness": "true", "color": "FFFFFF", "brightness": 40},
    {"enabled": True, "linkBrightness": 1, "color": "FFFFFF", "brightness": 40},
    {"enabled": True, "color": "FFFFFF", "maxBrightness": -1, "brightness": 40},
    {"enabled": True, "color": "FFFFFF", "maxBrightness": 101, "brightness": 40},
    {"enabled": True, "color": "FFFFFF", "maxBrightness": True, "brightness": 40},
    {"enabled": True, "color": "12345", "brightness": 40},
    {"enabled": True, "color": "FFFFFF", "brightness": 101},
    {"enabled": True, "color": "FFFFFF", "saturation": 101, "brightness": 40},
)
for request in invalid_requests:
    try:
        control.action_set_rgb(request)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid RGB state was accepted")

sys.path.insert(0, str(root / "decky/armada-control/py_modules"))
from armada_control import rgb

# The Python RGB wrapper reports unsupported devices when its privileged call fails.
rgb.call = lambda action, **payload: None
assert not rgb.rgb_supported()

calls = []
# The Python RGB wrapper forwards the complete settings payload unchanged.
rgb.call = lambda action, **payload: calls.append((action, payload)) or {}
assert rgb.rgb_supported()
assert calls.pop() == ("get_rgb", {})
assert rgb.get_rgb() == {}
assert calls.pop() == ("get_rgb", {})
rgb.set_rgb(True, False, "112233", 75, 100, 50)
assert calls.pop() == (
    "set_rgb",
    {
        "enabled": True,
        "linkBrightness": False,
        "color": "112233",
        "saturation": 75,
        "maxBrightness": 100,
        "brightness": 50,
    },
)

# Device files do not contain RGB environment overrides.
paths = list((root / "system_files/usr/lib/armada/devices").rglob("*"))
paths.append(root / "system_files/usr/libexec/armada/device-env")
for path in paths:
    if path.is_file():
        assert "ARMADA_RGB_" not in path.read_text(), path
PYEOF

grep -Fq 'ConditionPathExists=/etc/armada/rgb.json' "$ROOT/system_files/usr/lib/systemd/system/armada-rgb.service"
grep -Fq 'ExecStart=/usr/libexec/armada/armada-rgb-env apply' "$ROOT/system_files/usr/lib/systemd/system/armada-rgb.service"
grep -Fq 'systemctl enable armada-rgb.service' "$ROOT/build_files/40-vendor-system-files.sh"

grep -Fq 'ConditionPathExists=/etc/armada/rgb.json' "$ROOT/system_files/usr/lib/systemd/system/armada-rgb-brightness-watch.service"
grep -Fq 'Wants=armada-rgb.service' "$ROOT/system_files/usr/lib/systemd/system/armada-rgb-brightness-watch.service"
! grep -Fq 'Requires=armada-rgb.service' "$ROOT/system_files/usr/lib/systemd/system/armada-rgb-brightness-watch.service"
grep -Fq 'ExecStart=/usr/libexec/armada/armada-rgb-env watch' "$ROOT/system_files/usr/lib/systemd/system/armada-rgb-brightness-watch.service"
grep -Fq 'PathExists=/etc/armada/rgb.json' "$ROOT/system_files/usr/lib/systemd/system/armada-rgb-brightness-watch.path"
grep -Fq 'PathChanged=/etc/armada/rgb.json' "$ROOT/system_files/usr/lib/systemd/system/armada-rgb-brightness-watch.path"
grep -Fq 'Unit=armada-rgb-brightness-watch.service' "$ROOT/system_files/usr/lib/systemd/system/armada-rgb-brightness-watch.path"
grep -Fq 'systemctl enable armada-rgb-brightness-watch.path' "$ROOT/build_files/40-vendor-system-files.sh"
printf 'Armada Control RGB tests passed\n'
