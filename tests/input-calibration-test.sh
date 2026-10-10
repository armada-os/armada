#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 -B - "$ROOT" "$WORK" <<'PYEOF'
import importlib.machinery
import importlib.util
import json
from types import SimpleNamespace
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
mangmi_params = parameter_dir("mangmi")
calibration.CALIBRATION_BACKENDS = {
    "mangmi": mangmi_params,
    "rsinput": rsinput_params,
    "retroid": retroid_params,
}

rsinput_event = {"name": "RSInput Gamepad", "phys": "rsinput-gamepad/input0"}
retroid_event = {"name": "Retroid Pocket Gamepad", "phys": "retroid-pocket-gamepad/input0"}
mangmi_event = {"name": "MANGMI Pocket Max Joypad", "phys": "mangmi-pocket-max/input0"}
tester_event = {"name": "AYANEO Controller", "phys": "usb-controller/input0"}
virtual_event = {"name": "Microsoft X-Box 360 pad 0", "phys": ""}

assert calibration.event_backend(rsinput_event) == "rsinput"
assert calibration.event_backend(retroid_event) == "retroid"
assert calibration.event_backend(mangmi_event) == "mangmi"
assert calibration.event_backend(tester_event) is None
assert calibration.calibration_backend(rsinput_event) == "rsinput"
assert calibration.calibration_backend(retroid_event) == "retroid"
assert calibration.calibration_backend(mangmi_event) == "mangmi"
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
mangmi_controls = calibration.read_backend_controls(0, "mangmi")
assert default_controls["left_trigger"]["value"] == 111
assert default_controls["right_trigger"]["value"] == 222
assert retroid_controls["left_trigger"]["value"] == 333
assert retroid_controls["right_trigger"]["value"] == 444
assert mangmi_controls["left_trigger"]["value"] == 333
assert mangmi_controls["right_trigger"]["value"] == 444

values[2] = (0, 0, 0)
values[5] = (0, 0, 0)
fallback_controls = calibration.read_backend_controls(0)
assert fallback_controls["left_trigger"]["value"] == 555
assert fallback_controls["right_trigger"]["value"] == 666

calls = []
calibration.call = lambda action, **payload: calls.append((action, payload)) or {}


def last_write():
    return json.loads([payload for action, payload in calls if action == "write_config"][-1]["text"])


calibration.calibration_event = lambda: retroid_event
calibration.calibration_status = lambda: {"ok": True}
calibration.reset_calibration_params()
reset_payload = last_write()
assert reset_payload["backend"] == "retroid"
assert reset_payload["axis_leftx_min"] == -1408
assert reset_payload["axis_leftx_max"] == 1408
assert reset_payload["axis_leftx_deadzone"] == 0
assert reset_payload["trigger_left_max"] == 1552

calibration.calibration_event = lambda: mangmi_event
calibration.reset_calibration_params()
reset_payload = last_write()
assert reset_payload["trigger_left_max"] == 1910
assert reset_payload["trigger_right_max"] == 1758
assert reset_payload["axis_leftx_max"] == 1408
assert reset_payload["axis_leftx_deadzone"] == 70

calibration.calibration_event = lambda: rsinput_event
calibration.reset_calibration_params()
reset_payload = last_write()
assert reset_payload["axis_leftx_max"] == 1408
assert reset_payload["axis_leftx_deadzone"] == 0
assert reset_payload["trigger_left_deadzone"] == 0

device_tree = {"axis-range": 1024, "trigger-left-deadzone": 100}
calibration.device_tree_u32 = lambda _event, name: device_tree.get(name)
calibration.reset_calibration_params()
reset_payload = last_write()
assert reset_payload["axis_righty_min"] == -1024
assert reset_payload["axis_righty_max"] == 1024
assert reset_payload["axis_righty_deadzone"] == 0
assert reset_payload["trigger_left_deadzone"] == 100
assert reset_payload["trigger_right_deadzone"] == 0
calibration.calibration_event = lambda: retroid_event

