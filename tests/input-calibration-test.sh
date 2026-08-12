#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 -B - "$ROOT" "$WORK" <<'PYEOF'
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import struct
import sys

root = Path(sys.argv[1])
work = Path(sys.argv[2])
sys.path.insert(0, str(root / "decky/armada-control/py_modules"))
sys.path.insert(0, str(root / "system_files/usr/lib/armada"))

from armada_control import calibration


def parameter_dir(name):
    path = work / name
    path.mkdir()
    for param in calibration.CALIBRATION_PARAMS:
        (path / param).write_text("0", encoding="utf-8")
    (path / "update_params").write_text("0", encoding="utf-8")
    return path


rsinput_params = parameter_dir("rsinput")
retroid_params = parameter_dir("retroid")
calibration.CALIBRATION_BACKENDS = {
    "rsinput": rsinput_params,
    "retroid": retroid_params,
}

rsinput_event = {"name": "RSInput Gamepad", "phys": "rsinput-gamepad/input0"}
retroid_event = {"name": "Retroid Pocket Gamepad", "phys": "retroid-pocket-gamepad/input0"}
tester_event = {"name": "AYANEO Controller", "phys": "usb-controller/input0"}
virtual_event = {"name": "Microsoft X-Box 360 pad 0", "phys": ""}

assert calibration.event_backend(rsinput_event) == "rsinput"
assert calibration.event_backend(retroid_event) == "retroid"
assert calibration.event_backend(tester_event) is None
assert calibration.calibration_backend(rsinput_event) == "rsinput"
assert calibration.calibration_backend(retroid_event) == "retroid"
assert calibration.calibration_backend(tester_event) is None

calibration.inputplumber_source_events = lambda: []
calibration.input_events = lambda: [virtual_event, retroid_event]
assert calibration.calibration_event() == retroid_event

values = {
    0: (10, -1408, 1408),
    1: (20, -1408, 1408),
    2: (111, 0, 1552),
    3: (30, -1408, 1408),
    4: (40, -1408, 1408),
    5: (222, 0, 1552),
    9: (666, 0, 1023),
    10: (555, 0, 1023),
    20: (333, 0, 1552),
    21: (444, 0, 1552),
}


def fake_ioctl(_fd, request, _buffer):
    code = request - 0x80184540
    if code not in values:
        raise OSError(code)
    value, minimum, maximum = values[code]
    return struct.pack("iiiiii", value, minimum, maximum, 0, 0, 0)


calibration.fcntl.ioctl = fake_ioctl
default_controls = calibration.read_backend_controls(0)
retroid_controls = calibration.read_backend_controls(0, "retroid")
assert default_controls["left_trigger"]["value"] == 111
assert default_controls["right_trigger"]["value"] == 222
assert retroid_controls["left_trigger"]["value"] == 333
assert retroid_controls["right_trigger"]["value"] == 444

values[2] = (0, 0, 0)
values[5] = (0, 0, 0)
fallback_controls = calibration.read_backend_controls(0)
assert fallback_controls["left_trigger"]["value"] == 555
assert fallback_controls["right_trigger"]["value"] == 666

calls = []
calibration.call = lambda action, **payload: calls.append((action, payload)) or {}
calibration.calibration_event = lambda: retroid_event
calibration.calibration_status = lambda: {"ok": True}
calibration.reset_calibration_params()
reset_payload = json.loads(calls[-1][1]["text"])
assert reset_payload["backend"] == "retroid"
assert reset_payload["axis_leftx_min"] == -1408
assert reset_payload["axis_leftx_max"] == 1408
assert reset_payload["axis_leftx_deadzone"] == 0

state = {
    "supported": True,
    "canApply": True,
    "backend": "retroid",
    "controls": {},
}
capture = {
    "left_x": {"center": 0, "min": -1200, "max": 1250},
    "left_y": {"center": 0, "min": -1210, "max": 1230},
    "right_x": {"center": 0, "min": -1220, "max": 1240},
    "right_y": {"center": 0, "min": -1230, "max": 1260},
    "left_trigger": {"center": 0, "min": 0, "max": 1500},
    "right_trigger": {"center": 0, "min": 0, "max": 1510},
}
calibration.controller_state = lambda: state
calibration.save_calibration(capture)
save_payload = json.loads(calls[-1][1]["text"])
assert save_payload["backend"] == "retroid"
assert save_payload["axis_leftx_min"] == -1200
assert save_payload["trigger_right_max"] == 1510

calibration.calibration_event = lambda: tester_event
try:
    calibration.reset_calibration_params()
except RuntimeError:
    pass
else:
    raise AssertionError("tester-only controller reset was accepted")

calibration.controller_state = lambda: {
    "supported": True,
    "canApply": False,
    "backend": "tester",
    "controls": {},
}
try:
    calibration.save_calibration(capture)
except RuntimeError:
    pass
else:
    raise AssertionError("tester-only controller save was accepted")


def load_script(path, name):
    spec = importlib.util.spec_from_loader(
        name,
        importlib.machinery.SourceFileLoader(name, str(path)),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


apply_calibration = load_script(
    root / "system_files/usr/libexec/armada/apply-input-calibration",
    "apply_input_calibration_test",
)
apply_calibration.CONFIG = work / "input-calibration.json"
apply_calibration.CALIBRATION_BACKENDS = {
    "rsinput": rsinput_params,
    "retroid": retroid_params,
}

apply_calibration.CONFIG.write_text('{"axis_leftx_center": 17}\n', encoding="utf-8")
apply_calibration.main()
assert (rsinput_params / "axis_leftx_center").read_text(encoding="utf-8") == "17"
assert (retroid_params / "axis_leftx_center").read_text(encoding="utf-8") == "0"

apply_calibration.CONFIG.write_text(
    '{"backend":"retroid","axis_leftx_center":23}\n', encoding="utf-8"
)
apply_calibration.main()
assert (retroid_params / "axis_leftx_center").read_text(encoding="utf-8") == "23"
assert (retroid_params / "update_params").read_text(encoding="utf-8") == "1"

control = load_script(
    root / "system_files/usr/libexec/armada/armada-control",
    "armada_control_daemon_test",
)
control.CALIBRATION_BACKENDS = {
    "rsinput": rsinput_params,
    "retroid": retroid_params,
}
control.CONFIG_PATHS["calibration"] = work / "daemon-calibration.json"
control.action_write_config(
    {
        "name": "calibration",
        "text": '{"backend":"retroid","axis_righty_center":29}\n',
    }
)
assert (retroid_params / "axis_righty_center").read_text(encoding="utf-8") == "29"
assert json.loads(control.CONFIG_PATHS["calibration"].read_text())["backend"] == "retroid"

try:
    control.action_write_config(
        {"name": "calibration", "text": '{"backend":"unknown"}\n'}
    )
except ValueError:
    pass
else:
    raise AssertionError("unknown calibration backend was accepted")
PYEOF

echo "Input calibration tests passed"
