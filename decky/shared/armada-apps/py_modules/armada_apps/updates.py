import subprocess
import threading
import time
import urllib.error

from . import catalog, records
from .proc import clean_env
from .installers import resolve_release

TTL = 3600.0
# Where each release-fed install type keeps its records.
RELEASE_BUCKETS = {"appimage": "appimages", "deckyplugin": "plugins", "proton": "components", "turnip": "components"}

_lock = threading.Lock()
# at=None, not 0.0: monotonic() is seconds since boot, so a zero epoch would
# make the first check look fresh (and skip) on a recently booted device.
_cache = {"at": None, "flatpak": {}, "tags": {}, "stamps": {}}


def _release_key(install):
    # Keyed by where the release comes from, so a catalog change to an app's
    # feed or asset never compares against the old feed's tag.
    return "\n".join(install.get(key) or "" for key in ("releases", "asset", "checksum"))


def _lookup(install):
    """(tag, stamp), ("", "") when the feed has no matching release, or None
    when it could not be asked."""
    try:
        # The same pick an install makes, checksum file included, so a
        # release still missing it is not offered.
        tag, _, stamp, _ = resolve_release(install["releases"], install["asset"], install.get("checksum"))
    except urllib.error.HTTPError as error:
        # A feed with no release yet is an answer; retrying it on every check
        # would keep the cache cold and spend the API rate limit.
        return ("", "") if error.code == 404 else None
    except RuntimeError:
        return ("", "")
    except Exception:
        return None
    return tag, stamp


def _installed_release_apps(apps, state, refs):
    found = []
    for app in apps:
        install = app.get("install") or {}
        if install.get("type") in RELEASE_BUCKETS and install.get("releases"):
            if catalog.installed_info(app, state, refs).get("installed"):
                found.append(app)
    return found


def _refresh(apps, state, refs, force):
    release_apps = _installed_release_apps(apps, state, refs)
    fresh = not force and _cache["at"] is not None and time.monotonic() - _cache["at"] <= TTL
    if fresh:
        # Within the TTL, look up only feeds a catalog change has just added.
        missing = [app for app in release_apps if _release_key(app["install"]) not in _cache["tags"]]
        if missing:
            tags, stamps = dict(_cache["tags"]), dict(_cache["stamps"])
            for app in missing:
                found = _lookup(app["install"])
                if found is None:
                    continue
                tag, stamp = found
                key = _release_key(app["install"])
                tags[key] = tag
                if stamp:
                    stamps[key] = stamp
            _cache.update({"tags": tags, "stamps": stamps})
        return
    # A failed lookup must never cache as "nothing to update", so the TTL
    # starts only when every source answered.
    complete = True
    try:
        result = subprocess.run(
            ["flatpak", "remote-ls", "--updates", "--system", "--app", "--columns=application,version", "flathub"],
            capture_output=True,
            text=True,
            timeout=60,
            env=clean_env(),
        )
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or "flatpak remote-ls failed")
        flatpak_updates = catalog.parse_flatpak_columns(result.stdout)
    except (OSError, subprocess.TimeoutExpired):
        complete = False
        flatpak_updates = dict(_cache["flatpak"])
    tags = dict(_cache["tags"])
    stamps = dict(_cache["stamps"])
    for app in release_apps:
        install = app["install"]
        found = _lookup(install)
        if found is None:
            complete = False
            continue
        tag, stamp = found
        tags[_release_key(install)] = tag
        if stamp:
            stamps[_release_key(install)] = stamp
    _cache.update({"at": time.monotonic() if complete else None, "flatpak": flatpak_updates,
                   "tags": tags, "stamps": stamps})


def available(force=False):
    # Only the network half is cached; the comparison reruns every call so a
    # just-installed update clears its badge without another fetch.
    state = records.load_state()
    refs = catalog.flatpak_refs()
    # One snapshot of the catalog for the whole check; retired entries are
    # only kept for removal, never updated.
    apps = [app for app in catalog.all_apps() if not app.get("retired")]
    with _lock:
        _refresh(apps, state, refs, force)
        flatpak_updates = dict(_cache["flatpak"])
        tags = dict(_cache["tags"])
        stamps = dict(_cache["stamps"])
    updates = {}
    for app in apps:
        app_id = app.get("id")
        install = app.get("install") or {}
        kind = install.get("type")
        if kind == "flatpak":
            ref = install.get("ref")
            if ref in refs and ref in flatpak_updates:
                updates[app_id] = {"latest": flatpak_updates[ref]}
        elif kind in RELEASE_BUCKETS:
            info = catalog.installed_info(app, state, refs)
            if not info.get("installed"):
                continue
            key = _release_key(install)
            if kind == "deckyplugin" and install.get("dir"):
                # Seeded by the image, so there is no record: the installed
                # package.json against the release tag, newer only.
                current = catalog.parse_version(info.get("version"))
                latest = catalog.parse_version((tags.get(key) or "").lstrip("v"))
                if current and latest and latest > current:
                    updates[app_id] = {"latest": catalog.version_label(app, tags.get(key) or "")}
                continue
            record = (state.get(RELEASE_BUCKETS[kind]) or {}).get(app_id) or {}
            current, latest = record.get("stamp") or "", stamps.get(key) or ""
            if not (current and latest):
                # A mutable tag like "nightly" never changes, so the release
                # date is the only signal; fall back for pre-stamp records.
                current, latest = info.get("version") or "", tags.get(key) or ""
            if latest and current and latest != current:
                updates[app_id] = {"latest": catalog.version_label(app, tags.get(key) or ""),
                                   "date": stamps.get(key) or ""}
    return updates
