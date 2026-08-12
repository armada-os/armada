import copy
import fcntl
import json
import struct
import subprocess
import time
from pathlib import Path

from .privileged import call
from .system import read_text

INPUT_CALIBRATION_CONFIG = Path("/etc/armada/input-calibration.json")
CALIBRATION_BACKENDS = {
    "rsinput": Path("/sys/module/rsinput/parameters"),
    "retroid": Path("/sys/module/retroid/parameters"),
}
INPUTPLUMBER_INTERCEPT = Path("/usr/libexec/armada/inputplumber-intercept")
INPUTPLUMBER_SERVICE = "org.shadowblip.InputPlumber"
INPUTPLUMBER_COMPOSITE_IFACE = "org.shadowblip.Input.CompositeDevice"
ABS_CODES = {
    "left_x": 0,
    "left_y": 1,
    "right_x": 3,
    "right_y": 4,
}
TRIGGER_CODES = {
    "default": {"left_trigger": (2, 10), "right_trigger": (5, 9)},
    "retroid": {"left_trigger": (20,), "right_trigger": (21,)},
}
CALIBRATION_PARAMS = (
    "axis_leftx_min",
    "axis_leftx_center",
    "axis_leftx_max",
    "axis_leftx_deadzone",
    "axis_leftx_antideadzone",
    "axis_lefty_min",
    "axis_lefty_center",
    "axis_lefty_max",
    "axis_lefty_deadzone",
    "axis_lefty_antideadzone",
    "axis_rightx_min",
    "axis_rightx_center",
    "axis_rightx_max",
    "axis_rightx_deadzone",
    "axis_rightx_antideadzone",
    "axis_righty_min",
    "axis_righty_center",
    "axis_righty_max",
    "axis_righty_deadzone",
    "axis_righty_antideadzone",
    "trigger_left_max",
    "trigger_left_deadzone",
    "trigger_left_antideadzone",
    "trigger_right_max",
    "trigger_right_deadzone",
    "trigger_right_antideadzone",
)
_inputplumber_events_cache = {"time": 0, "events": []}
_calibration_session_token = None
_session_device = None
_session_fd = None


def input_events():
    events = []
    for event in sorted(Path("/sys/class/input").glob("event*")):
        name = read_text(event / "device/name")
        phys = read_text(event / "device/phys")
        dev = Path("/dev/input") / event.name
        if name and dev.exists():
            events.append(input_event_from_path(dev, name=name, phys=phys, source="sysfs"))
    return events


def input_event_from_path(path, name=None, phys=None, source="sysfs"):
    dev = Path(path)
    sysfs = Path("/sys/class/input") / dev.name
    return {
        "event": dev.name,
        "path": str(dev),
        "name": name if name is not None else read_text(sysfs / "device/name"),
        "phys": phys if phys is not None else read_text(sysfs / "device/phys"),
        "source": source,
    }


