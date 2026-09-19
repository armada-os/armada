#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 -B - "$ROOT" "$WORK" <<'PYEOF'
import importlib.machinery
import importlib.util
import copy
import json
import math
from pathlib import Path
import struct
import sys

root = Path(sys.argv[1])
work = Path(sys.argv[2])
sys.path.insert(0, str(root / "decky/armada-control/py_modules"))
sys.path.insert(0, str(root / "system_files/usr/lib/armada"))

from armada_control import calibration
import rsinput_calibration


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

original_read_text = calibration.read_text
for compatible, profile_name in (
    ("retroidpocket,rpnova", "rpnova"),
    ("ayn,thor", "thor"),
):
    calibration.read_text = lambda _path, compatible=compatible: compatible
    profile = calibration.calibration_profile("rsinput")
    assert profile is calibration.CALIBRATION_PROFILES[profile_name]
    assert profile["calibrate_axes"] is False
    assert profile["trigger_apply"] is False
calibration.read_text = original_read_text

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

assert rsinput_calibration.COMMAND.size == 64
assert rsinput_calibration.SAMPLE.size == 48
version, command, length, payload = rsinput_calibration.COMMAND.unpack(
    rsinput_calibration.mode_record("left", True)
)
assert (version, command, length) == (1, 0xA0, 1)
assert payload == b"\1" + b"\0" * 57
assert set(rsinput_calibration.MODE_COMMANDS.values()) == {0xA0, 0xA1}
sample = rsinput_calibration.SAMPLE.pack(1, 2, 255, 26, b"\0" * 26, 7, 1, 0)
decoded = rsinput_calibration.decode_sample(sample, "left")
assert decoded["generation"] == 2 and decoded["dropped"] == 7

center = rsinput_calibration.CenterTracker("left")
physical_directions = {
    "left": (-800, 0), "right": (800, 0), "up": (0, -800), "down": (0, 800),
    "up-left": (-600, -600), "up-right": (600, -600),
    "down-left": (-600, 600), "down-right": (600, 600),
}
for index, name in enumerate(rsinput_calibration.CENTER_DIRECTIONS):
    physical_x, physical_y = physical_directions[name]
    center.observe({"logicalX": -physical_x, "logicalY": -physical_y,
                    "rawX": 32600 + index, "rawY": 32500 + index})
    assert center.progress()["pendingDirection"] == name
    for _ in range(rsinput_calibration.CENTER_STABLE_SAMPLE_GOAL):
        center.observe({"logicalX": 0, "logicalY": 0,
                        "rawX": 32600 + index, "rawY": 32500 + index})
assert center.complete
assert center.progress()["directionCount"] == 8
assert center.result()["centerWords"] == [32603, 32503]
assert center.result()["returns"] == [[32600 + index, 32500 + index] for index in range(8)]

def sweep(tracker, radius_x=1000, radius_y=1000, short_positive_y=False):
    for degree in range(0, 1801):
        angle = math.radians(degree % 360)
        logical_y_scale = 908 if short_positive_y and math.sin(angle) > 0 else 1024
        tracker.observe({
            "timestampNs": degree * 4_000_000, "generation": degree + 1,
            "sequence": degree % 255 + 1, "length": 26, "dropped": 0,
            "logicalX": round(math.cos(angle) * 1024),
            "logicalY": round(math.sin(angle) * logical_y_scale),
            "rawX": 32768 + round(math.cos(angle) * radius_x),
            "rawY": 32768 + round(math.sin(angle) * radius_y), "rawZ": 40000,
        })


range_tracker = rsinput_calibration.RangeTracker("right", (32768, 32768))
sweep(range_tracker)
assert range_tracker.complete
assert range_tracker.progress()["coveredHeadings"] == 8
assert len(range_tracker.result()["rawSpaceCandidate"]["tableWords"]) == 29
assert range_tracker.progress()["coveredSectors"] == 72
result = range_tracker.result()
observed = {(r["rawX"], r["rawY"], r["rawZ"]) for r in range_tracker.trace}
assert all(tuple(triple) in observed for triple in result["rawSpaceCandidate"]["triples"])
assert result["mountingRotationDegrees"] == 180

