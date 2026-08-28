from .privileged import call


def get_rgb():
    return call("get_rgb")


def set_rgb(enabled, color, brightness):
    return call(
        "set_rgb",
        enabled=enabled,
        color=color,
        brightness=brightness,
    )