state = {
    "supported": True,
    "canApply": True,
    "backend": "retroid",
    "controls": {},
}
capture = {
    "left_x": {"min": -1200, "max": 1250},
    "left_y": {"min": -1210, "max": 1230},
    "right_x": {"min": -1220, "max": 1240},
    "right_y": {"min": -1230, "max": 1260},
    "left_trigger": {"min": 0, "max": 1500},
    "right_trigger": {"min": 0, "max": 1510},
}
calibration.read_controller_state = lambda: dict(state)


def save(captured):
    calibration._recording = SimpleNamespace(capture=lambda: captured)
    return calibration.save_calibration()


save(capture)
save_payload = last_write()
assert save_payload["backend"] == "retroid"
assert save_payload["axis_leftx_min"] == -1140
assert save_payload["axis_leftx_deadzone"] == 57
assert save_payload["axis_leftx_antideadzone"] == 57
assert save_payload["trigger_right_max"] == 1464
assert save_payload["trigger_right_deadzone"] == 45
assert save_payload["trigger_right_antideadzone"] == 45
assert calibration._recording is None
try:
    calibration.save_calibration()
except RuntimeError:
    pass
else:
    raise AssertionError("saved with nothing calibrated")

sticks = {key: capture[key] for key in ("left_x", "left_y", "right_x", "right_y")}
shaped = {"axis_leftx_min": -1200, "axis_leftx_center": 5, "axis_leftx_max": 1200,
          "axis_leftx_deadzone": 84, "axis_leftx_antideadzone": 84}
unmoved = calibration.calibration_from_capture({**capture, "left_x": {"min": -3, "max": 4}}, shaped)
assert {key: unmoved[key] for key in shaped} == shaped
untouched = calibration.calibration_from_capture({"left_y": capture["left_y"]}, shaped)
assert {key: untouched[key] for key in shaped} == shaped
again = calibration.calibration_from_capture({**capture, "left_x": {"min": -1200, "max": 1250}}, shaped)
assert again["axis_leftx_max"] == 1140
assert again["axis_leftx_center"] == 5
assert again["axis_leftx_deadzone"] == 84
assert again["axis_leftx_antideadzone"] == 84
threshold = calibration.calibration_from_capture({**capture, "left_x": {"min": -256, "max": 256}}, {})
assert threshold["axis_leftx_max"] == 243

offset = calibration.calibration_from_capture(
    {**capture, "left_x": {"min": -960, "max": 1140, "rest_min": 20, "rest_max": 60}}, {"axis_leftx_deadzone": 84}
)
assert offset["axis_leftx_center"] == -40
assert offset["axis_leftx_max"] == 950
assert offset["axis_leftx_min"] == -950
assert offset["axis_leftx_deadzone"] == 47
assert offset["axis_leftx_antideadzone"] == 47
wandering = calibration.calibration_from_capture(
    {**capture, "left_x": {"min": -960, "max": 1140, "rest_min": -60, "rest_max": 100}}, {}
)
assert wandering["axis_leftx_center"] == -20
assert wandering["axis_leftx_max"] == 931
assert wandering["axis_leftx_deadzone"] == 120
masked = calibration.calibration_from_capture(
    {**capture, "left_x": {"min": -1200, "max": 1200, "rest_min": 0, "rest_max": 150}},
    {"axis_leftx_deadzone": 100, "axis_leftx_antideadzone": 100},
)
assert masked["axis_leftx_center"] == -75
assert masked["axis_leftx_deadzone"] == 175
default_deadzone = calibration.calibration_from_capture(capture, {}, 70)
assert default_deadzone["axis_leftx_deadzone"] == 70
assert default_deadzone["axis_leftx_antideadzone"] == 70
assert calibration.stick_defaults(mangmi_event, "mangmi") == (1408, 70)
flipped = calibration.calibration_from_capture(
    {**capture, "left_x": {"min": -960, "max": 1140, "rest_min": 40, "rest_max": 40}},
    {"axis_leftx_center": 5}, 0, {"axis_leftx"},
)
assert flipped["axis_leftx_center"] == 45
assert flipped["axis_leftx_max"] == 950
assert flipped["axis_lefty_center"] == 0
assert calibration.inverted_axes(retroid_event, "retroid") == frozenset()
assert calibration.inverted_axes(rsinput_event, "rsinput") == frozenset()


