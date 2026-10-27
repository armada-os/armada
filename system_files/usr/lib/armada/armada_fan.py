import math
from pathlib import Path


HWMON_ROOT = Path("/sys/class/hwmon")
FAN_DEFAULTS = {"ramp_up": 36, "ramp_down": 6, "smoothing": 0.50, "min_pwm": 51}


def normalize_fan_settings(values, *, clamp_values=False):
    if not isinstance(values, dict):
        raise ValueError("invalid fan settings")
    settings = {}
    for key, minimum in (("ramp_up", 1), ("ramp_down", 1), ("min_pwm", 0)):
        raw = values.get(key)
        try:
            number = float(raw)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"invalid {key}: {raw!r}")
        if isinstance(raw, bool) or not math.isfinite(number) or not number.is_integer():
            raise ValueError(f"invalid {key}: {raw!r}")
        if clamp_values:
            number = max(minimum, min(number, 255))
        elif not minimum <= number <= 255:
            raise ValueError(f"{key} out of range: {raw!r}")
        settings[key] = int(number)
    raw = values.get("smoothing")
    try:
        smoothing = float(raw)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"invalid smoothing: {raw!r}")
    if isinstance(raw, bool) or not math.isfinite(smoothing):
        raise ValueError(f"smoothing out of range: {raw!r}")
    if clamp_values:
        smoothing = max(0.0, min(smoothing, 0.99))
    elif not 0 <= smoothing <= 0.99:
        raise ValueError(f"smoothing out of range: {raw!r}")
    settings["smoothing"] = smoothing
    return settings


def read_fan_settings(parser, section="fan", fallback=None):
    inherited = FAN_DEFAULTS if fallback is None else fallback
    return normalize_fan_settings({
        key: parser.get(section, key, fallback=inherited[key]) for key in FAN_DEFAULTS
    }, clamp_values=True)


def discover_fan_hwmon():
    controls = [path for path in HWMON_ROOT.glob("hwmon*") if (path / "pwm1").exists()]
    for path in controls:
        try:
            if (path / "name").read_text().strip() == "pwmfan":
                return path
        except OSError:
            pass
    return next(iter(controls), None)
