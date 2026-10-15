import hashlib
import json
import logging
import os
import re
import select
import subprocess
import threading
import time
import zipfile
from pathlib import Path

from . import installers, paths, store, userfs
from .proc import clean_env

PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+")
_lock = threading.RLock()
_process = None
_timer = None
_retry_at = 0.0
_retry_reason = "Aurora is unavailable; retry in a minute"
_results = []


def stop(idle_timer=None):
    """Reap the JVM helper; ignore an idle timer superseded by a newer request."""
    global _process, _timer
    with _lock:
        if idle_timer is not None and idle_timer is not _timer:
            return
        if _timer:
            _timer.cancel()
            _timer = None
        if _process:
            process = _process
            _process = None
            try:
                process.kill()
                process.communicate(timeout=5)
            except (OSError, subprocess.TimeoutExpired) as error:
                logging.warning("Aurora helper cleanup failed (%s)", type(error).__name__)
                try:
                    process.wait(timeout=1)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            finally:
                for stream in (process.stdin, process.stdout):
                    if stream:
                        stream.close()


def _read_reply():
    """Read one bounded JSON response with a deadline covering partial lines."""
    deadline = time.monotonic() + 90
    data = bytearray()
    while b"\n" not in data:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([_process.stdout], [], [], remaining)[0]:
            raise TimeoutError()
        chunk = os.read(_process.stdout.fileno(), 65536)
        if not chunk:
            raise EOFError()
        data.extend(chunk)
        if len(data) > 4 * 1024 * 1024:
            raise ValueError("Aurora response is too large")
    reply = json.loads(data)
    if not isinstance(reply, dict):
        raise ValueError("Invalid Aurora response")
    return reply


def request(operation, **arguments):
    """Serialize helper requests, reuse anonymous sessions and back off on upstream failures."""
    global _process, _timer, _retry_at, _retry_reason
    with _lock:
        if time.monotonic() < _retry_at:
            raise RuntimeError(_retry_reason)
        if _timer:
            _timer.cancel()
        if _process is None or _process.poll() is not None:
            stop()
            root = Path(os.environ.get("ARMADA_AURORA_HOME", "/usr/lib/armada-aurora"))
            ids = paths.user_ids()
            try:
                _process = subprocess.Popen(
                    [str(root / "bin/armada-aurora")], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                    env=clean_env({"JAVA_HOME": str(root / "runtime"), "HOME": str(paths.user_home()),
                                   "JAVA_OPTS": "-Xms16m -Xmx128m"}),
                    user=ids[0] if ids else None, group=ids[1] if ids else None,
                )
            except OSError as error:
                logging.error("Aurora helper startup failed (%s, errno %s)", type(error).__name__, error.errno)
                raise RuntimeError("Aurora helper could not start; check the Armada installation") from None
            logging.debug("Aurora helper started")
        try:
            _process.stdin.write(json.dumps({"op": operation, **arguments}) + "\n")
            _process.stdin.flush()
            reply = _read_reply()
        except Exception as error:
            logging.warning("Aurora %s response failed (%s, exit %s)",
                            operation, type(error).__name__, _process.poll())
            stop()
            raise RuntimeError("Aurora did not respond; try again") from None
        timer = _timer = threading.Timer(300, lambda: stop(timer))
        _timer.daemon = True
        _timer.start()
        if reply.get("error"):
            logging.warning("Aurora %s failed: %s%s", operation, reply["error"],
                            f" (HTTP {reply['status']})" if reply.get("status") else "")
            if reply["error"] in ("authentication", "rate_limit"):
                _retry_at = time.monotonic() + 60
                _retry_reason = reply.get("message") or "Aurora is unavailable; retry in a minute"
                if reply["error"] == "authentication":
                    stop()
            raise RuntimeError(reply.get("message") or "Aurora request failed")
        return reply


