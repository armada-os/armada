import copy
import fcntl
import json
import struct
import sys
import subprocess
import time
from pathlib import Path

from .privileged import call
from .proc import clean_env
from .system import read_text

sys.path.insert(0, "/usr/lib/armada")
import input_calibration_policy as calibration_policy

INPUT_CALIBRATION_CONFIG = Path("/etc/armada/input-calibration.json")
CALIBRATION_BACKENDS = {
    "mangmi": Path("/sys/module/mangmi_pocket_max/parameters"),
    "rsinput": Path("/sys/module/rsinput/parameters"),
    "retroid": Path("/sys/module/retroid/parameters"),
}
INPUTPLUMBER_INTERCEPT = Path("/usr/libexec/armada/inputplumber-intercept")
INPUTPLUMBER_SERVICE = "org.shadowblip.InputPlumber"
INPUTPLUMBER_COMPOSITE_IFACE = "org.shadowblip.Input.CompositeDevice"
AXIS_PARAMS = {
    "left_x": "axis_leftx",
    "left_y": "axis_lefty",
    "right_x": "axis_rightx",
    "right_y": "axis_righty",
}
ABS_CODES = {
    "left_x": 0,
    "left_y": 1,
    "right_x": 3,
    "right_y": 4,
}
TRIGGER_CODES = {
    "default": {"left_trigger": (2, 10), "right_trigger": (5, 9)},
    "mangmi": {"left_trigger": (20,), "right_trigger": (21,)},
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
# Driver defaults: 0x610 in rsinput and retroid, MCU_BRAKE_MAX/MCU_GAS_MAX in mangmi.
TRIGGER_DEFAULT_MAX = {
    "mangmi": {"trigger_left": 1910, "trigger_right": 1758},
    "retroid": {"trigger_left": 1552, "trigger_right": 1552},
    "rsinput": {"trigger_left": 1552, "trigger_right": 1552},
}
# Driver defaults as (range, deadzone); rsinput device trees may override them.
STICK_DEFAULTS = {
    "mangmi": (1408, 70),
    "retroid": (1408, 0),
    "rsinput": (1408, 0),
}
STICK_MIN_TRAVEL = 256
# 2: trigger deadzones are relative to the driver's fixed release reference.
CALIBRATION_VERSION = 2
TRIGGER_MIN_TRAVEL = 256
OUTER_MARGIN_PERCENT = 3
STICK_OUTER_MARGIN_PERCENT = 5
# A few releases rarely show how far the resting position really wanders.
STICK_MIN_DEADZONE_PERCENT = 5
# A reading counts once it has held steady this long; a moving stick overshoots what a push reaches.
HOLD_SECONDS = 0.5
STICK_KEYS = {"left_stick": ("left_x", "left_y"), "right_stick": ("right_x", "right_y")}
TRIGGER_KEYS = ("left_trigger", "right_trigger")
_inputplumber_events_cache = {"time": 0, "events": []}
_calibration_session_token = None
_session_device = None
_session_fd = None
_ranges_stale = False
_recording = None


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
            env=clean_env(),
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
            env=clean_env(),
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
            env=clean_env(),
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
            env=clean_env(),
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
            env=clean_env(),
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
        lambda event: "mangmi-pocket-max" in event["phys"].casefold()
        or "mangmi pocket max joypad" in event["name"].casefold(),
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
    if "mangmi pocket max joypad" in name or "mangmi-pocket-max" in phys:
        return "mangmi"
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
        "calibration": calibration_policy.capability(backend),
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
    state = read_controller_state()
    if _recording is not None and state.get("supported"):
        _recording.sample(state["controls"], time.monotonic())
        state["progress"] = _recording.progress()
    return state


def read_controller_state():
    if _session_fd is not None and _session_device is not None:
        try:
            return build_state(
                _session_device,
                read_backend_controls(_session_fd.fileno(), event_backend(_session_device)),
            )
        except ValueError:
            # The session closed under this read.
            pass
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


def device_tree_u32(event, name):
    node = Path("/sys/class/input") / str(event.get("event", "")) / "device/device/of_node" / name
    try:
        data = node.read_bytes()
    except OSError:
        return None
    return int.from_bytes(data[:4], "big") if len(data) >= 4 else None


def inverted_axes(event, backend):
    # rsinput flips these axes after adding the center, so their center correction flips too.
    if backend != "rsinput":
        return frozenset()
    node = Path("/sys/class/input") / str(event.get("event", "")) / "device/device/of_node"
    names = {"invert-x": "axis_leftx", "invert-y": "axis_lefty", "invert-rx": "axis_rightx", "invert-ry": "axis_righty"}
    return frozenset(axis for prop, axis in names.items() if (node / prop).exists())


def stick_defaults(event, backend):
    axis_range, axis_deadzone = STICK_DEFAULTS[backend]
    if backend == "rsinput":
        axis_range = device_tree_u32(event, "axis-range") or axis_range
        axis_deadzone = device_tree_u32(event, "axis-deadzone") or axis_deadzone
    return axis_range, axis_deadzone


def reset_calibration_params(triggers_only=False):
    global _ranges_stale, _recording
    _recording = None
    event = calibration_event()
    backend = calibration_backend(event)
    if backend is None:
        raise RuntimeError("controller calibration is not supported on this device")
    if triggers_only and not calibration_policy.capability(backend)["triggers"]:
        raise RuntimeError("trigger calibration requires raw trigger support from the driver")
    if not triggers_only and calibration_policy.uses_mcu(backend):
        raise RuntimeError("stick calibration is managed by the MCU on this device")
    params = read_calibration_params(backend) if triggers_only else {}
    axis_range, axis_deadzone = stick_defaults(event, backend)
    trigger_deadzone = {"trigger_left": 0, "trigger_right": 0}
    if backend == "rsinput":
        trigger_deadzone["trigger_left"] = device_tree_u32(event, "trigger-left-deadzone") or 0
        trigger_deadzone["trigger_right"] = device_tree_u32(event, "trigger-right-deadzone") or 0
    for axis in (() if triggers_only else ("axis_leftx", "axis_lefty", "axis_rightx", "axis_righty")):
        params[f"{axis}_min"] = -axis_range
        params[f"{axis}_center"] = 0
        params[f"{axis}_max"] = axis_range
        params[f"{axis}_deadzone"] = axis_deadzone
        params[f"{axis}_antideadzone"] = 0
    for trigger in ("trigger_left", "trigger_right"):
        params[f"{trigger}_max"] = TRIGGER_DEFAULT_MAX[backend][trigger]
        params[f"{trigger}_deadzone"] = trigger_deadzone[trigger]
        params[f"{trigger}_antideadzone"] = 0
    params["backend"] = backend
    params = calibration_policy.clean_config(params)
    params["version"] = CALIBRATION_VERSION
    call("write_config", name="calibration", text=json.dumps(params, indent=2, sort_keys=True) + "\n")
    _ranges_stale = True
    return calibration_status()


class Hold:
    def __init__(self):
        self.zone = None
        self.low = self.high = ()
        self.since = 0.0
        self.fired = False

    def update(self, zone, values, tolerance, now):
        steady = zone is not None and zone == self.zone
        if steady:
            low = tuple(map(min, self.low, values))
            high = tuple(map(max, self.high, values))
            steady = all(b - a <= tolerance for a, b in zip(low, high))
        if not steady:
            self.zone = zone
            self.low = self.high = tuple(values)
            self.since = now
            self.fired = False
            return None
        self.low, self.high = low, high
        if self.fired or now - self.since < HOLD_SECONDS:
            return None
        self.fired = True
        return tuple((a + b) // 2 for a, b in zip(low, high))

    def fill(self, now):
        if self.zone is None:
            return 0.0
        return 1.0 if self.fired else min((now - self.since) / HOLD_SECONDS, 1.0)


class Recording:
    def __init__(self, params, triggers_only=False):
        self.params = params
        self.triggers_only = triggers_only
        self.holds = {name: Hold() for name in (*STICK_KEYS, *TRIGGER_KEYS)}
        self.pushes = {name: {} for name in STICK_KEYS}
        self.rests = {name: [] for name in STICK_KEYS}
        self.triggers = {}
        self.now = None

    def sample(self, controls, now):
        first = self.now is None
        for stick, keys in STICK_KEYS.items():
            if self.triggers_only:
                continue
            if all(key in controls for key in keys):
                self.sample_stick(stick, [controls[key] for key in keys], keys, now, first)
        for name in TRIGGER_KEYS:
            if name in controls:
                self.sample_trigger(name, controls[name], now)
        self.now = now

    def sample_stick(self, stick, axes, keys, now, first):
        values, reach = [], []
        for control, key in zip(axes, keys):
            antideadzone = int(self.params.get(f"{AXIS_PARAMS[key]}_antideadzone", 0))
            value = int(control["value"])
            # The driver subtracts the antideadzone; evdev fuzz can hold a released axis off zero.
            if abs(value) <= int(control.get("fuzz", 0)):
                value = 0
            elif antideadzone:
                value += antideadzone if value > 0 else -antideadzone
            values.append(value)
            reach.append((int(control["max"]) - int(control["min"])) // 2 + antideadzone)
        x, y = values
        zone = None
        if abs(x) < reach[0] // 4 and abs(y) < reach[1] // 4:
            zone = "rest"
        elif abs(x) > reach[0] // 2 and abs(y) < abs(x) // 2:
            zone = "left" if x < 0 else "right"
        elif abs(y) > reach[1] // 2 and abs(x) < abs(y) // 2:
            zone = "up" if y < 0 else "down"
        held = self.holds[stick].update(zone, values, max(8, min(reach) * 15 // 1000), now)
        if first and zone == "rest":
            # A stick needs one resting position to save, and it is released when recording starts.
            held = tuple(values)
        if held is None:
            return
        if zone == "rest":
            self.rests[stick].append(held)
            return
        push = held[0] if zone in ("left", "right") else held[1]
        # A stick left resting partway must not shrink a full push already recorded.
        if abs(push) * 100 >= abs(self.pushes[stick].get(zone, 0)) * 85:
            self.pushes[stick][zone] = push

    def sample_trigger(self, name, control, now):
        value = int(control["value"])
        trigger = self.triggers.setdefault(name, {"min": value, "fuzz": int(control.get("fuzz", 0))})
        trigger["min"] = min(trigger["min"], value)
        reach = int(control["max"]) - int(control["min"])
        zone = "full" if value - int(control["min"]) > reach // 2 else None
        held = self.holds[name].update(zone, (value,), max(8, reach * 15 // 1000), now)
        if held is not None:
            trigger["max"] = max(trigger.get("max", 0), held[0])

    def progress(self):
        result = {}
        for stick in STICK_KEYS:
            hold = self.holds[stick]
            result[stick] = {
                side: 1.0 if side in self.pushes[stick] else (hold.fill(self.now) if hold.zone == side else 0.0)
                for side in ("left", "right", "up", "down")
            }
        for name in TRIGGER_KEYS:
            done = "max" in self.triggers.get(name, {})
            result[name] = 1.0 if done else self.holds[name].fill(self.now)
        result["ready"] = bool(self.capture())
        return result

    def capture(self):
        capture = {}
        for stick, keys in STICK_KEYS.items():
            rests = self.rests[stick]
            for index, (key, sides) in enumerate(zip(keys, (("left", "right"), ("up", "down")))):
                if not rests or any(side not in self.pushes[stick] for side in sides):
                    continue
                resting = [rest[index] for rest in rests]
                capture[key] = {
                    "min": self.pushes[stick][sides[0]],
                    "max": self.pushes[stick][sides[1]],
                    "rest_min": min(resting),
                    "rest_max": max(resting),
                }
        capture.update({name: trigger for name, trigger in self.triggers.items() if "max" in trigger})
        return capture


def calibration_from_capture(capture, current=None, stick_deadzone=0, inverted=()):
    current = current or {}
    params = dict(current)
    for key, axis in AXIS_PARAMS.items():
        values = capture.get(key) or {}
        rest_min = int(values.get("rest_min", 0))
        rest_max = int(values.get("rest_max", 0))
        center = (rest_min + rest_max) // 2
        inner = min(center - int(values.get("min", 0)), int(values.get("max", 0)) - center)
        if inner < STICK_MIN_TRAVEL:
            continue
        inner = inner * (100 - STICK_OUTER_MARGIN_PERCENT) // 100
        shift = -center if axis in inverted else center
        params[f"{axis}_min"] = -inner
        params[f"{axis}_center"] = int(current.get(f"{axis}_center", 0)) - shift
        params[f"{axis}_max"] = inner
        deadzone = max(
            stick_deadzone,
            inner * STICK_MIN_DEADZONE_PERCENT // 100,
            (rest_max - rest_min + 1) // 2 * 3 // 2,
        )
        if rest_min <= 0 <= rest_max:
            # A rest reading of 0 may sit anywhere inside the active deadzone, so keep all of it covered.
            deadzone = max(deadzone, int(current.get(f"{axis}_deadzone", 0)) + abs(center))
        params[f"{axis}_deadzone"] = deadzone
        params[f"{axis}_antideadzone"] = deadzone
    for name, key in (("trigger_left", "left_trigger"), ("trigger_right", "right_trigger")):
        values = capture.get(key) or {}
        minimum = int(values.get("min", 0))
        maximum = int(values.get("max", 0))
        current_deadzone = int(current.get(f"{name}_deadzone", 0))
        current_antideadzone = int(current.get(f"{name}_antideadzone", 0))
        if minimum <= int(values.get("fuzz", 0)):
            # evdev fuzz filtering can hold a released trigger slightly above zero.
            minimum = 0
        if maximum - minimum < TRIGGER_MIN_TRAVEL:
            continue
        # Samples arrive with the active antideadzone already subtracted.
        full = maximum + current_antideadzone
        rest = minimum + current_antideadzone if minimum > 0 else 0
        margin = max(int((full - rest) * 0.03), 4)
        # A rest reading of 0 may be hidden by the active deadzone, so never shrink it.
        deadzone = rest + margin if minimum > 0 else max(current_deadzone, margin)
        params[f"{name}_max"] = full * (100 - OUTER_MARGIN_PERCENT) // 100
        params[f"{name}_deadzone"] = deadzone
        params[f"{name}_antideadzone"] = deadzone
    return params


def calibration_status():
    state = controller_state()
    state["saved"] = INPUT_CALIBRATION_CONFIG.exists()
    backend = state.get("backend") if state.get("canApply") else None
    state["params"] = read_calibration_params(backend) if backend else {}
    if state.get("supported") and not state.get("canApply"):
        state["reason"] = "Live tester only on this device"
    return state


def start_recording():
    global _recording
    _recording = None
    state = read_controller_state()
    backend = state.get("backend") if state.get("canApply") else None
    if backend not in CALIBRATION_BACKENDS:
        raise RuntimeError("controller calibration is not supported on this device")
    if not calibration_policy.capability(backend)["triggers"]:
        raise RuntimeError("trigger calibration requires raw trigger support from the driver")
    _recording = Recording(read_calibration_params(backend), calibration_policy.uses_mcu(backend))
    return controller_state()


def save_calibration():
    global _ranges_stale, _recording
    state = read_controller_state()
    backend = state.get("backend") if state.get("canApply") else None
    if backend not in CALIBRATION_BACKENDS:
        raise RuntimeError("controller calibration is not supported on this device")
    if not calibration_policy.capability(backend)["triggers"]:
        raise RuntimeError("trigger calibration requires raw trigger support from the driver")
    capture = _recording.capture() if _recording is not None else {}
    if calibration_policy.uses_mcu(backend):
        capture = {key: value for key, value in capture.items() if key in TRIGGER_KEYS}
    if not capture:
        raise RuntimeError("nothing was calibrated")
    current = read_calibration_params(backend)
    if any(name not in current for name in CALIBRATION_PARAMS):
        # Untouched controls are saved from these; a partial read would drop them at boot.
        raise RuntimeError("could not read the current controller calibration")
    event = state.get("event") or {}
    _, stick_deadzone = stick_defaults(event, backend)
    params = calibration_from_capture(capture, current, stick_deadzone, inverted_axes(event, backend))
    params["backend"] = backend
    params = calibration_policy.clean_config(params)
    params["version"] = CALIBRATION_VERSION
    call("write_config", name="calibration", text=json.dumps(params, indent=2, sort_keys=True) + "\n")
    _ranges_stale = True
    _recording = None
    return calibration_status()


def begin_session(token=None):
    global _calibration_session_token
    _calibration_session_token = str(token or "default")
    open_session_device()
    return begin_calibration_intercept()


def end_session(token=None):
    global _calibration_session_token, _ranges_stale, _recording
    if _calibration_session_token != str(token or "default"):
        return False
    _recording = None
    close_session_device()
    ended = end_calibration_intercept()
    if _ranges_stale:
        # Restarting InputPlumber any earlier would drop the calibration intercept.
        call("reload_input_ranges")
        _ranges_stale = False
    _calibration_session_token = None
    return ended


def mcu_calibration(operation, token, step=None):
    global _ranges_stale
    # Start prepares the live stick parameters. Refresh consumers when the modal
    # closes even if the RPC response is lost or measurement is cancelled.
    if operation == "start":
        _ranges_stale = True
    return call("rsinput_calibration", operation=operation, token=token, step=step)
