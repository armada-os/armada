from .privileged import call

DEFAULT_MODE = "direct"
TOUCHSCREEN_MODES = {"direct", "trackpad"}


def touchscreen_mode():
    try:
        value = str(call("get_touchscreen_mode").get("value") or "")
    except Exception:
        return DEFAULT_MODE
    return value if value in TOUCHSCREEN_MODES else DEFAULT_MODE


def set_touchscreen_mode(value):
    if value not in TOUCHSCREEN_MODES:
        raise ValueError("invalid touchscreen mode")
    return str(
        call("set_touchscreen_mode", value=value).get("value") or touchscreen_mode()
    )
