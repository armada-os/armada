import json
import os
import pathlib
import re
import stat
import subprocess


SYSTEM_DIR = pathlib.Path("/usr/share/armada/turnip")
# Installed by armada-components; wins over the image's variant of the same name, which
# stays as the fallback. Stable is always the image's.
COMPONENT_DIR = pathlib.Path("/var/lib/armada/components/turnip/current")
DEFAULT_DRIVER = "stable"
USER_PREFIX = "user:"
LIBRARY = "libvulkan_freedreno.so"
FLATPAK_MANIFEST = "flatpak.aarch64.json"
FLATPAK_SYSTEM_DIR = pathlib.Path("/usr/lib/aarch64-linux-gnu/GL/host/turnip")
SAFE_FOLDER_NAME = re.compile(r"[^/:.][^/:]{0,99}")
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


def _variant(name, manifest, image_only=False):
    if not SAFE_FOLDER_NAME.fullmatch(name):
        return None
    for root in (SYSTEM_DIR,) if image_only else (COMPONENT_DIR, SYSTEM_DIR):
        variant = root / name
        if (root == SYSTEM_DIR or name != DEFAULT_DRIVER) and (variant / manifest).is_file() \
                and (variant / "aarch64" / LIBRARY).is_file():
            return variant
    return None


def system_manifests(name):
    variant = _variant(name, "icd.aarch64.json")
    if not variant:
        return None
    # one list for every loader: each skips the manifests it cannot open or load. x86 builds
    # sit at the image's path inside the FEX guest, so a remote variant uses the image's x86.
    return [str(variant / "icd.aarch64.json"),
            *(str(SYSTEM_DIR / name / f"icd.{arch}.json") for arch in ("x86_64", "i686"))]


def flatpak_manifest(name):
    # the manifest's path inside the sandbox; only the image's tree is exposed there
    if not _variant(name, FLATPAK_MANIFEST, image_only=True):
        return None
    return str(FLATPAK_SYSTEM_DIR / name / FLATPAK_MANIFEST)


def flatpak_problem(run, app, libraries, exposed):
    # why the libraries won't all load in app's sandbox (ldd there), or None; -r also
    # finds unversioned symbols the runtime's libraries lack (an older wayland, say)
    probe = [*run, *(f"--filesystem={path}:ro" for path in exposed), "--command=ldd",
             app, "-r", *map(str, libraries)]
    try:
        result = subprocess.run(probe, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"ldd failed: {exc}"
    output = (result.stdout + result.stderr).splitlines()
    missing = list(dict.fromkeys(
        line.split(" (required by ")[0].split("\t(")[0].strip() for line in output
        if "not found" in line or line.startswith("undefined symbol:")))
    if missing:
        return "; ".join(missing)
    if result.returncode:
        return output[-1].strip() if output else f"ldd exited {result.returncode}"
    return None


def user_library(home, name):
    library = user_dir(home) / name / LIBRARY
    if SAFE_FOLDER_NAME.fullmatch(name) and is_arm64_glibc(library):
        return library
    return None


def list_drivers(home):
    drivers = []
    paths = [*SYSTEM_DIR.glob("*/variant.json"), *COMPONENT_DIR.glob("*/variant.json")]
    for path in sorted(paths, key=lambda path: (path.parent.name != DEFAULT_DRIVER, path.parent.name)):
        name = path.parent.name
        owner = SYSTEM_DIR / name if name == DEFAULT_DRIVER else _variant(name, "icd.aarch64.json")
        if path.parent != owner:
            continue
        try:
            with path.open(encoding="utf-8") as f:
                info = json.load(f)
        except (OSError, ValueError):
            info = None
        if not isinstance(info, dict):
            continue
        drivers.append({
            "id": path.parent.name,
            "label": str(info.get("label") or path.parent.name),
            "version": str(info.get("version") or ""),
        })
    if not drivers or drivers[0]["id"] != DEFAULT_DRIVER:
        drivers.insert(0, {"id": DEFAULT_DRIVER, "label": "Stable", "version": ""})
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