# Logical-axis distortion must not affect raw-space selection.
distorted = rsinput_calibration.RangeTracker("left", (32768, 32768))
sweep(distorted, radius_x=800, radius_y=1250, short_positive_y=True)
distorted_result = distorted.result()
assert distorted_result["quality"]["outerRadiusRatio"] < rsinput_calibration.MAX_RADIAL_RATIO
assert distorted_result["rawSpaceCandidate"]["available"]
assert distorted_result["slotRawAngles"] == [90, 180, 270, 0, 45, 135, 225, 315]

# Coverage alone is insufficient without firm gate contact.
weak = rsinput_calibration.RangeTracker("left", (32768, 32768))
sweep(weak, radius_x=400, radius_y=400)
assert weak.complete and weak.progress()["coveredSectors"] == 72
try:
    weak.result()
except RuntimeError as error:
    assert "weak outer-gate contact" in str(error)
else:
    raise AssertionError("weak full-coverage sweep was accepted")

malformed = rsinput_calibration.RangeTracker("left", (32768, 32768))
try:
    malformed.observe({"length": 14})
except RuntimeError:
    pass
else:
    raise AssertionError("malformed range report was accepted")

arithmetic = rsinput_calibration.RangeTracker("left", (32768, 32768))
bad = {"timestampNs": 0, "generation": 1, "sequence": 1, "length": 26,
       "dropped": 0, "logicalX": 0, "logicalY": 0, "rawX": 10 ** 400,
       "rawY": 32768, "rawZ": 40000}
try:
    arithmetic.observe(bad)
except RuntimeError as error:
    assert "arithmetic" in str(error)
else:
    raise AssertionError("raw arithmetic overflow was accepted")

# The left stick's 180-degree rotation maps logical +Y to A3 triple 2.
left_range = rsinput_calibration.RangeTracker("left", (32768, 32768))
sweep(left_range)
left_result = left_range.result()
assert left_result["stick"] == "left"
assert left_result["slotRawAngles"] == [90, 180, 270, 0, 45, 135, 225, 315]
selected = left_result["rawSpaceCandidate"]["selectedTraceIndices"]
assert all(left_range.distance(left_range.trace[index]["rawAngle"], target) <= 5
           for index, target in zip(selected, [90, 180, 270, 0, 45, 135, 225, 315]))
assert all(left_result["rawSpaceCandidate"]["triples"][slot] == [left_range.trace[index][key]
           for key in ("rawX", "rawY", "rawZ")] for slot, index in enumerate(selected))
rp6_stock_triples = [
    (0x7F32, 0x848A, 0x951D), (0x7A34, 0x7EAA, 0x946E),
    (0x7FB8, 0x79EE, 0x9468), (0x84DA, 0x7F23, 0x9546),
    (0x834C, 0x8347, 0x954F), (0x7B42, 0x82C2, 0x94B8),
    (0x7C35, 0x7B80, 0x9400), (0x8324, 0x7B77, 0x94BE),
]
assert rsinput_calibration.derived_words(rp6_stock_triples) == (
    0x01CA, 0x0DD9, 0x13F2, 0x24F9, 0x5C7F,
)
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

original_profile = calibration.calibration_profile
calibration.calibration_profile = lambda _backend=None: calibration.CALIBRATION_PROFILES["rp6"]
try:
    rp6_params = calibration.calibration_from_capture(capture, {}, "rsinput")
    assert not any(name.startswith("axis_") for name in rp6_params)
    assert rp6_params["trigger_left_max"] == 1500
    weak_triggers = copy.deepcopy(capture)
    weak_triggers["left_trigger"]["max"] = 1000
    try:
        calibration.calibration_from_capture(weak_triggers, {}, "rsinput")
    except RuntimeError as error:
        assert "left trigger was not fully pressed" in str(error)
    else:
        raise AssertionError("weak RP6 trigger capture was accepted")
    calibration.controller_state = lambda: {"supported": True, "canApply": True,
                                            "backend": "rsinput", "controls": {}}
    try:
        calibration.save_calibration(capture)
    except RuntimeError as error:
        assert "raw trigger support" in str(error)
    else:
        raise AssertionError("RP6 post-clamp trigger calibration was accepted")
