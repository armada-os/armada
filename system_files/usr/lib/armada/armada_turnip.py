import json
import os
import pathlib
import re
import stat


SYSTEM_DIR = pathlib.Path("/usr/share/armada/turnip")
# The system Mesa; selecting it overrides nothing.
STABLE = "stable"
USER_PREFIX = "user:"
LIBRARY = "libvulkan_freedreno.so"
# Any folder name that cannot break a path or the colon-separated manifest list.
NAME = re.compile(r"[^/:.][^/:]{0,99}")
MAX_LIBRARY_SIZE = 256 * 1024 * 1024


def user_dir(home):
    return pathlib.Path(home) / ".local" / "share" / "armada" / "turnip"


def _read_regular(path, limit):
    # Runs as root over a user-writable tree: never block, follow a link, or read unbounded.
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            return None
        with os.fdopen(os.dup(fd), "rb") as f:
            return f.read(limit)
    except OSError:
        return None
    finally:
        os.close(fd)


def is_arm64_glibc(path):
    # An Android build ships under the same file name and would leave a game with no driver.
    data = _read_regular(path, MAX_LIBRARY_SIZE)
    return (data is not None and len(data) >= 64 and data[:5] == b"\x7fELF\x02"
            and data[18:20] == b"\xb7\x00" and b"libc.so.6\0" in data)


def system_manifests(name):
    variant = SYSTEM_DIR / name
    if not (NAME.fullmatch(name) and (variant / "icd.aarch64.json").is_file()
            and (variant / "aarch64" / LIBRARY).is_file()):
        return None
    # one list for every loader: each skips the manifests it cannot open or load
    return [str(variant / f"icd.{arch}.json") for arch in ("aarch64", "x86_64", "i686")]


def user_library(home, name):
    library = user_dir(home) / name / LIBRARY
    if NAME.fullmatch(name) and is_arm64_glibc(library):
        return library
    return None


def list_drivers(home):
    drivers = []
    for path in sorted(SYSTEM_DIR.glob("*/variant.json"),
                       key=lambda path: (path.parent.name != STABLE, path)):
        name = path.parent.name
        try:
            with path.open(encoding="utf-8") as f:
                info = json.load(f)
        except (OSError, ValueError):
            info = None
        if not isinstance(info, dict) or not (name == STABLE or system_manifests(name)):
            continue
        drivers.append({
            "id": path.parent.name,
            "label": str(info.get("label") or path.parent.name),
            "version": str(info.get("version") or ""),
        })
    if not drivers or drivers[0]["id"] != STABLE:
        drivers.insert(0, {"id": STABLE, "label": "Stable", "version": ""})
    for path in sorted(user_dir(home).glob(f"*/{LIBRARY}")):
        name = path.parent.name
        if not user_library(home, name):
            continue
        try:
            label = json.loads(_read_regular(path.parent / "meta.json", 65536)).get("name")
        except (TypeError, ValueError, AttributeError):
            label = None
        drivers.append({
            "id": USER_PREFIX + name,
            "label": label if isinstance(label, str) and label else name,
            "version": "",
        })
    return drivers
