from .privileged import call


def rgb_supported():
    try:
        return get_rgb() is not None
    except Exception:
        return False


def get_rgb():
    return call("get_rgb")


def set_rgb(enabled, color, brightness):
    return call(
        "set_rgb",
        enabled=enabled,
        color=color,
        brightness=brightness,
    )
