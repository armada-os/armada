import subprocess

from .privileged import call

CONTROLLER_LAYOUT = "/usr/libexec/armada/controller-layout"
DEFAULT_LAYOUT = "auto"
BUTTON_LAYOUTS = {
    "auto": "Automatic",
    "xbox": "Xbox",
    "nintendo": "Nintendo",
}


def _valid(value, default):
    return value if value in BUTTON_LAYOUTS else default


def button_layout_state():
    try:
        result = call("get_button_layout")
        value = _valid(str(result.get("value") or ""), DEFAULT_LAYOUT)
        resolved = _valid(str(result.get("resolved") or ""), "xbox")
        return {"value": value, "resolved": resolved}
    except Exception:
        pass
    try:
        value = subprocess.check_output((CONTROLLER_LAYOUT, "get"), text=True, timeout=3).strip()
        resolved = subprocess.check_output((CONTROLLER_LAYOUT, "resolve"), text=True, timeout=3).strip()
    except (OSError, subprocess.SubprocessError):
        return {"value": DEFAULT_LAYOUT, "resolved": "xbox"}
    return {
        "value": _valid(value, DEFAULT_LAYOUT),
        "resolved": _valid(resolved, "xbox"),
    }


def set_button_layout(value):
    if value not in BUTTON_LAYOUTS:
        raise ValueError("invalid button layout")
    result = call("set_button_layout", value=value)
    return {
        "value": _valid(str(result.get("value") or ""), DEFAULT_LAYOUT),
        "resolved": _valid(str(result.get("resolved") or ""), "xbox"),
    }
