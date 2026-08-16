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


def state_root():
    # Root-owned so state writes never touch user-writable directories.
    env = os.environ.get("ARMADA_STORE_STATE_DIR")
    if env:
        return Path(env)
    return Path("/var/lib/armada-store")


def plugin_dir():
    env = os.environ.get("DECKY_PLUGIN_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]
