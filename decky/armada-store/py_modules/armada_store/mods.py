import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from . import installers, paths, userfs
from .proc import clean_env

TOOL = Path(__file__).with_name("modtool.py")
CACHE_PARTS = (".cache", "armada-mods")
DOWNLOAD_NAME = "store-download.tar.gz"

RELEASES_TTL = 60.0
MAX_RELEASE_PAGES = 10

_lock = threading.Lock()
_cache = {"at": None, "mods": {}}
_releases = {}


# The mods folder belongs to the user, so everything that touches it runs as
# the user: nothing there can redirect a root write.
def _tool(*args, timeout=300):
    env = clean_env({"HOME": str(paths.user_home())})
    for name in ("XDG_CACHE_HOME", "XDG_DATA_HOME"):
        env.pop(name, None)
    argv = ["/usr/bin/python3", "-I", str(TOOL), *args]
    if os.geteuid() == 0:
        argv = ["runuser", "-u", paths.user_name(), "--", *argv]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
    if result.returncode != 0:
        lines = result.stderr.strip().splitlines()
        raise RuntimeError(lines[-1] if lines else "mod tool failed")
    return result.stdout


def invalidate():
    _cache["at"] = None


def installed(max_age=5.0):
    """Installed mods by id, however they got there."""
    with _lock:
        if _cache["at"] is None or time.monotonic() - _cache["at"] > max_age:
            try:
                _cache["mods"] = {mod["id"]: mod for mod in json.loads(_tool("list", timeout=30))}
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
                pass
            _cache["at"] = time.monotonic()
        return _cache["mods"]


def apps(known):
    """Catalog entries for installed mods the bundled catalog does not list."""
    return [{"id": mod["id"], "name": mod["name"], "summary": mod["summary"], "category": "mods",
             "canInstall": False,
             "install": {"type": "gamemod", "steamAppids": mod["steamAppids"]}}
            for mod in installed().values() if mod["id"] not in known]


def version_key(version):
    return [int(part) if part.isdigit() else -1 for part in re.split(r"[.+-]", version or "")]


# Every mod of a repository is looked up in the same release list, so one
# fetch serves a whole refresh.
def _release_assets(releases_url):
    cached = _releases.get(releases_url)
    if cached and time.monotonic() - cached[0] <= RELEASES_TTL:
        return cached[1]
    assets, url = [], releases_url
    for _ in range(MAX_RELEASE_PAGES):
        with installers.urllib.request.urlopen(installers._request(url), timeout=30,
                                               context=installers._ssl_context()) as resp:
            data = json.load(resp)
            following = re.search(r'<([^>]+)>;\s*rel="next"', resp.headers.get("Link") or "")
        for release in [data] if isinstance(data, dict) else data:
            if not (release.get("draft") or release.get("prerelease")):
                assets += [(asset.get("name") or "", asset.get("browser_download_url"))
                           for asset in release.get("assets") or []]
        if not following:
            break
        url = following.group(1)
    _releases[releases_url] = (time.monotonic(), assets)
    return assets


def latest(app_id, install_spec):
    """Version and URL of a mod's highest published version, wherever in the release history it sits."""
    pattern, prefix = re.compile(install_spec["asset"]), app_id + "-"
    found = [(name[len(prefix):-len(".tar.gz")], url)
             for name, url in _release_assets(install_spec["releases"]) if url and pattern.search(name)]
    if not found:
        raise RuntimeError("No release of this mod has been published")
    return max(found, key=lambda entry: version_key(entry[0]))


def install(app_id, install_spec, cancel, progress):
    _, url = latest(app_id, install_spec)
    cache_fd = userfs.open_user_path(list(CACHE_PARTS), create=True)
    try:
        with userfs.create_file(cache_fd, DOWNLOAD_NAME, 0o600) as fh:
            installers.download_to(fh, url, cancel, progress)
        _tool("install", str(paths.user_home().joinpath(*CACHE_PARTS, DOWNLOAD_NAME)), app_id)
    finally:
        userfs.unlink(cache_fd, DOWNLOAD_NAME)
        os.close(cache_fd)
        invalidate()


def add_local(path):
    path = str(path or "")
    if not path.startswith("/") or not path.lower().endswith((".tar.gz", ".tgz")):
        raise ValueError("Choose a mod .tar.gz file")
    try:
        return json.loads(_tool("install", path))["id"]
    finally:
        invalidate()


def remove(mod_id):
    try:
        _tool("remove", mod_id)
    finally:
        invalidate()
