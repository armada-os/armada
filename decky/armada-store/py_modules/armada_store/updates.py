import subprocess
import threading
import time

from . import catalog, store
from .proc import clean_env
from .installers import resolve_release_asset

TTL = 3600.0

_lock = threading.Lock()
# at=None, not 0.0: monotonic() is seconds since boot, so a zero epoch would
# make the first check look fresh (and skip) on a recently booted device.
_cache = {"at": None, "flatpak": set(), "tags": {}, "stamps": {}}


def _installed_release_apps(state, refs):
    apps = []
    for app in catalog.all_apps():
        install = app.get("install") or {}
        if install.get("type") in ("appimage", "deckyplugin") and install.get("releases"):
            if catalog.installed_info(app, state, refs).get("installed"):
                apps.append(app)
    return apps


def _refresh(state, refs, force):
    if not force and _cache["at"] is not None and time.monotonic() - _cache["at"] <= TTL:
        return
    # A failed lookup must never cache as "nothing to update", so the TTL
    # starts only when every source answered.
    complete = True
    try:
        result = subprocess.run(
            ["flatpak", "remote-ls", "--updates", "--system", "--app", "--columns=application", "flathub"],
            capture_output=True,
            text=True,
            timeout=60,
            env=clean_env(),
        )
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or "flatpak remote-ls failed")
        flatpak_updates = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    except (OSError, subprocess.TimeoutExpired):
        complete = False
        flatpak_updates = set(_cache["flatpak"])
    tags = dict(_cache["tags"])
    stamps = dict(_cache["stamps"])
    for app in _installed_release_apps(state, refs):
        install = app["install"]
        try:
            tag, _, stamp = resolve_release_asset(install["releases"], install["asset"])
        except Exception:
            complete = False
            continue
        if tag:
            tags[app["id"]] = tag
        if stamp:
            stamps[app["id"]] = stamp
    _cache.update({"at": time.monotonic() if complete else None, "flatpak": flatpak_updates,
                   "tags": tags, "stamps": stamps})


def available(force=False):
    # Only the network half is cached; the comparison reruns every call so a
    # just-installed update clears its badge without another fetch.
    state = store.load_state()
    refs = catalog.flatpak_refs()
    with _lock:
        _refresh(state, refs, force)
        flatpak_updates = set(_cache["flatpak"])
        tags = dict(_cache["tags"])
        stamps = dict(_cache["stamps"])
    updates = {}
    for app in catalog.all_apps():
        app_id = app.get("id")
        install = app.get("install") or {}
        kind = install.get("type")
        if kind == "flatpak":
            ref = install.get("ref")
            if ref in refs and ref in flatpak_updates:
                updates[app_id] = {"latest": ""}
        elif kind in ("appimage", "deckyplugin"):
            info = catalog.installed_info(app, state, refs)
            if not info.get("installed"):
                continue
            bucket = "appimages" if kind == "appimage" else "plugins"
            record = (state.get(bucket) or {}).get(app_id) or {}
            current, latest = record.get("stamp") or "", stamps.get(app_id) or ""
            if not (current and latest):
                # A mutable tag like "nightly" never changes, so the release
                # date is the only signal; fall back for pre-stamp records.
                current, latest = info.get("version") or "", tags.get(app_id) or ""
            if latest and current and latest != current:
                updates[app_id] = {"latest": tags.get(app_id) or ""}
    return updates
