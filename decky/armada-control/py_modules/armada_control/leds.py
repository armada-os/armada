from .privileged import call

DEFAULTS = {
    "enabled": False,
    "mode": "static",
    "brightness": 60,
    "left": "ff0000",
    "right": "ff0000",
    "period": 4.0,
}


def led_state():
    try:
        result = call("get_leds")
    except Exception:
        return {"supported": False, "leds": dict(DEFAULTS)}
    return {
        "supported": bool(result.get("supported")),
        "leds": result.get("leds") or dict(DEFAULTS),
    }


def save_leds(data):
    if not isinstance(data, dict):
        raise ValueError("invalid led config")
    return call("set_leds", leds=data)
