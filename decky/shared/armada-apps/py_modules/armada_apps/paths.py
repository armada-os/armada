import os
import pwd
from pathlib import Path


def user_name():
    return os.environ.get("DECKY_USER") or "armada"


def user_home():
    env = os.environ.get("DECKY_USER_HOME")
    if env:
        return Path(env)
    try:
        return Path(pwd.getpwnam(user_name()).pw_dir)
    except KeyError:
        return Path("/var/home") / user_name()


def user_ids():
    try:
        entry = pwd.getpwnam(user_name())
    except KeyError:
        return None
    return entry.pw_uid, entry.pw_gid


def apps_dir():
    return user_home() / "Applications"


def plugins_dir():
    return user_home() / "homebrew/plugins"


# Where each component kind lives under the user's home, one folder per app id.
COMPONENT_PARTS = {
    # Steam reads compatibility tools only from its own root.
    "proton": (".local", "share", "Steam", "compatibilitytools.d"),
    # Must match the user driver folder in /usr/lib/armada/armada_turnip.py.
    "turnip": (".local", "share", "armada", "turnip"),
}


def component_dir(kind):
    return user_home().joinpath(*COMPONENT_PARTS[kind])


def state_root():
    # Root-owned so state writes never touch user-writable directories.
    from .profile import profile
    env = os.environ.get(profile.env + "_STATE_DIR")
    if env:
        return Path(env)
    return Path("/var/lib") / profile.name


def plugin_dir():
    env = os.environ.get("DECKY_PLUGIN_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def bundled_plugins_dir():
    # Where the image keeps the plugins boot sync copies into homebrew.
    env = os.environ.get("ARMADA_BUNDLED_PLUGINS")
    if env:
        return Path(env)
    return Path("/usr/share/decky-plugins")
