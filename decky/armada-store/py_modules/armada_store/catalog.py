import json
import os
import re
import stat
import subprocess
import threading
import time

from . import store
from .proc import clean_env
from .paths import apps_dir, plugin_dir, plugins_dir, user_home, user_ids


_flatpak_cache = {"at": 0.0, "refs": set()}
_flatpak_refresh = threading.Lock()
LAUNCH_WRAPPER = "/usr/libexec/armada/armada-game-launch"
COMMAND_TOKEN = "%command%"
DEFAULT_LAUNCH_OPTIONS = f"{LAUNCH_WRAPPER} {COMMAND_TOKEN}"


def bundled_apps():
    try:
        with open(plugin_dir() / "catalog.json", encoding="utf-8") as fh:
            apps = json.load(fh).get("apps", [])
            return apps if isinstance(apps, list) else []
    except (OSError, ValueError):
        return []


def all_apps():
    return bundled_apps()


def find_app(app_id):
    for app in all_apps():
        if app.get("id") == app_id:
            return app
    return None


def flatpak_refs(max_age=3.0):
    if time.monotonic() - _flatpak_cache["at"] <= max_age:
        return _flatpak_cache["refs"]
    # One refresher at a time; concurrent callers get the stale copy instead
    # of stacking up flatpak subprocesses behind a slow call.
    if not _flatpak_refresh.acquire(blocking=False):
        return _flatpak_cache["refs"]
    try:
        result = subprocess.run(
            ["flatpak", "list", "--system", "--app", "--columns=application"],
            capture_output=True,
            text=True,
            timeout=15,
            env=clean_env(),
        )
        _flatpak_cache["refs"] = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    except (OSError, subprocess.TimeoutExpired):
        pass
    finally:
        # Stamp even on failure so a broken flatpak backs off instead of hammering.
        _flatpak_cache["at"] = time.monotonic()
        _flatpak_refresh.release()
    return _flatpak_cache["refs"]


def invalidate_flatpak_cache():
    _flatpak_cache["at"] = 0.0


def installed_info(app, state, refs):
    install = app.get("install") or {}
    kind = install.get("type")
    if kind == "flatpak":
        return {"installed": install.get("ref") in refs}
    if kind == "appimage":
        record = (state.get("appimages") or {}).get(app.get("id")) or {}
        filename = install.get("filename") or record.get("filename")
        installed = bool(filename and (apps_dir() / filename).exists())
        info = {"installed": installed}
        if installed and record.get("tag"):
            info["version"] = record["tag"]
        return info
    if kind == "system":
        return {"installed": bool(install.get("exec")) and os.path.exists(install["exec"])}
    if kind == "deckyplugin":
        record = (state.get("plugins") or {}).get(app.get("id")) or {}
        dirname = record.get("dir")
        installed = bool(dirname and "/" not in dirname and (plugins_dir() / dirname).exists())
        info = {"installed": installed}
        if installed and record.get("tag"):
            info["version"] = record["tag"]
        return info
    return {"installed": False}


def _conflict_present(entry, refs):
    kind = entry.get("type")
    if kind == "flatpak":
        return bool(entry.get("ref")) and entry["ref"] in refs
    if kind == "appimage":
        filename = entry.get("filename")
        return bool(filename and (apps_dir() / filename).exists())
    return False


def present_conflicts(app, refs):
    """Rival packagings of the same app that are actually on the system."""
    return [entry for entry in (app.get("conflicts") or []) if _conflict_present(entry, refs)]


def installed_map():
    state = store.load_state()
    refs = flatpak_refs()
    result = {}
    for app in all_apps():
        app_id = app.get("id")
        if not app_id:
            continue
        info = installed_info(app, state, refs)
        conflicts = present_conflicts(app, refs)
        if conflicts:
            info["conflicts"] = conflicts
        result[app_id] = info
    return result


def wrap_launch_options(options):
    options = str(options or "").strip()
    if LAUNCH_WRAPPER in options:
        return options
    if COMMAND_TOKEN in options:
        return options.replace(COMMAND_TOKEN, DEFAULT_LAUNCH_OPTIONS, 1)
    return " ".join(filter(None, (DEFAULT_LAUNCH_OPTIONS, options)))


def launch_spec(app):
    install = app.get("install") or {}
    kind = install.get("type")
    if app.get("desktopOnly"):
        return None
    home = str(user_home())
    name = app.get("name") or app.get("id") or "App"
    extra = (install.get("launchOptions") or "").strip()
    if kind == "flatpak" and install.get("ref"):
        options = " ".join(filter(None, ("run " + install["ref"], extra)))
        return {"name": name, "exe": "/usr/bin/flatpak", "startDir": home,
                "launchOptions": wrap_launch_options(options)}
    if kind == "appimage" and install.get("filename"):
        return {"name": name, "exe": str(apps_dir() / install["filename"]),
                "startDir": str(apps_dir()), "launchOptions": wrap_launch_options(extra)}
    if kind == "system" and install.get("exec"):
        return {"name": name, "exe": install["exec"],
                "startDir": os.path.dirname(install["exec"]),
                "launchOptions": wrap_launch_options(extra)}
    return None


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


def catalog_payload():
    apps = []
    for app in all_apps():
        install = app.get("install") or {}
        apps.append({
            "id": app.get("id") or "",
            "name": app.get("name") or "",
            "summary": app.get("summary") or "",
            "category": app.get("category") or "",
            "icon": app.get("icon") or "",
            "note": app.get("note") or "",
            "installType": install.get("type") or "",
            "desktopOnly": bool(app.get("desktopOnly")),
            "launch": launch_spec(app),
        })
    return {"apps": apps, "home": str(user_home())}


def prepare_shortcut(path):
    """Validate a user-picked file and return a Steam shortcut spec for it."""
    path = str(path or "")
    if not path.startswith("/"):
        raise ValueError("Enter an absolute path")
    _ensure_user_executable(path)
    base = path.rsplit("/", 1)[-1]
    name = re.sub(r"\.(appimage|sh|bin|x86_64|aarch64|exe)$", "", base, flags=re.I)
    name = re.sub(r"[-_.]+", " ", name).strip() or base
    return {"name": name, "exe": path, "startDir": path.rsplit("/", 1)[0] or "/",
            "launchOptions": DEFAULT_LAUNCH_OPTIONS}
