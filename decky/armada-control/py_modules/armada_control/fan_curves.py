import configparser
import os
import re
import sys
from pathlib import Path

from .privileged import call
from .fan_sensors import get_current_temp
from .power_config import FACTORY_POWER_CONFIG, POWER_CONFIG, POWER_CONFIG_LOCK, render_config

sys.path.insert(0, os.environ.get("ARMADA_GAME_TWEAKS_LIB", "/usr/lib/armada"))
from armada_fan import FAN_DEFAULTS, discover_fan_hwmon, normalize_fan_settings, read_fan_settings

# Profile armada-powerd is actually running (may differ from [general] default_profile).
STATE_FILE = Path("/var/lib/armada/powerd.state")
PROFILE_NAMES = ("eco", "balanced", "performance")

CURVE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
CURVE_POINT_RE = re.compile(r"^-?\d{1,3}:\d{1,3}$")
MIN_CURVE_TEMP, MAX_CURVE_TEMP = -40, 150
MIN_CURVE_PWM, MAX_CURVE_PWM = 0, 255


def default_label(name):
    return name.replace("_", " ").title()


def normalize_curve_reference(value):
    if not isinstance(value, str):
        raise ValueError("invalid fan curve reference")
    return value.strip().lower()


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
    settings = read_fan_settings(parser)
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
            **read_fan_settings(parser, section, settings),
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
            "fan_curve": normalize_curve_reference(parser.get(section, "fan_curve", fallback="")),
        }
    return profiles


def _parse_fan_settings(parser):
    return read_fan_settings(parser)


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


def charging_fan_supported():
    return discover_fan_hwmon() is not None


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
    if not isinstance(fan_curves, dict):
        raise ValueError("invalid fan curves")
    out = {}
    for name, curve in fan_curves.items():
        if not isinstance(name, str) or not CURVE_NAME_RE.fullmatch(name):
            raise ValueError(f"invalid fan curve name: {name!r}")
        if not isinstance(curve, dict):
            raise ValueError(f"invalid fan curve entry: {name!r}")
        label = curve.get("label", "")
        if not isinstance(label, str) or len(label) > 80 or any(c in label for c in "\r\n\0"):
            raise ValueError(f"invalid fan curve label: {name!r}")
        out[name] = {
            "label": label.strip() or default_label(name),
            "curve": validate_curve_string(curve.get("curve")),
            **normalize_fan_settings(curve),
        }
    return out


def _normalize_deleted(deleted):
    if not isinstance(deleted, list):
        raise ValueError("invalid deleted fan curves")
    for name in deleted:
        if not isinstance(name, str) or not CURVE_NAME_RE.fullmatch(name):
            raise ValueError(f"invalid fan curve name: {name!r}")
    return set(deleted)


def set_or_clear(parser, section, key, value, keep):
    if keep:
        if not parser.has_section(section):
            parser.add_section(section)
        parser.set(section, key, str(value))
    elif parser.has_section(section) and parser.has_option(section, key):
        parser.remove_option(section, key)


def render_all(fan_curves, deleted=None):
    fan_curves = _normalize_curves(fan_curves)
    deleted = _normalize_deleted([] if deleted is None else deleted)
    if deleted.intersection(fan_curves):
        raise ValueError("can't save and delete the same fan curve")
    merged = _read_merged()
    factory = _read(FACTORY_POWER_CONFIG)
    factory_curves = _parse_fan_curves(factory)
    settings = read_fan_settings(merged)
    existing_curves = _parse_fan_curves(merged)
    profiles = _parse_profile_summary(merged)
    for name in deleted:
        if name in factory_curves:
            raise ValueError(f"can't remove built-in fan curve '{name}'")
        if name not in existing_curves:
            raise ValueError(f"unknown fan curve: {name!r}")
        assigned = [p["label"] for p in profiles.values() if p["fan_curve"] == name]
        if assigned:
            raise ValueError(f"can't remove '{name}': still assigned to {', '.join(assigned)}")

    parser = _read(POWER_CONFIG)

    for name, curve in fan_curves.items():
        section = f"fan_curve.{name}"
        # Compare with inherited settings, which may include legacy [fan] overrides.
        baseline = {
            "label": default_label(name),
            "curve": None,
            **factory_curves.get(name, {}),
            **read_fan_settings(factory, section, settings),
        }
        for key in ("label", "curve", *FAN_DEFAULTS):
            set_or_clear(parser, section, key, curve[key], curve[key] != baseline[key])
        if parser.has_section(section) and not parser.options(section):
            parser.remove_section(section)

    for name in deleted:
        parser.remove_section(f"fan_curve.{name}")

    return render_config(parser)


def save_charging_pwm(pwm):
    pwm = normalize_fan_settings({**FAN_DEFAULTS, "min_pwm": pwm})["min_pwm"]
    with POWER_CONFIG_LOCK:
        parser = _read(POWER_CONFIG)
        factory = _read(FACTORY_POWER_CONFIG).getint("fan", "charging_pwm", fallback=0)
        set_or_clear(parser, "fan", "charging_pwm", pwm, pwm != factory)
        call("write_config", name="power", text=render_config(parser))
        return pwm


def save_all(fan_curves, deleted=None):
    with POWER_CONFIG_LOCK:
        rendered = render_all(fan_curves, deleted)
        if fan_curves or deleted:
            call("write_config", name="power", text=rendered)
        return get_state()
