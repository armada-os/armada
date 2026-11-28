import hashlib
import json
import os
import re
import stat
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from armada_apps import icons, installers
from armada_apps.catalog import CATALOG_FILE, SCHEMA_VERSION, parse_document
from armada_apps.paths import plugin_dir, state_root

# A host Armada controls, so the storage behind it can change without an
# image update.
DEFAULT_SOURCE = "https://downloads.armadaos.dev/store"
# A branch override reads that branch's file straight from GitHub.
REPO_RAW = "https://raw.githubusercontent.com/armada-os/armada/{branch}/decky/armada-store"

CACHE_FILE = "remote-catalog.json"
OVERRIDE_FILE = "catalog-source"
OS_VERSION_FILE = "/usr/lib/armada/version"

MAX_CATALOG_BYTES = 1 << 20
REQUEST_TIMEOUT = 10.0
REQUEST_DEADLINE = 20.0
# The published file is edge-cached for five minutes, so polling faster than
# that while the Store stays open only spends requests.
OPEN_INTERVAL = 60.0
POLL_INTERVAL = 300.0
THROTTLE_BACKOFF = 900.0

BRANCH_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}")

_lock = threading.Lock()
_refreshing = threading.Lock()
_memo = {"key": None, "value": None}
_gate = {"source": None, "attempt": None, "until": None}


class Unavailable(RuntimeError):
    pass


def _override():
    # Root-owned and not writable by anyone else, or it is ignored: whoever
    # can write it decides what the Store offers.
    path = state_root() / OVERRIDE_FILE
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH) or info.st_size > 4096):
            return None
        with os.fdopen(os.dup(fd), "r", encoding="utf-8") as fh:
            return fh.read().strip() or None
    except (OSError, ValueError):
        return None
    finally:
        os.close(fd)


def parse_source(value):
    """A branch of armada-os/armada, an https base URL, or an absolute local
    directory, as the base that holds the catalog file."""
    value = (value or "").strip()
    if value.startswith("/"):
        return os.path.normpath(value)
    if value.startswith("https://"):
        return value.rstrip("/")
    if BRANCH_RE.fullmatch(value) and ".." not in value.split("/") and "//" not in value:
        return REPO_RAW.format(branch=urllib.parse.quote(value, safe="/"))
    raise ValueError("Not a branch, https URL or absolute directory: " + repr(value))


def source():
    # The env var is for tests; it outranks the override file.
    for value in (os.environ.get("ARMADA_STORE_CATALOG_BASE"), _override()):
        if value:
            try:
                return parse_source(value)
            except ValueError as error:
                print("armada-store: catalog source ignored: {}".format(error))
    return DEFAULT_SOURCE


def _read_local(path, limit):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as error:
        raise Unavailable(str(error))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Unavailable("Not a regular file: " + str(path))
        with os.fdopen(os.dup(fd), "rb") as fh:
            data = fh.read(limit + 1)
    finally:
        os.close(fd)
    if len(data) > limit:
        raise Unavailable("Larger than {} bytes: {}".format(limit, path))
    return data


class Throttled(Unavailable):
    def __init__(self, retry_after):
        super().__init__("Throttled")
        self.retry_after = retry_after


def fetch(base, relpath, limit, etag=None):
    """(bytes, etag), or (None, etag) when the server says nothing changed."""
    if base.startswith("/"):
        return _read_local(os.path.join(base, relpath), limit), None
    url = base + "/" + urllib.parse.quote(relpath)
    if not url.startswith("https://"):
        raise Unavailable("Refusing non-HTTPS catalog URL")
    request = installers._request(url)
    if etag:
        request.add_header("If-None-Match", etag)
    deadline = time.monotonic() + REQUEST_DEADLINE
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT,
                                    context=installers._ssl_context()) as resp:
            if not (resp.geturl() or url).startswith("https://"):
                raise Unavailable("Refusing redirect to non-HTTPS URL")
            sock = getattr(getattr(getattr(resp, "fp", None), "raw", None), "_sock", None)
            chunks, size = [], 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise Unavailable("Timed out reading " + url)
                # The socket timeout only bounds silence, so a server trickling
                # bytes would outlast it; cap each wait by what is left overall.
                if sock is not None:
                    try:
                        sock.settimeout(min(REQUEST_TIMEOUT, remaining))
                    except OSError:
                        sock = None  # closed once the body is in: nothing left to wait on
                chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise Unavailable("Larger than {} bytes: {}".format(limit, url))
                chunks.append(chunk)
            return b"".join(chunks), resp.headers.get("ETag")
    except urllib.error.HTTPError as error:
        if error.code == 304:
            return None, etag
        if error.code in (403, 429):
            try:
                retry = float(error.headers.get("Retry-After") or THROTTLE_BACKOFF)
            except ValueError:
                retry = THROTTLE_BACKOFF
            raise Throttled(max(60.0, retry))
        raise Unavailable("{} for {}".format(error.code, url))
    except (OSError, ValueError) as error:
        if isinstance(error, Unavailable):
            raise
        raise Unavailable(str(error))


def parse_catalog(data):
    return parse_document(data)


