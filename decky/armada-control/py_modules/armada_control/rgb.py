from .privileged import call


def rgb_supported():
    try:
        return get_rgb() is not None
    except Exception:
        return False


def get_rgb():
    return call("get_rgb")


def set_rgb(enabled, link_brightness, color, saturation, max_brightness, brightness):
    return call(
        "set_rgb",
        enabled=enabled,
        linkBrightness=link_brightness,
        color=color,
        saturation=saturation,
        maxBrightness=max_brightness,
        brightness=brightness,
    )