def app_entry(info):
    """Translate Play metadata into a Store entry, retaining availability restrictions."""
    package = str(info.get("package") or "")
    if not PACKAGE.fullmatch(package):
        raise ValueError("Invalid Android package")
    available = info.get("restriction", "NOT_RESTRICTED") == "NOT_RESTRICTED"
    return {
        "id": "android:" + package, "name": info.get("name") or package,
        "summary": info.get("description") or "", "icon": info.get("icon") or "",
        "category": "android", "canInstall": bool(info.get("free")) and available,
        "note": "Paid apps are not supported" if not info.get("free") else (
            "" if available else "Unavailable for this device or anonymous session"),
        "install": {"type": "android", "package": package},
    }


def search(query, page=None, category=None):
    """Fetch a search/category page and retain metadata for selection and installation."""
    global _results
    reply = request("browse" if category else "search", query=str(query),
                    **({"category": category} if category else {}), **({"page": page} if page else {}))
    entries = [app_entry(info) for info in reply.get("apps", [])]
    if not category:
        query = str(query).strip().casefold()
        entries.sort(key=lambda app: (app["name"].casefold() != query,
                                     not app["name"].casefold().startswith(query)))
    with _lock:
        _results = list({app["id"]: app for app in _results + entries}.values())
    logging.debug("Aurora %s returned %d apps", "browse" if category else "search", len(entries))
    return {"ids": [app["id"] for app in entries], "pages": reply.get("pages", [])}


def apps():
    """Combine session search results with persistent installed and imported entries."""
    entries = {app["id"]: app for app in _results}
    entries.update(store.load_state().get("android") or {})
    return list(entries.values())


def apk_path(app):
    """Locate an imported APK or the base APK of a downloaded package."""
    install = app.get("install") or {}
    return Path(install["path"]) if install.get("path") else (
        paths.apps_dir() / "Android" / install["package"] / "base.apk")


def import_local(path):
    """Validate a standalone APK and queue its Steam shortcut without moving the source."""
    from . import catalog
    if not str(path).lower().endswith(".apk") or not catalog._is_apk(path):
        raise ValueError("Choose a valid standalone APK")
    launch = catalog.prepare_shortcut(path)
    app_id = "android-local:" + hashlib.sha256(os.fsencode(path)).hexdigest()[:24]
    app = {"id": app_id, "name": launch["name"], "category": "android",
           "summary": "Local APK", "canInstall": False,
           "install": {"type": "android", "path": path}}
    store.record_android(app_id, app)
    store.add_pending_shortcut(app_id)
    logging.info("Android local APK shortcut queued: %s", app_id)
    return app_id


def _download_apk(package_fd, package, entry, cancel, progress):
    """Download one APK into staging and return its size only after integrity checks pass."""
    name = entry["name"]
    try:
        with userfs.create_file(package_fd, name) as fh:
            installers.download_to(fh, entry["url"], cancel, progress)
    except installers.Cancelled:
        raise
    except Exception as error:
        logging.warning("Android download failed: %s/%s (%s, HTTP %s)",
                        package, name, type(error).__name__, getattr(error, "code", None))
        raise RuntimeError("APK download failed; try again") from None
    file_path = userfs.proc_path(package_fd, name)
    phase = "checking size of " + name
    try:
        size = os.stat(name, dir_fd=package_fd).st_size
        if size != int(entry.get("size") or 0):
            raise RuntimeError("Incomplete APK download")
        expected = entry.get("sha256")
        phase = "checking checksum of " + name
        if not expected or not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
            raise RuntimeError("APK checksum is unavailable")
        with open(file_path, "rb") as fh:
            if hashlib.file_digest(fh, "sha256").hexdigest() != expected.lower():
                raise RuntimeError("APK checksum mismatch")
        phase = "checking APK contents of " + name
        try:
            with zipfile.ZipFile(file_path) as apk:
                if "AndroidManifest.xml" not in apk.namelist() or apk.testzip():
                    raise RuntimeError("Invalid APK download")
        except zipfile.BadZipFile:
            raise RuntimeError("Invalid APK download") from None
    except Exception as error:
        logging.error("Android APK failed: %s during %s (%s)", package, phase, type(error).__name__)
        raise
    logging.debug("Android APK verified: %s/%s (%d bytes)", package, name, size)
    return size


