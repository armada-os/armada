"""Category icons: monochrome SVGs the panel draws as masks in the text color.

A catalog names each icon by its file name in the icons folder next to the
catalog. A copy fetched with the current catalog is used first, then the
plugin's own. The panel gets data: URIs, which masks accept without CORS and
which work offline."""
import base64
import os
import re

from .paths import plugin_dir, state_root

MAX_ICON_BYTES = 16384
FOLDER = "icons"
ICON_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\.svg")


def name_problem(name):
    """Why a catalog icon name is unusable, or None."""
    if not (isinstance(name, str) and ICON_NAME.fullmatch(name)):
        return "bad icon"
    return None


def svg_problem(data):
    """Why these bytes can't be used as an icon, or None."""
    if len(data) > MAX_ICON_BYTES:
        return "larger than {} bytes".format(MAX_ICON_BYTES)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "not UTF-8"
    # Never parsed as XML (entity expansion); used only as an image mask,
    # where scripts and external references do not run.
    if "<!DOCTYPE" in text or "<!ENTITY" in text or "<svg" not in text:
        return "not a plain SVG"
    return None


def _cache_path(name):
    return state_root() / FOLDER / name


def _read(file):
    try:
        with open(file, "rb") as fh:
            return fh.read(MAX_ICON_BYTES + 1)
    except OSError:
        return None


def load(name):
    """The icon's bytes, or None."""
    if name_problem(name):
        return None
    for file in (_cache_path(name), plugin_dir() / FOLDER / name):
        data = _read(file)
        if data is not None and not svg_problem(data):
            return data
    return None


def data_uri(name):
    data = load(name)
    if data is None:
        return ""
    return "data:image/svg+xml;base64," + base64.b64encode(data).decode("ascii")


def fetch(names, fetch_one, done=()):
    """Fetch the icons not in done with fetch_one(name) -> bytes and keep the
    ones that check out; a failure keeps what is there. Returns done plus what
    was stored, so a catalog's icons are each fetched once, failures retried."""
    stored = set(done)
    for name in names:
        if name_problem(name) or name in stored:
            continue
        try:
            data = fetch_one(name)
        except Exception as error:
            print("icon {} unavailable: {}".format(name, error))
            continue
        problem = svg_problem(data or b"")
        if problem:
            print("icon {} refused: {}".format(name, problem))
            continue
        _store(name, data)
        stored.add(name)
    return stored


def _store(name, data):
    file = _cache_path(name)
    file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = file.with_name("." + file.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.replace(tmp, file)