def busctl_get_property(path, interface, prop):
    try:
        result = subprocess.run(
            ["busctl", "--system", "--json=short", "get-property", INPUTPLUMBER_SERVICE, path, interface, prop],
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        return None
    data = payload.get("data")
    if str(payload.get("type", "")).startswith("a"):
        return data if isinstance(data, list) else []
    if isinstance(data, list):
        return data[0] if len(data) == 1 else data
    return data


def begin_calibration_intercept():
    try:
        call("inputplumber_intercept", mode="overlay")
        return True
    except Exception:
        pass
    try:
        subprocess.run(
            [str(INPUTPLUMBER_INTERCEPT), "overlay"],
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def end_calibration_intercept():
    try:
        call("inputplumber_intercept", mode="reset")
        return True
    except Exception:
        pass
    try:
        subprocess.run(
            [str(INPUTPLUMBER_INTERCEPT), "reset"],
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def inputplumber_source_events():
    now = time.monotonic()
    if now - _inputplumber_events_cache["time"] < 2:
        return copy.deepcopy(_inputplumber_events_cache["events"])

    try:
        result = subprocess.run(
            ["busctl", "--system", "--list", "--no-pager", "--no-legend"],
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        _inputplumber_events_cache.update({"time": now, "events": []})
        return []
    if INPUTPLUMBER_SERVICE not in result.stdout:
        _inputplumber_events_cache.update({"time": now, "events": []})
        return []

    try:
        tree = subprocess.run(
            ["busctl", "--system", "tree", INPUTPLUMBER_SERVICE],
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        _inputplumber_events_cache.update({"time": now, "events": []})
        return []

    events = []
    seen = set()
    for line in tree.stdout.splitlines():
        path = line.strip(" │├─└")
        if not path.startswith("/org/shadowblip/InputPlumber/CompositeDevice"):
            continue
        paths = busctl_get_property(path, INPUTPLUMBER_COMPOSITE_IFACE, "SourceDevicePaths")
        if not isinstance(paths, list):
            continue
        for source_path in paths:
            dev = Path(source_path)
            if dev.name in seen or not str(dev).startswith("/dev/input/event") or not dev.exists():
                continue
            event = input_event_from_path(dev, source="inputplumber")
            if event["name"]:
                events.append(event)
                seen.add(dev.name)
    _inputplumber_events_cache.update({"time": now, "events": copy.deepcopy(events)})
    return events


def calibration_event():
    events = inputplumber_source_events()
    if not events:
        events = input_events()
    preferred = (
        lambda event: "rsinput-gamepad" in event["phys"].casefold() or "rsinput" in event["name"].casefold(),
        lambda event: "retroid-pocket-gamepad" in event["phys"].casefold()
        or "retroid pocket gamepad" in event["name"].casefold(),
        lambda event: "AYANEO Controller" in event["name"],
        lambda event: event["name"] == "Microsoft X-Box 360 pad",
    )
    ignored = ("InputPlumber", "DualSense", "Keyboard", "Touchpad", "Motion Sensors", "Headset")
    for match in preferred:
        for event in events:
            if any(token in event["name"] for token in ignored):
                continue
            if match(event):
                return event
    for event in events:
        if any(token in event["name"] for token in ignored):
            continue
        if "pad" in event["name"].casefold() or "controller" in event["name"].casefold() or "gamepad" in event["name"].casefold():
            return event
    return None


def eviocgabs(code):
    return 0x80184540 + code


def read_abs(fd, code):
    data = fcntl.ioctl(fd, eviocgabs(code), b"\0" * 24)
    if len(data) != 24:
        raise OSError(f"unexpected EVIOCGABS response length for code {code}")
    value, minimum, maximum, fuzz, flat, resolution = struct.unpack("iiiiii", data)
    if minimum == maximum:
        raise OSError(f"analog control {code} has no range")
    return {
        "value": value,
        "min": minimum,
        "max": maximum,
        "flat": flat,
        "fuzz": fuzz,
        "resolution": resolution,
    }


def event_backend(event):
    if not event:
        return None
    name = str(event.get("name", "")).casefold()
    phys = str(event.get("phys", "")).casefold()
    if "rsinput" in name or "rsinput-gamepad" in phys:
        return "rsinput"
    if "retroid pocket gamepad" in name or "retroid-pocket-gamepad" in phys:
        return "retroid"
    return None


def calibration_backend(event=None):
    if event is None:
        event = calibration_event()
    backend = event_backend(event)
    if backend and CALIBRATION_BACKENDS[backend].exists():
        return backend
    return None


def read_backend_controls(fd, backend=None):
    controls = {}
    for name, code in ABS_CODES.items():
        try:
            controls[name] = read_abs(fd, code)
        except OSError:
            pass
    trigger_codes = TRIGGER_CODES.get(backend, TRIGGER_CODES["default"])
    for name, codes in trigger_codes.items():
        for code in codes:
            try:
                controls[name] = read_abs(fd, code)
                break
            except OSError:
                pass
    return controls


def build_state(event, controls):
    backend = calibration_backend(event)
    return {
        "supported": bool(controls),
        "reason": "" if controls else "Controller has no readable analog controls",
        "controls": controls,
        "event": event,
        "canApply": bool(backend),
        "backend": backend or "tester",
    }


def open_session_device():
    # Resolve the controller once per modal session and hold the fd open so each
    # ~50ms poll is a couple of ioctls, not a fresh device-enumeration + open.
    global _session_device, _session_fd
    close_session_device()
    event = calibration_event()
    if not event:
        return None
    try:
        _session_fd = open(event["path"], "rb", buffering=0)
        _session_device = event
    except OSError:
        _session_fd = None
        _session_device = None
    return _session_device


def close_session_device():
    global _session_device, _session_fd
    if _session_fd is not None:
        try:
            _session_fd.close()
        except OSError:
            pass
    _session_fd = None
    _session_device = None


def controller_state():
    if _session_fd is not None and _session_device is not None:
        try:
            return build_state(
                _session_device,
                read_backend_controls(_session_fd.fileno(), event_backend(_session_device)),
            )
        except OSError:
            # Node went away (device re-registered); re-resolve once.
            if open_session_device() and _session_fd is not None:
                try:
                    return build_state(
                        _session_device,
                        read_backend_controls(_session_fd.fileno(), event_backend(_session_device)),
                    )
                except OSError:
                    close_session_device()
    event = calibration_event()
    if not event:
        return {"supported": False, "reason": "No controller input device found", "controls": {}, "event": None}
    try:
        with open(event["path"], "rb", buffering=0) as f:
            controls = read_backend_controls(f.fileno(), event_backend(event))
    except OSError as exc:
        return {"supported": False, "reason": str(exc), "controls": {}, "event": event}
    return build_state(event, controls)


def read_calibration_params(backend=None):
    params = {}
    if backend is None:
        backend = calibration_backend()
    parameters = CALIBRATION_BACKENDS.get(backend)
    if parameters is None or not parameters.exists():
        return params
    for name in CALIBRATION_PARAMS:
        text = read_text(parameters / name)
        if text:
            try:
                params[name] = int(text)
            except ValueError:
                pass
    return params


def reset_calibration_params():
    backend = calibration_backend()
    if backend is None:
        raise RuntimeError("controller calibration is not supported on this device")
    params = {}
    axis_range = 1408 if backend == "retroid" else 1024
    axis_deadzone = 0 if backend == "retroid" else 70
    for axis in ("axis_leftx", "axis_lefty", "axis_rightx", "axis_righty"):
        params[f"{axis}_min"] = -axis_range
        params[f"{axis}_center"] = 0
        params[f"{axis}_max"] = axis_range
        params[f"{axis}_deadzone"] = axis_deadzone
        params[f"{axis}_antideadzone"] = 0
    for trigger in ("trigger_left", "trigger_right"):
        params[f"{trigger}_max"] = 1552
        params[f"{trigger}_deadzone"] = 0
        params[f"{trigger}_antideadzone"] = 0
    params["backend"] = backend
    call("write_config", name="calibration", text=json.dumps(params, indent=2, sort_keys=True) + "\n")
    return calibration_status()


def calibration_from_capture(capture, current=None):
    current = current or {}

    def axis_params(prefix, x_key, y_key):
        result = {}
        for suffix, key in (("x", x_key), ("y", y_key)):
            values = capture.get(key) or {}
            minimum = int(values.get("min", 0))
            maximum = int(values.get("max", 0))
            center = int(values.get("center", 0))
            negative = min(minimum - center, -1)
            positive = max(maximum - center, 1)
            inner = max(min(abs(negative), abs(positive)), 1)
            deadzone = max(int(inner * 0.07), 20)
            result[f"{prefix}{suffix}_min"] = -inner
            result[f"{prefix}{suffix}_center"] = int(current.get(f"{prefix}{suffix}_center", 0)) - center
            result[f"{prefix}{suffix}_max"] = inner
            result[f"{prefix}{suffix}_deadzone"] = deadzone
            result[f"{prefix}{suffix}_antideadzone"] = 0
        return result
    params = {}
    params.update(axis_params("axis_left", "left_x", "left_y"))
    params.update(axis_params("axis_right", "right_x", "right_y"))
    for name, key in (("trigger_left", "left_trigger"), ("trigger_right", "right_trigger")):
        values = capture.get(key) or {}
        minimum = int(values.get("min", 0))
        maximum = int(values.get("max", 0))
        span = max(maximum - minimum, 1)
        params[f"{name}_max"] = span
        params[f"{name}_deadzone"] = max(int(span * 0.03), 4)
        params[f"{name}_antideadzone"] = 0
    return params


def merge_capture_sample(capture, state):
    merged = copy.deepcopy(capture or {})
    for name, control in state.get("controls", {}).items():
        if name not in merged:
            continue
        value = int(control.get("value", 0))
        merged[name]["min"] = min(int(merged[name].get("min", value)), value)
        merged[name]["max"] = max(int(merged[name].get("max", value)), value)
    return merged


def calibration_status():
    state = controller_state()
    state["saved"] = INPUT_CALIBRATION_CONFIG.exists()
    backend = state.get("backend") if state.get("canApply") else None
    state["params"] = read_calibration_params(backend) if backend else {}
    if state.get("supported") and not state.get("canApply"):
        state["reason"] = "Live tester only on this device"
    return state


def save_calibration(capture):
    state = controller_state()
    backend = state.get("backend") if state.get("canApply") else None
    if backend not in CALIBRATION_BACKENDS:
        raise RuntimeError("controller calibration is not supported on this device")
    capture = merge_capture_sample(capture, state)
    params = calibration_from_capture(capture, read_calibration_params(backend))
    params["backend"] = backend
    call("write_config", name="calibration", text=json.dumps(params, indent=2, sort_keys=True) + "\n")
    return calibration_status()


def begin_session(token=None):
    global _calibration_session_token
    _calibration_session_token = str(token or "default")
    open_session_device()
    return begin_calibration_intercept()


def end_session(token=None):
    global _calibration_session_token
    if _calibration_session_token != str(token or "default"):
        return False
    _calibration_session_token = None
    close_session_device()
    return end_calibration_intercept()