def _stage_apks(staging_fd, package, files, cancel, progress):
    """Build a verified APK set and Lepton manifest, closing the package directory on every exit."""
    os.mkdir("tree", dir_fd=staging_fd)
    os.mkdir("tree/" + package, dir_fd=staging_fd)
    package_fd = os.open("tree/" + package, os.O_RDONLY | os.O_DIRECTORY, dir_fd=staging_fd)
    try:
        total = sum(int(entry.get("size") or 0) for entry in files)
        completed = 0
        def update(done, size):
            progress(completed + done, total)
        for entry in files:
            if cancel.is_set():
                raise installers.Cancelled()
            completed += _download_apk(package_fd, package, entry, cancel, update)
        # Lepton uses this explicit set to select the base, install splits and detect changes.
        names = ["base.apk"] + sorted(entry["name"] for entry in files if entry["name"] != "base.apk")
        with userfs.create_file(package_fd, ".armada-apks") as fh:
            fh.write(("\n".join(names) + "\n").encode())
        if cancel.is_set():
            raise installers.Cancelled()
        userfs.grant_user_fd(package_fd)
    finally:
        os.close(package_fd)


def install(app, cancel, progress):
    """Download and verify a complete APK set, publish it atomically, then queue its shortcut."""
    package = app["install"]["package"]
    if not PACKAGE.fullmatch(package):
        raise ValueError("Invalid Android package")
    reply = request("resolve", package=package)
    record = app_entry(reply["app"])
    if record["install"]["package"] != package:
        raise RuntimeError("Unexpected Android package in download response")
    record["version"] = reply["app"].get("version") or ""
    files = reply.get("files") or []
    names = [entry.get("name", "") for entry in files]
    if (names.count("base.apk") != 1 or len(names) != len(set(names)) or any(
        not re.fullmatch(r"[A-Za-z0-9_.-]+\.apk", name) for name in names
    ) or sum(entry.get("type") == "BASE" for entry in files) != 1 or any(
        entry.get("type") != ("BASE" if entry.get("name") == "base.apk" else "SPLIT") for entry in files
    )):
        raise RuntimeError("Unsupported APK download")
    logging.info("Android install started: %s (%d APKs)", package, len(files))
    # Keep incomplete downloads private and on the destination filesystem for atomic publication.
    home_fd, staging_name, staging_fd = userfs.make_staging("android")
    dest_fd = None
    preserved = [False]
    phase = "staging"
    try:
        _stage_apks(staging_fd, package, files, cancel, progress)
        phase = "opening destination"
        dest_fd = userfs.open_user_path(("Applications", "Android"), create=True)
        phase = "publishing APK set"
        installers._publish_tree(home_fd, staging_name, staging_fd, dest_fd, package, preserved)
        # State and shortcut work starts only after the complete set has been published.
        phase = "recording installation"
        store.record_android(app["id"], record)
        phase = "queuing Steam shortcut"
        store.add_pending_shortcut(app["id"])
        logging.info("Android install completed: %s", package)
    except installers.Cancelled:
        logging.info("Android install cancelled: %s", package)
        raise
    except Exception as error:
        logging.error("Android install failed: %s during %s (%s)", package, phase, type(error).__name__)
        raise
    finally:
        if dest_fd is not None:
            os.close(dest_fd)
        if preserved[0]:
            logging.warning("Android recovery staging retained: %s", package)
            os.close(staging_fd)
            os.close(home_fd)
        else:
            userfs.cleanup_staging(home_fd, staging_name, staging_fd)


def uninstall(app):
    """Remove Store-managed APKs and state; leave imported source files intact."""
    install = app["install"]
    if not install.get("path"):
        package = install["package"]
        if not PACKAGE.fullmatch(package):
            raise ValueError("Invalid Android package")
        try:
            fd = userfs.open_user_path(("Applications", "Android"))
        except FileNotFoundError:
            pass
        else:
            try:
                userfs.remove_entry(fd, package)
            finally:
                os.close(fd)
    store.clear_android(app["id"])
    logging.info("Android entry removed: %s", app["id"])
