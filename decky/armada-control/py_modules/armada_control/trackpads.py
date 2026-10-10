from .privileged import call


DEFAULT = {
    "supported": False,
    "secondaryAvailable": False,
    "enabled": False,
    "blockTouchscreen": False,
    "gameModeOnly": True,
    "shortcutEnabled": True,
    "shortcutButtons": ["L3", "R3"],
    "shortcutHoldSeconds": 3,
    "screen": "primary",
    "leftEnabled": True,
    "rightEnabled": True,
    "mode": "simple",
    "tapToClick": True,
    "limitToBounds": True,
    "leftSize": 35,
    "rightSize": 35,
    "edgeGap": 8,
    "hapticStrength": 60,
    "borderOpacity": 30,
    "borderWidth": 2,
    "backgroundStyle": "dots",
    "backgroundOpacity": 30,
    "autoHide": True,
    "hideDelay": 1,
    "borderRadius": 24,
    "dotSize": 1,
    "dotGap": 4,
    "centerDotEnabled": False,
    "centerDotSize": 8,
    "centerDotOpacity": 35,
}


def get_virtual_trackpads():
    try:
        return {**DEFAULT, **call("get_virtual_trackpads")}
    except (OSError, RuntimeError, KeyError, TypeError, ValueError):
        return dict(DEFAULT)


def set_virtual_trackpads(config):
    return call("set_virtual_trackpads", config=config)


def reset_virtual_trackpads():
    return call("reset_virtual_trackpads")


def get_virtual_trackpads_state():
    try:
        return call("get_virtual_trackpads_state")
    except (OSError, RuntimeError, KeyError, TypeError, ValueError):
        return {
            "leftActive": False,
            "rightActive": False,
            "leftZone": "bottom",
            "rightZone": "bottom",
            "leftX": 0.25,
            "leftY": 0.5,
            "rightX": 0.75,
            "rightY": 0.5,
            "leftTouchX": 0.5,
            "leftTouchY": 0.5,
            "rightTouchX": 0.5,
            "rightTouchY": 0.5,
        }
