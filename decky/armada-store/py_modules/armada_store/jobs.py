import threading
import time
from collections import OrderedDict

from . import catalog, installers, paths, postinstall, store

ACTIVE_PHASES = {"queued", "resolving", "downloading", "installing", "extracting", "removing"}
DONE_TTL = 10.0
ERROR_TTL = 300.0

_lock = threading.Lock()
_jobs = OrderedDict()
_queue = []
_worker = None


class Job:
    def __init__(self, app_id, action):
        self.app_id = app_id
        self.action = action
        self.phase = "queued"
        self.percent = None
        self.error = ""
        self.finished_at = None
        self.cancel = threading.Event()

    def snapshot(self):
        return {
            "appId": self.app_id,
            "action": self.action,
            "phase": self.phase,
            "percent": self.percent,
            "error": self.error,
        }


def start(app_id, action):
    if action not in ("install", "uninstall", "replace"):
        raise ValueError("Unknown action: " + str(action))
    app = catalog.find_app(app_id)
    if app is None:
        raise ValueError("Unknown app: " + str(app_id))
    global _worker
    with _lock:
        existing = _jobs.get(app_id)
        if existing and existing.phase in ACTIVE_PHASES:
            raise ValueError("Already in progress")
        job = Job(app_id, action)
        _jobs[app_id] = job
        _jobs.move_to_end(app_id)
        _queue.append(app_id)
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_run, name="armada-store-jobs", daemon=True)
            _worker.start()
    return job.snapshot()


def cancel(app_id):
    with _lock:
        job = _jobs.get(app_id)
        if job is None or job.phase not in ACTIVE_PHASES:
            return False
        if job.phase == "queued" and app_id in _queue:
            _queue.remove(app_id)
            job.phase = "cancelled"
            job.finished_at = time.monotonic()
        else:
            job.cancel.set()
    return True


def dismiss(app_id):
    with _lock:
        job = _jobs.get(app_id)
        if job is not None and job.phase not in ACTIVE_PHASES:
            del _jobs[app_id]


def status():
    now = time.monotonic()
    with _lock:
        stale = []
        for app_id, job in _jobs.items():
            if job.finished_at is None:
                continue
            ttl = ERROR_TTL if job.phase == "error" else DONE_TTL
            if now - job.finished_at > ttl:
                stale.append(app_id)
        for app_id in stale:
            del _jobs[app_id]
        return [job.snapshot() for job in _jobs.values()]


def _run():
    global _worker
    while True:
        with _lock:
            if not _queue:
                # Hand off under the lock so start() never sees a dying worker as alive.
                _worker = None
                return
            app_id = _queue.pop(0)
            job = _jobs.get(app_id)
        if job is not None:
            _execute(job)
            job.finished_at = time.monotonic()


# Plugin installs download then extract; each phase reports 0-100 of itself,
# so they are weighted into one bar rather than restarting halfway through.
DOWNLOAD_SPAN = (0, 80)
EXTRACT_SPAN = (80, 100)
FULL_SPAN = (0, 100)


