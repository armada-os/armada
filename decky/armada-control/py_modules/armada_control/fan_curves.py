import configparser
import re
import tempfile
from pathlib import Path

from .privileged import call
from .fan_sensors import get_current_temp

# Shared with Armada Control: only owns [fan_curve.*] sections and [fan]'s
# ramp/smoothing/min_pwm keys; forces min_pwm to 0 when any curve's fan-stopped.
POWER_CONFIG = Path("/etc/armada/power-profiles.conf")
FACTORY_POWER_CONFIG = Path("/usr/share/armada/power-profiles.conf")
# Profile armada-powerd is actually running (may differ from [general] default_profile).
STATE_FILE = Path("/var/lib/armada/powerd.state")
PROFILE_NAMES = ("eco", "balanced", "performance")

CURVE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
CURVE_POINT_RE = re.compile(r"^-?\d{1,3}:\d{1,3}$")
MIN_CURVE_TEMP, MAX_CURVE_TEMP = -40, 150
MIN_CURVE_PWM, MAX_CURVE_PWM = 0, 255

RAMP_KEYS = ("ramp_up", "ramp_down")
MIN_RAMP, MAX_RAMP = 1, 255
FACTORY_RAMP_FALLBACK = {"ramp_up": 36, "ramp_down": 6}

# Matches the clamp armada-powerd applies when it reads this key.
MIN_SMOOTHING, MAX_SMOOTHING = 0.0, 0.99
FACTORY_SMOOTHING_FALLBACK = 0.50

FACTORY_MIN_PWM_FALLBACK = 51
MIN_PWM, MAX_PWM = 0, 255


def default_label(name):
    return name.replace("_", " ").title()


def _read(path):
    parser = configparser.ConfigParser()
    parser.optionxform = str
    if path.exists():
        parser.read(path)
    return parser


def _read_merged():
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read([p for p in (FACTORY_POWER_CONFIG, POWER_CONFIG) if p.exists()])
    return parser


def _parse_fan_curves(parser):
    curves = {}
    for section in parser.sections():
        if not section.startswith("fan_curve."):
            continue
        name = section.split(".", 1)[1]
        curve = parser.get(section, "curve", fallback="")
        if not curve:
            continue
        curves[name] = {
            "label": parser.get(section, "label", fallback="") or default_label(name),
            "curve": curve,
        }
    return curves


def _parse_profile_summary(parser):
    profiles = {}
    for name in PROFILE_NAMES:
        section = f"profile.{name}"
        if not parser.has_section(section):
            continue
        profiles[name] = {
            "label": parser.get(section, "label", fallback="") or default_label(name),
            "fan_curve": parser.get(section, "fan_curve", fallback=""),
        }
    return profiles


def _parse_fan_settings(parser):
    out = {}
    for key in RAMP_KEYS:
        out[key] = parser.getint("fan", key, fallback=FACTORY_RAMP_FALLBACK[key])
    out["smoothing"] = parser.getfloat("fan", "smoothing", fallback=FACTORY_SMOOTHING_FALLBACK)
    out["min_pwm"] = parser.getint("fan", "min_pwm", fallback=FACTORY_MIN_PWM_FALLBACK)
    return out


def _parse_curve_points(value):
    points = []
    for item in str(value or "").split(","):
        item = item.strip()
        if not CURVE_POINT_RE.match(item):
            continue
        temp_s, pwm_s = item.split(":", 1)
        points.append((int(temp_s), int(pwm_s)))
    return points


def _curve_has_fan_stop(curve_string):
    points = _parse_curve_points(curve_string)
    if not points:
        return False
    lowest = min(points, key=lambda point: point[0])
    return lowest[1] == 0


def _read_active_profile(merged, profiles):
    # Prefer live daemon state; fall back to the configured default, then any profile.
    try:
        for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
            if not line.startswith("profile="):
                continue
            value = line.split("=", 1)[1].strip()
            if value in profiles:
                return value
    except OSError:
        pass

    default_profile = merged.get("general", "default_profile", fallback="")
    if default_profile in profiles:
        return default_profile

    return next(iter(sorted(profiles)), "")


def get_state():
    merged = _read_merged()
    factory = _read(FACTORY_POWER_CONFIG)
    profiles = _parse_profile_summary(merged)
    return {
        "fanCurves": _parse_fan_curves(merged),
        "factoryFanCurves": _parse_fan_curves(factory),
        "fanSettings": _parse_fan_settings(merged),
        "factoryFanSettings": _parse_fan_settings(factory),
        "profiles": profiles,
        "activeProfile": _read_active_profile(merged, profiles),
        "currentTemp": get_current_temp(),
    }


def validate_curve_string(value):
    text = str(value or "").strip()
    if not text:
        raise ValueError("fan curve must have at least one point")
    points = []
    for item in text.split(","):
        item = item.strip()
        if not CURVE_POINT_RE.match(item):
            raise ValueError(f"invalid curve point: {item!r}")
        temp_s, pwm_s = item.split(":", 1)
        temp, pwm = int(temp_s), int(pwm_s)
        if not (MIN_CURVE_TEMP <= temp <= MAX_CURVE_TEMP):
            raise ValueError(f"curve temperature out of range: {temp}")
        if not (MIN_CURVE_PWM <= pwm <= MAX_CURVE_PWM):
            raise ValueError(f"curve pwm out of range: {pwm}")
        points.append((temp, pwm))
    return ",".join(f"{temp}:{pwm}" for temp, pwm in points)


