import re
import subprocess

from .privileged import call

STICK_LED_SCRIPT = "/usr/libexec/armada/stick-led-color"
STICK_LED_MODES = {"static", "breathing", "battery", "battery-breathing", "rainbow", "chase", "alternating", "reactive", "multidot", "ambilight"}
STICK_LED_PARAMS = ("speed", "intensity", "size")
FLASH_BUTTONS = (
    "south", "east", "north", "west",
    "l1", "r1", "l3", "r3", "l4", "r4",
    "start", "select",
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
    "other",
)
DEFAULT_COLOR = "0050FF"
DEFAULT_MODE = "static"
DEFAULT_SCREEN_LINK = False


def stick_led_supported():
    from pathlib import Path

    return Path("/sys/class/leds/l:r1").exists()


def _default_state(supported):
    return {
        "supported": supported,
        "mode": DEFAULT_MODE,
        "color": DEFAULT_COLOR,
        "screenLink": DEFAULT_SCREEN_LINK,
        "params": {},
        "flashColors": {},
    }


def stick_led_state():
    if not stick_led_supported():
        return _default_state(False)
    try:
        result = call("get_stick_led")
        mode = str(result.get("mode") or DEFAULT_MODE)
        color = str(result.get("color") or DEFAULT_COLOR)
        screen_link = bool(result.get("screen_link"))
        params = {k: float(v) for k, v in dict(result.get("params") or {}).items()}
        flash_colors = {k: str(v) for k, v in dict(result.get("flashColors") or {}).items()}
    except Exception:
        try:
            out = subprocess.check_output([STICK_LED_SCRIPT, "get"], text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return _default_state(True)
        mode, color, screen_link, params, flash_colors = DEFAULT_MODE, DEFAULT_COLOR, DEFAULT_SCREEN_LINK, {}, {}
        for line in out.splitlines():
            key, sep, value = line.partition("=")
            if not sep:
                continue
            key, value = key.strip(), value.strip()
            if key == "mode" and value in STICK_LED_MODES:
                mode = value
            elif key == "color" and re.fullmatch(r"[0-9A-Fa-f]{6}", value or ""):
                color = value
            elif key == "screen_link":
                screen_link = value == "1"
            elif key.startswith("flash_") and key[len("flash_"):] in FLASH_BUTTONS:
                if re.fullmatch(r"[0-9A-Fa-f]{6}", value or ""):
                    flash_colors[key[len("flash_"):]] = value.upper()
            elif "_" in key and key.split("_", 1)[0] in STICK_LED_PARAMS:
                try:
                    params[key] = float(value)
                except ValueError:
                    pass
        return {
            "supported": True,
            "mode": mode,
            "color": color,
            "screenLink": screen_link,
            "params": params,
            "flashColors": flash_colors,
        }
    return {
        "supported": True,
        "mode": mode if mode in STICK_LED_MODES else DEFAULT_MODE,
        "color": color,
        "screenLink": screen_link,
        "params": params,
        "flashColors": flash_colors,
    }


def set_stick_led_color(value):
    value = str(value).lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        raise ValueError("invalid color")
    call("set_stick_led_color", value=value.upper())
    return stick_led_state()


def set_stick_led_mode(mode):
    if mode not in STICK_LED_MODES:
        raise ValueError("invalid stick led mode")
    call("set_stick_led_mode", mode=mode)
    return stick_led_state()


def set_stick_led_screen_link(enabled):
    call("set_stick_led_screen_link", enabled=bool(enabled))
    return stick_led_state()


def set_stick_led_param(param, mode, value):
    if param not in STICK_LED_PARAMS:
        raise ValueError("invalid stick led param")
    call("set_stick_led_param", param=param, mode=mode, value=float(value))
    return stick_led_state()


def set_stick_led_flash_color(button, value):
    if button not in FLASH_BUTTONS:
        raise ValueError("invalid flash button")
    value = str(value).lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        raise ValueError("invalid color")
    call("set_stick_led_flash_color", button=button, value=value.upper())
    return stick_led_state()