def controls(lx=0, ly=0, rx=0, ry=0, lt=0, rt=0, reach=1408, fuzz=0):
    axis = lambda value: {"value": value, "min": -reach, "max": reach, "fuzz": fuzz}
    trigger = lambda value: {"value": value, "min": 0, "max": 1552, "fuzz": 30}
    return {"left_x": axis(lx), "left_y": axis(ly), "right_x": axis(rx), "right_y": axis(ry),
            "left_trigger": trigger(lt), "right_trigger": trigger(rt)}


def hold(recording, clock, seconds, **kwargs):
    for _ in range(round(seconds / 0.05)):
        clock[0] += 0.05
        recording.sample(controls(**kwargs), clock[0])


recording = calibration.Recording({})
clock = [0.0]
hold(recording, clock, 0.05, lx=-47, ly=42)
assert recording.rests["left_stick"] == [(-47, 42)]
hold(recording, clock, 0.6, lx=-47, ly=42)
assert not recording.progress()["right_stick"]["left"]
hold(recording, clock, 0.3, lx=-1248, ly=131)
filling = recording.progress()["left_stick"]["left"]
assert 0 < filling < 1, filling
hold(recording, clock, 0.4, lx=-1248, ly=131)
assert recording.progress()["left_stick"]["left"] == 1
assert not recording.progress()["ready"]
hold(recording, clock, 0.6, lx=-62, ly=49)
for step in range(20):
    hold(recording, clock, 0.05, lx=1100 + step * 5, ly=-300 + step * 30)
assert recording.progress()["left_stick"]["right"] < 1
hold(recording, clock, 0.6, lx=1052, ly=-70)
hold(recording, clock, 0.6, lx=-21, ly=98)
assert recording.progress()["ready"]
hold(recording, clock, 0.6, lx=-48, ly=-1226)
hold(recording, clock, 0.6, lx=-129, ly=1168)
hold(recording, clock, 0.6, lx=-48, ly=57)
hold(recording, clock, 0.6, lx=-800, ly=60)
hold(recording, clock, 0.6, lx=-48, ly=57)
assert recording.capture()["left_x"]["min"] == -1248
hold(recording, clock, 0.6, lx=-1260, ly=60)
hold(recording, clock, 0.6, lx=0, ly=0, lt=1500)
held = recording.capture()
assert held["left_x"] == {"min": -1260, "max": 1052, "rest_min": -62, "rest_max": 0}, held
assert held["left_y"] == {"min": -1226, "max": 1168, "rest_min": 0, "rest_max": 98}, held
assert "right_x" not in held and "right_trigger" not in held
assert held["left_trigger"]["max"] == 1500 and held["left_trigger"]["min"] == 0
assert recording.progress()["left_trigger"] == 1
assert recording.progress()["right_trigger"] == 0
measured = calibration.calibration_from_capture(held, {})
assert measured["axis_leftx_center"] == 31
assert measured["axis_leftx_max"] == (1052 + 31) * 95 // 100
assert measured["axis_leftx_deadzone"] == 51
assert "axis_rightx_max" not in measured

shaped_recording = calibration.Recording({"axis_leftx_antideadzone": 70, "axis_lefty_antideadzone": 70})
clock = [0.0]
hold(shaped_recording, clock, 0.6, reach=1070)
hold(shaped_recording, clock, 0.6, lx=-1060, reach=1070)
hold(shaped_recording, clock, 0.6, lx=6, reach=1070, fuzz=16)
hold(shaped_recording, clock, 0.6, lx=1080, reach=1070)
assert shaped_recording.capture()["left_x"] == {"min": -1130, "max": 1150, "rest_min": 0, "rest_max": 0}