def _normalize_curves(fan_curves):
    if not isinstance(fan_curves, dict) or not fan_curves:
        raise ValueError("at least one fan curve is required")
    out = {}
    for name, curve in fan_curves.items():
        if not CURVE_NAME_RE.match(str(name)):
            raise ValueError(f"invalid fan curve name: {name!r}")
        if not isinstance(curve, dict):
            raise ValueError(f"invalid fan curve entry: {name!r}")
        out[name] = {
            "label": str(curve.get("label") or "").strip(),
            "curve": validate_curve_string(curve.get("curve")),
        }
    return out


def _normalize_settings(fan_settings):
    if not isinstance(fan_settings, dict):
        raise ValueError("invalid fan settings")
    out = {}
    for key in RAMP_KEYS:
        try:
            value = int(fan_settings.get(key))
        except (TypeError, ValueError):
            raise ValueError(f"invalid {key}: {fan_settings.get(key)!r}")
        if not (MIN_RAMP <= value <= MAX_RAMP):
            raise ValueError(f"{key} out of range: {value}")
        out[key] = value
    try:
        smoothing = round(float(fan_settings.get("smoothing")), 2)
    except (TypeError, ValueError):
        raise ValueError(f"invalid smoothing: {fan_settings.get('smoothing')!r}")
    if not (MIN_SMOOTHING <= smoothing <= MAX_SMOOTHING):
        raise ValueError(f"smoothing out of range: {smoothing}")
    out["smoothing"] = smoothing
    try:
        min_pwm = int(fan_settings.get("min_pwm"))
    except (TypeError, ValueError):
        raise ValueError(f"invalid min_pwm: {fan_settings.get('min_pwm')!r}")
    if not (MIN_PWM <= min_pwm <= MAX_PWM):
        raise ValueError(f"min_pwm out of range: {min_pwm}")
    out["min_pwm"] = min_pwm
    return out


def set_or_clear(parser, section, key, value, keep):
    if keep:
        if not parser.has_section(section):
            parser.add_section(section)
        parser.set(section, key, str(value))
    elif parser.has_section(section) and parser.has_option(section, key):
        parser.remove_option(section, key)


def render_all(fan_curves, fan_settings):
    fan_curves = _normalize_curves(fan_curves)
    fan_settings = _normalize_settings(fan_settings)
    factory_curves = _parse_fan_curves(_read(FACTORY_POWER_CONFIG))
    factory_settings = _parse_fan_settings(_read(FACTORY_POWER_CONFIG))

    # Everything else in the file is preserved byte-for-byte.
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(POWER_CONFIG)

    existing_curve_sections = {s for s in parser.sections() if s.startswith("fan_curve.")}

    for name, curve in fan_curves.items():
        section = f"fan_curve.{name}"
        factory_curve = factory_curves.get(name)
        edited = (
            factory_curve is None
            or curve["curve"] != factory_curve.get("curve")
            or (curve["label"] and curve["label"] != factory_curve.get("label"))
        )
        set_or_clear(parser, section, "curve", curve["curve"], edited)
        if curve["label"]:
            set_or_clear(parser, section, "label", curve["label"], edited)
        if parser.has_section(section) and not parser.options(section):
            parser.remove_section(section)

    # Drops overrides for curves removed from the payload; no-op for factory-only curves.
    kept_sections = {f"fan_curve.{name}" for name in fan_curves}
    for section in existing_curve_sections - kept_sections:
        parser.remove_section(section)

    for key in RAMP_KEYS:
        edited = fan_settings[key] != factory_settings[key]
        set_or_clear(parser, "fan", key, fan_settings[key], edited)

    # Rounded on both sides since getfloat isn't guaranteed exact to 2 decimals.
    smoothing_edited = round(fan_settings["smoothing"], 2) != round(factory_settings["smoothing"], 2)
    set_or_clear(parser, "fan", "smoothing", fan_settings["smoothing"], smoothing_edited)

    # Forces min_pwm to 0 when any curve is fan-stopped (see note at top of file).
    any_fan_stop = any(_curve_has_fan_stop(curve["curve"]) for curve in fan_curves.values())
    effective_min_pwm = 0 if any_fan_stop else fan_settings["min_pwm"]
    factory_min_pwm = factory_settings["min_pwm"]
    min_pwm_edited = effective_min_pwm != factory_min_pwm
    set_or_clear(parser, "fan", "min_pwm", effective_min_pwm, min_pwm_edited)

    with tempfile.TemporaryFile("w+", encoding="utf-8") as f:
        parser.write(f)
        f.seek(0)
        return f.read()


def save_all(fan_curves, fan_settings):
    state = get_state()
    used_by = {}
    for profile_name, profile in state["profiles"].items():
        used_by.setdefault(profile["fan_curve"], []).append(profile["label"])
    normalized = _normalize_curves(fan_curves)
    for removed in set(state["fanCurves"]) - set(normalized):
        if removed in used_by:
            names = ", ".join(used_by[removed])
            raise ValueError(f"can't remove '{removed}': still assigned to {names} on the Power tab")
    rendered = render_all(fan_curves, fan_settings)
    call("write_config", name="power", text=rendered)
    return get_state()