def _scaled(span, done, total):
    if not total:
        return None
    start, end = span
    return min(end, start + (end - start) * min(done, total) // total)


def _download_progress(job, span=FULL_SPAN):
    def update(done, total):
        job.phase = "downloading"
        job.percent = _scaled(span, done, total)
    return update


def _extract_progress(job, span=FULL_SPAN):
    def update(done, total):
        job.phase = "extracting"
        job.percent = _scaled(span, done, total)
    return update


def _execute(job):
    app = catalog.find_app(job.app_id)
    install = (app or {}).get("install") or {}
    kind = install.get("type")
    try:
        if app is None:
            raise RuntimeError("App is no longer in the catalog")
        if job.action in ("install", "replace"):
            _execute_install(job, app, install, kind)
            # After the install, never before: a download that fails partway
            # would otherwise leave the user with neither packaging.
            if job.action == "replace":
                # Before the removal: dying in between must not strand the
                # shortcut on a packaging that is gone.
                store.add_pending_shortcut(job.app_id, force=True)
                _remove_conflicts(job, app)
            postinstall.run(app)
        else:
            _execute_uninstall(job, install, kind)
        job.phase = "done"
        job.percent = None
    except installers.Cancelled:
        job.phase = "cancelled"
        job.percent = None
    except Exception as error:
        job.phase = "error"
        job.percent = None
        job.error = str(error) or error.__class__.__name__


def _remove_conflicts(job, app):
    job.phase = "removing"
    job.percent = None
    for entry in catalog.present_conflicts(app, catalog.flatpak_refs()):
        if entry.get("type") == "flatpak":
            installers.uninstall_flatpak(entry["ref"], job.cancel)
            catalog.invalidate_flatpak_cache()
        elif entry.get("type") == "appimage":
            installers.remove_appimage(entry, None)
            # The entry and the record are keyed by app id, so the replacement
            # packaging does not inherit them.
            installers.remove_desktop_entry(job.app_id)
            store.clear_appimage(job.app_id)
        else:
            raise RuntimeError("Unknown conflict type: " + str(entry.get("type")))


def _execute_install(job, app, install, kind):
    if kind == "flatpak":
        # Indeterminate until the first parsed percent, not a misleading 0%.
        job.phase = "installing"
        job.percent = None

        def on_percent(value):
            job.percent = value

        installers.install_flatpak(install["ref"], job.cancel, on_percent)
        installers.override_flatpak(install["ref"], install.get("overrides"))
        catalog.invalidate_flatpak_cache()
        store.add_pending_shortcut(job.app_id)
    elif kind == "appimage":
        job.phase = "resolving"
        previous = ((store.load_state().get("appimages") or {}).get(job.app_id) or {}).get("filename")
        filename, tag, stamp = installers.install_appimage(install, job.cancel, _download_progress(job))
        store.record_appimage(job.app_id, filename, tag, stamp)
        # A catalog filename change (ES-DE matches emulators by name) would
        # otherwise strand the old download in ~/Applications.
        if previous and previous != filename:
            try:
                installers.remove_appimage({}, {"filename": previous})
            except Exception:
                pass
        # Best-effort: the app is installed and usable from Steam without it.
        try:
            installers.write_desktop_entry(app, str(paths.apps_dir() / filename))
        except Exception as error:
            print("armada-store: desktop entry skipped: {}".format(error))
        # An app with no launch spec can never become a shortcut, so a pending
        # record for it would never clear.
        if catalog.launch_spec(app):
            store.add_pending_shortcut(job.app_id)
    elif kind == "deckyplugin":
        job.phase = "resolving"
        previous = ((store.load_state().get("plugins") or {}).get(job.app_id) or {}).get("dir")
        dirname, tag, stamp = installers.install_decky_plugin(
            install,
            job.cancel,
            _download_progress(job, DOWNLOAD_SPAN),
            _extract_progress(job, EXTRACT_SPAN),
        )
        store.record_plugin(job.app_id, dirname, tag, stamp)
        if previous and previous != dirname:
            try:
                installers.remove_decky_plugin({"dir": previous})
            except Exception:
                pass
        if previous:
            installers.restart_decky()
    else:
        raise RuntimeError("Unknown install type: " + str(kind))


def _execute_uninstall(job, install, kind):
    job.phase = "removing"
    store.clear_pending_shortcut(job.app_id)
    state = store.load_state()
    if kind == "flatpak":
        installers.uninstall_flatpak(install["ref"], job.cancel)
        catalog.invalidate_flatpak_cache()
    elif kind == "appimage":
        installers.remove_appimage(install, (state.get("appimages") or {}).get(job.app_id))
        installers.remove_desktop_entry(job.app_id)
        store.clear_appimage(job.app_id)
    elif kind == "deckyplugin":
        installers.remove_decky_plugin((state.get("plugins") or {}).get(job.app_id))
        store.clear_plugin(job.app_id)
    else:
        raise RuntimeError("Unknown install type: " + str(kind))