def _write_atomic(path, data, mode=0o600):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_CLOEXEC, mode)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read_cache():
    try:
        with open(state_root() / CACHE_FILE, encoding="utf-8") as fh:
            cache = json.load(fh)
    except (OSError, ValueError):
        return None
    if not (isinstance(cache, dict) and isinstance(cache.get("body"), str)
            and isinstance(cache.get("source"), str) and isinstance(cache.get("file"), str)
            and type(cache.get("fetchedAt")) is int and 0 <= cache["fetchedAt"] < 1 << 40
            and isinstance(cache.get("etag"), (str, type(None)))):
        return None
    return cache


def image_build():
    # "YYYYMMDD.<sha>"; anything else (a local "unknown" build) has no date.
    path = os.environ.get("ARMADA_STORE_OS_VERSION_FILE", OS_VERSION_FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            match = re.match(r"(\d{8})(?:\.|$)", fh.read().strip())
    except OSError:
        return None
    return match.group(1) if match else None


def _bundled_path():
    return plugin_dir() / CATALOG_FILE


def _stat_key(path):
    try:
        info = os.stat(path)
        return (info.st_mtime_ns, info.st_size)
    except OSError:
        return None


def bundled():
    try:
        data = _bundled_path().read_bytes()
        return parse_catalog(data), data
    except (OSError, ValueError):
        return {"apps": [], "categories": []}, b""


def _select():
    base = source()
    cache = _read_cache()
    if cache and (cache.get("source") != base or cache.get("file") != CATALOG_FILE):
        cache = None
    if cache:
        build = image_build()
        fetched = time.strftime("%Y%m%d", time.gmtime(cache.get("fetchedAt") or 0))
        # An image newer than the last fetch bundles a newer catalog than that
        # fetch; offline, it wins until a fetch succeeds again.
        if build and fetched < build:
            cache = None
    if cache:
        try:
            body = cache["body"].encode("utf-8")
            doc = parse_catalog(body)
            return {**doc, "origin": "remote", "source": base,
                    "revision": hashlib.sha256(base.encode() + b"\0" + body).hexdigest()[:16]}
        except ValueError:
            pass
    doc, data = bundled()
    return {**doc, "origin": "bundled", "source": base,
            "revision": "bundled-" + hashlib.sha256(data).hexdigest()[:16]}


def active():
    """{"apps", "categories", "origin", "source", "revision"} for the catalog in use. The
    lists are shared; callers must not mutate them."""
    key = (source(), _stat_key(state_root() / CACHE_FILE), _stat_key(_bundled_path()),
           _stat_key(os.environ.get("ARMADA_STORE_OS_VERSION_FILE", OS_VERSION_FILE)))
    with _lock:
        if _memo["key"] == key:
            return _memo["value"]
    value = _select()
    with _lock:
        _memo.update({"key": key, "value": value})
    return value


def refresh():
    """Fetch once now. True when the active catalog changed."""
    base = source()
    cache = _read_cache()
    # The file name too: after an image moves to a new schema, a 304 must not
    # relabel the old file's body as the new one.
    if not (cache and cache.get("source") == base and cache.get("file") == CATALOG_FILE):
        cache = None
    etag = cache.get("etag") if cache else None
    data, etag = fetch(base, CATALOG_FILE, MAX_CATALOG_BYTES, etag)
    if base != source():
        return False  # the override changed mid-fetch; that source gets its own turn
    before = active()["revision"]
    if data is None:
        body = cache["body"]
    else:
        parse_catalog(data)
        body = data.decode("utf-8")
    # Before the switch, so new sections arrive with their icons. A new
    # catalog fetches all of them, since one may have changed under its name;
    # the same catalog again only retries the ones not stored yet.
    done = cache.get("iconsStored") if cache and cache.get("body") == body else None
    done = [n for n in done if isinstance(n, str)] if isinstance(done, list) else []
    try:
        categories = json.loads(body).get("categories") or []
        stored = icons.fetch([c.get("icon") for c in categories if isinstance(c, dict)],
                             lambda name: fetch(base, icons.FOLDER + "/" + name, icons.MAX_ICON_BYTES)[0],
                             done)
    except (ValueError, AttributeError):
        stored = set(done)
    record = {"source": base, "file": CATALOG_FILE, "etag": etag,
              "fetchedAt": int(time.time()), "body": body, "iconsStored": sorted(stored)}
    _write_atomic(state_root() / CACHE_FILE, (json.dumps(record) + "\n").encode("utf-8"))
    return active()["revision"] != before


def opened():
    maybe_refresh(OPEN_INTERVAL)


def maybe_refresh(interval):
    """Start a background fetch when one is due; never blocks the caller."""
    base = source()
    now = time.monotonic()
    with _lock:
        if _gate["until"] is not None and now < _gate["until"]:
            return False
        last = _gate["attempt"]
        if _gate["source"] == base and last is not None and now - last < interval:
            return False
        if not _refreshing.acquire(blocking=False):
            return False
        _gate.update({"source": base, "attempt": now, "until": None})

    def run():
        try:
            refresh()
        except Throttled as error:
            with _lock:
                _gate["until"] = time.monotonic() + error.retry_after
        except (Unavailable, ValueError, OSError) as error:
            print("armada-store: catalog refresh failed: {}".format(error))
        finally:
            _refreshing.release()

    threading.Thread(target=run, name="armada-store-catalog", daemon=True).start()
    return True