resting = calibration.calibration_from_capture(
    {**sticks, "left_trigger": {"min": 60, "max": 1100}, "right_trigger": {"min": 0, "max": 40}},
    {"trigger_right_max": 1400, "trigger_right_deadzone": 50, "trigger_right_antideadzone": 50},
)
assert resting["trigger_left_max"] == 1067
assert resting["trigger_left_deadzone"] == 60 + 31
assert resting["trigger_left_antideadzone"] == 60 + 31
assert resting["trigger_right_max"] == 1400
assert resting["trigger_right_deadzone"] == 50
assert resting["trigger_right_antideadzone"] == 50

recalibrated = calibration.calibration_from_capture(
    {**sticks, "left_trigger": {"min": 0, "max": 1009}, "right_trigger": {"min": 20, "max": 1009}},
    {
        "trigger_left_max": 1100,
        "trigger_left_deadzone": 91,
        "trigger_left_antideadzone": 91,
        "trigger_right_max": 1100,
        "trigger_right_deadzone": 91,
        "trigger_right_antideadzone": 91,
    },
)
assert recalibrated["trigger_left_max"] == 1067
assert recalibrated["trigger_left_deadzone"] == 91
assert recalibrated["trigger_left_antideadzone"] == 91
assert recalibrated["trigger_right_max"] == 1067
assert recalibrated["trigger_right_deadzone"] == 111 + 29


def defuzz(value, old, fuzz):
    # Mirrors input_defuzz_abs_event() in drivers/input/input.c.
    if fuzz:
        if old - fuzz // 2 < value < old + fuzz // 2:
            return old
        if old - fuzz < value < old + fuzz:
            return (old * 3 + value) // 4
        if old - 2 * fuzz < value < old + 2 * fuzz:
            return (old + value) // 2
    return value


def pull_trigger(current, reference, rest_raw, full_raw, fuzz):
    deadzone = current.get("trigger_left_deadzone", 0)
    antideadzone = current.get("trigger_left_antideadzone", 0)
    sweep = list(range(rest_raw, full_raw, -25)) + [full_raw] * 20
    sweep += list(range(full_raw, rest_raw, 25)) + [rest_raw] * 20
    reported = 0
    seen = []
    for recording in (False, True):
        for raw in sweep:
            value = reference - raw
            value = 0 if value < deadzone else max(value - antideadzone, 0)
            reported = defuzz(value, reported, fuzz)
            if recording:
                seen.append(reported)
    return {"min": min(seen), "max": max(seen), "fuzz": fuzz}


fuzzy = {}
deadzones = []
for _ in range(5):
    pulled = pull_trigger(fuzzy, 1910, 1850, 800, 16)
    fuzzy = calibration.calibration_from_capture({**sticks, "left_trigger": pulled}, fuzzy)
    deadzones.append(fuzzy["trigger_left_deadzone"])
assert 0 < pulled["min"] <= 16
assert len(set(deadzones)) == 1, deadzones
assert abs(fuzzy["trigger_left_max"] - 1076) <= 8

save(capture)
assert last_write()["version"] == 2
assert calls[-1][0] == "write_config"
calibration.begin_calibration_intercept = lambda: True
calibration.end_calibration_intercept = lambda: True
calibration.open_session_device = lambda: None
record = calibration.call


def failing_call(action, **payload):
    if action == "reload_input_ranges":
        raise RuntimeError("restart failed")
    return record(action, **payload)


calibration.begin_session("modal")
save(capture)
calibration.call = failing_call
try:
    calibration.end_session("modal")
except RuntimeError:
    pass
else:
    raise AssertionError("failed range reload was reported as success")
calibration.call = record
# A failed Close must retry without needing to open a new modal.
calibration.end_session("modal")
assert calls[-1][0] == "reload_input_ranges"
reloads = len(calls)
calibration.begin_session("modal")
calibration.end_session("modal")
assert len(calls) == reloads
saves = len(calls)
(retroid_params / "trigger_left_max").unlink()
try:
    save(capture)
except RuntimeError:
    pass
else:
    raise AssertionError("save with an unreadable current parameter was accepted")
assert len(calls) == saves
(retroid_params / "trigger_left_max").write_text("0", encoding="utf-8")

