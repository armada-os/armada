import os
import re
import stat
import zipfile

from armada_apps.catalog import DEFAULT_LAUNCH_OPTIONS
from armada_apps.paths import user_ids

from .android import ANDROID_COMPAT_TOOL
from . import android


def _ensure_user_executable(path):
    # Downloaded files often lack the exec bit. Checked and changed through
    # the fd so the ownership test and the chmod cannot race.
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        raise ValueError("File not found: " + path)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Not a regular file: " + path)
        ids = user_ids()
        # Owner-execute only: widening to 0755 would expose a private file.
        if ids and info.st_uid == ids[0] and not info.st_mode & stat.S_IXUSR:
            try:
                os.fchmod(fd, stat.S_IMODE(info.st_mode) | stat.S_IXUSR)
            except OSError:
                pass
    finally:
        os.close(fd)


def prepare_shortcut(path):
    """Validate a user-picked file and return a Steam shortcut spec for it."""
    path = str(path or "")
    if not path.startswith("/"):
        raise ValueError("Enter an absolute path")
    apk = _is_apk(path)
    if apk and not os.path.isdir(android.ANDROID_COMPAT_TOOL_DIR):
        raise ValueError("Android apps are not supported on this image")
    if not apk:
        _ensure_user_executable(path)
    base = path.rsplit("/", 1)[-1]
    name = re.sub(r"\.(appimage|sh|bin|x86_64|aarch64|exe|apk)$", "", base, flags=re.I)
    name = re.sub(r"[-_.]+", " ", name).strip() or base
    spec = {"name": name, "exe": path, "startDir": path.rsplit("/", 1)[0] or "/",
            "launchOptions": DEFAULT_LAUNCH_OPTIONS}
    if apk:
        spec["compatTool"] = ANDROID_COMPAT_TOOL
    return spec


def _is_apk(path):
    if not path.lower().endswith(".apk"):
        return False
    try:
        with zipfile.ZipFile(path) as apk:
            return "AndroidManifest.xml" in apk.namelist()
    except (OSError, zipfile.BadZipFile):
        return False