finally:
    calibration.calibration_profile = original_profile

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

class FakeCaptureManager:
    def capability(self):
        return {"available": True}

    def begin(self, token, stick, phase):
        return {"token": token, "stick": stick, "phase": phase}

    def status(self, token):
        return {"token": token}

    def end(self, token):
        return token == "test"

    def commit(self, token):
        return {"committed": token == "test"}


control.RSINPUT_CALIBRATION = FakeCaptureManager()
assert control.action_rsinput_calibration_capability({})["available"] is True
assert control.action_rsinput_calibration_begin(
    {"token": "test", "stick": "left", "phase": "center"}
)["phase"] == "center"
assert control.action_rsinput_calibration_status({"token": "test"})["token"] == "test"
assert control.action_rsinput_calibration_end({"token": "test"})["ended"] is True
assert control.action_rsinput_calibration_commit(
    {"token": "test"}
)["committed"] is True

# Commit writes the stock command order with a dwell after each frame.
manager = rsinput_calibration.CaptureManager()
writes = []
original_write = rsinput_calibration.os.write
original_open = rsinput_calibration.os.open
original_close = rsinput_calibration.os.close
original_device_path = rsinput_calibration.device_path
original_sleep = rsinput_calibration.time.sleep
original_journal_root = rsinput_calibration.JOURNAL_ROOT
rsinput_calibration.os.write = lambda _fd, data: writes.append(data) or len(data)
rsinput_calibration.os.open = lambda *_args: 99
rsinput_calibration.os.close = lambda _fd: None
rsinput_calibration.device_path = lambda: "/dev/fake-calibration"
delays = []
rsinput_calibration.time.sleep = delays.append
rsinput_calibration.JOURNAL_ROOT = work
try:
    capability = manager.capability()
    assert capability["available"] is True
    rsinput_calibration.device_path = lambda: None
    capability = manager.capability()
    assert capability["available"] is False
    try:
        manager.begin("test", "left", "center")
    except RuntimeError as error:
        assert "not supported" in str(error)
    else:
        raise AssertionError("unsupported device started MCU calibration")
    rsinput_calibration.device_path = lambda: "/dev/fake-calibration"
    try:
        manager.commit("test")
    except RuntimeError as error:
        assert "all calibration steps" in str(error)
    else:
        raise AssertionError("incomplete manager accepted a commit")
    assert writes == []
    for stick in ("left", "right"):
        manager.completed[("test", stick, "center")] = {
            "centerWords": [32760, 32770],
            "returns": [[32760, 32770]] * 8,
        }
        manager.completed[("test", stick, "range")] = {
            "rawSpaceCandidate": {"tableWords": list(range(29))},
        }
    committed = manager.commit("test")
    assert committed["outcome"] == "all-frames-transmitted"
    assert [rsinput_calibration.COMMAND.unpack(frame)[1] for frame in writes] == [
        0xA0, 0xA2, 0xA3, 0xA0, 0xA1, 0xA5, 0xA6, 0xA0,
    ]
    assert delays == [rsinput_calibration.WRITE_DELAY_SECONDS] * 8
    journal_events = [json.loads(line) for line in Path(committed["journal"]).read_text().splitlines()]
    assert journal_events[0]["interCommandDelaySeconds"] == rsinput_calibration.WRITE_DELAY_SECONDS
    assert journal_events[-1]["outcome"] == "all-frames-transmitted"
finally:
    rsinput_calibration.os.write = original_write
    rsinput_calibration.os.open = original_open
    rsinput_calibration.os.close = original_close
    rsinput_calibration.device_path = original_device_path
    rsinput_calibration.time.sleep = original_sleep
    rsinput_calibration.JOURNAL_ROOT = original_journal_root
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