calibration.calibration_event = lambda: tester_event
try:
    calibration.reset_calibration_params()
except RuntimeError:
    pass
else:
    raise AssertionError("tester-only controller reset was accepted")

calibration.read_controller_state = lambda: {
    "supported": True,
    "canApply": False,
    "backend": "tester",
    "controls": {},
}
try:
    save(capture)
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
    "mangmi": mangmi_params,
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


def shaped_trigger(raw, reference, params):
    value = reference - raw
    if value < params["trigger_left_deadzone"]:
        return 0
    return value - params["trigger_left_antideadzone"]


# Rest at raw 1352, full pull at raw 452.
legacy = {"backend": "retroid", "trigger_left_max": 900, "trigger_left_deadzone": 27,
          "trigger_left_antideadzone": 0}
migrated = apply_calibration.migrate(legacy, "retroid")
assert migrated["trigger_left_max"] - migrated["trigger_left_antideadzone"] == 900
for raw in range(0, 2000, 7):
    assert shaped_trigger(raw, 1552, migrated) == shaped_trigger(raw, legacy["trigger_left_max"], legacy)
assert shaped_trigger(1352, 1552, migrated) == 0
assert shaped_trigger(452, 1552, migrated) == 448

assert apply_calibration.migrate({**legacy, "version": 2}, "retroid")["trigger_left_max"] == 900
assert apply_calibration.migrate({**legacy, "backend": "rsinput"}, "rsinput")["trigger_left_max"] == 900
legacy_mangmi = apply_calibration.migrate(
    {"trigger_right_max": 1552, "trigger_right_deadzone": 0, "trigger_right_antideadzone": 0}, "mangmi"
)
assert legacy_mangmi["trigger_right_max"] == 1758
assert legacy_mangmi["trigger_right_deadzone"] == 206
assert legacy_mangmi["trigger_right_antideadzone"] == 206

apply_calibration.CONFIG.write_text(json.dumps(legacy), encoding="utf-8")
apply_calibration.main()
assert (retroid_params / "trigger_left_max").read_text(encoding="utf-8") == "1552"
assert (retroid_params / "trigger_left_deadzone").read_text(encoding="utf-8") == "679"
assert (retroid_params / "trigger_left_antideadzone").read_text(encoding="utf-8") == "652"

control = load_script(
    root / "system_files/usr/libexec/armada/armada-control",
    "armada_control_daemon_test",
)
control.CALIBRATION_BACKENDS = {
    "mangmi": mangmi_params,
    "rsinput": rsinput_params,
    "retroid": retroid_params,
}
control.CONFIG_PATHS["calibration"] = work / "daemon-calibration.json"
commands = []
control.run = lambda command, timeout=20: commands.append(command)
control.action_write_config(
    {
        "name": "calibration",
        "text": '{"backend":"retroid","axis_righty_center":29}\n',
    }
)
assert (retroid_params / "axis_righty_center").read_text(encoding="utf-8") == "29"
assert json.loads(control.CONFIG_PATHS["calibration"].read_text())["backend"] == "retroid"
assert commands == []
control.unit_active = lambda unit: False
control.action_reload_input_ranges({})
assert commands == []
control.unit_active = lambda unit: True
control.action_reload_input_ranges({})
assert commands == [
    ["/usr/bin/systemctl", "restart", "inputplumber.service"],
    ["/usr/bin/systemctl", "start", "armada-controller-type.service"],
]


def failing_run(command, timeout=20):
    raise RuntimeError("unit failed")


restart = control.run
control.run = failing_run
try:
    control.action_reload_input_ranges({})
except RuntimeError:
    pass
else:
    raise AssertionError("failed controller restart was reported as success")
control.run = restart

try:
    control.action_write_config(
        {"name": "calibration", "text": '{"backend":"unknown"}\n'}
    )
except ValueError:
    pass
else:
    raise AssertionError("unknown calibration backend was accepted")
PYEOF

python3 -B "$ROOT/tests/input-calibration-policy-test.py"
python3 -B "$ROOT/tests/mcu-calibration-test.py"

echo "Input calibration tests passed"
