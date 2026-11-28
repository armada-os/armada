import json
import os
import re
import subprocess
import threading
import time

from . import icons, records
from .proc import clean_env
from .profile import profile
from .paths import apps_dir, bundled_plugins_dir, component_dir, plugin_dir, plugins_dir, user_home


_flatpak_cache = {"at": 0.0, "refs": set(), "versions": {}}
_flatpak_refresh = threading.Lock()
LAUNCH_WRAPPER = "/usr/libexec/armada/armada-game-launch"
COMMAND_TOKEN = "%command%"
DEFAULT_LAUNCH_OPTIONS = f"{LAUNCH_WRAPPER} {COMMAND_TOKEN}"

SCHEMA_VERSION = 1
# The Store's remote catalog. A breaking format change publishes
# catalog-v2.json beside this one, so Stores that shipped keep getting
# updates from the file they understand.
CATALOG_FILE = "catalog-v{}.json".format(SCHEMA_VERSION)
# A catalog that ships inside its plugin always matches the code reading it.
BUNDLED_CATALOG_FILE = "catalog.json"


# What this Store can handle. A remote catalog may name newer ones; those
# entries stay hidden until an image ships a Store that knows them.
INSTALL_TYPES = ("flatpak", "appimage", "system", "deckyplugin", "proton", "turnip")
# Downloaded from a release feed and unpacked into a folder named after the app id.
COMPONENT_TYPES = ("proton", "turnip")
CONFLICT_TYPES = ("flatpak", "appimage")
# The fields each install type may carry. Anything else hides the entry: an
# unknown field there could change what gets installed or removed.
INSTALL_FIELDS = {
    # version: a pattern whose first group is the part of a release tag shown
    # as the version. path: the folder inside the archive holding the tool or
    # driver.
    "flatpak": {"type", "ref", "overrides", "launchOptions"},
    "appimage": {"type", "releases", "asset", "checksum", "version", "filename", "launchOptions"},
    "system": {"type", "exec", "launchOptions"},
    "deckyplugin": {"type", "releases", "asset", "checksum", "version", "dir"},
    "proton": {"type", "releases", "asset", "checksum", "version", "path"},
    "turnip": {"type", "releases", "asset", "checksum", "version", "path"},
}
CONFLICT_FIELDS = {"flatpak": {"type", "ref"}, "appimage": {"type", "filename"}}
# Where retired apps go when their own section is gone.
OTHER_CATEGORY = "other"
CATEGORY_LANGUAGES = ("en", "zh-CN")

# No ":" so catalog ids can never collide with "android:" and "android-local:".
APP_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
# One path component the Store creates or reads: no separators, no "." or "..".
SAFE_NAME = re.compile(r"[A-Za-z0-9_+@-][A-Za-z0-9._+@ -]{0,127}")
# A Flatpak application ID; anything else (say "--all") would reach the
# flatpak command line as an option.
FLATPAK_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+)+")
VERSION = re.compile(r"\d{1,6}(\.\d{1,6}){0,3}")


def parse_version(value):
    """A plain dotted version as a comparable tuple, trailing zeros dropped so
    0.2 equals 0.2.0; None when it is not one."""
    if not (isinstance(value, str) and VERSION.fullmatch(value)):
        return None
    parts = [int(part) for part in value.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def _read_version(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return parse_version(json.load(fh).get("version"))
    except (OSError, ValueError, AttributeError):
        return None


_store_version = []


def parse_document(data):
    """{"apps", "categories"}. Only the envelope is checked here; entries are
    judged one by one, so one bad entry never hides the rest."""
    try:
        doc = json.loads(data)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("catalog is not JSON: {}".format(error))
    if not isinstance(doc, dict):
        raise ValueError("catalog is not an object")
    # type() rather than ==: True and 1.0 both equal 1.
    if type(doc.get("schemaVersion")) is not int or doc["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("catalog schemaVersion is not {}".format(SCHEMA_VERSION))
    apps, categories = doc.get("apps"), doc.get("categories")
    if not isinstance(apps, list) or not isinstance(categories, list):
        raise ValueError("catalog has no app or category list")
    for items, what in ((apps, "app"), (categories, "category")):
        ids = [item["id"] for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]
        if len(ids) != len(set(ids)):
            raise ValueError("catalog has duplicate {} ids".format(what))
    return {"apps": apps, "categories": categories}


class BundledSource:
    """The catalog shipped inside the plugin, for plugins that update as a
    whole rather than fetching their catalog."""

    def __init__(self, path=None):
        self.path = path

    def bundled(self):
        data = (self.path or plugin_dir() / BUNDLED_CATALOG_FILE).read_bytes()
        return parse_document(data), data

    def active(self):
        import hashlib
        try:
            doc, data = self.bundled()
        except (OSError, ValueError) as error:
            print("{}: bundled catalog unusable: {}".format(profile.name, error))
            doc, data = {"apps": [], "categories": []}, b""
        return {**doc, "revision": "bundled-" + hashlib.sha256(data).hexdigest()[:16]}


def store_version():
    if not _store_version:
        _store_version.append(_read_version(plugin_dir() / "package.json") or (0,))
    return _store_version[0]


def _too_new(item):
    """Why an item's minStoreVersion hides it here, or None."""
    if "minStoreVersion" not in item:
        return None
    minimum = parse_version(item["minStoreVersion"])
    if minimum is None:
        return "bad minStoreVersion"
    if minimum > store_version():
        return "needs Store " + item["minStoreVersion"]
    return None


def _str(value, required=False):
    return isinstance(value, str) and (bool(value) or not required)


def _safe_name(value):
    return isinstance(value, str) and bool(SAFE_NAME.fullmatch(value)) and value not in (".", "..")


def _flatpak_id(value):
    return isinstance(value, str) and bool(FLATPAK_ID.fullmatch(value))


def _safe_path(value):
    """A relative path of SAFE_NAME parts, at most eight deep."""
    if not isinstance(value, str):
        return False
    parts = value.split("/")
    return 0 < len(parts) <= 8 and all(_safe_name(part) for part in parts)


def _https(value):
    return isinstance(value, str) and value.startswith("https://")


def _valid_install(install):
    kind = install.get("type")
    if not _str(install.get("launchOptions")) and install.get("launchOptions") is not None:
        return False
    if kind == "flatpak":
        overrides = install.get("overrides")
        return _flatpak_id(install.get("ref")) and (
            overrides is None or (isinstance(overrides, list)
                                  and all(_str(o, True) and o.startswith("--") for o in overrides)))
    if kind in ("appimage", "deckyplugin", *COMPONENT_TYPES):
        if not (_https(install.get("releases")) and _str(install.get("asset"), True)):
            return False
        for key in ("checksum", "version"):
            if install.get(key) is not None and not _str(install[key], True):
                return False
        try:
            re.compile(install["asset"])
            re.compile(install.get("checksum") or "")
            if install.get("version") is not None and re.compile(install["version"]).groups < 1:
                return False
        except re.error:
            return False
        if kind == "deckyplugin":
            return install.get("dir") is None or _safe_name(install["dir"])
        if kind in COMPONENT_TYPES:
            return install.get("path") is None or _safe_path(install["path"])
        return _safe_name(install.get("filename"))
    if kind == "system":
        return _str(install.get("exec"), True) and install["exec"].startswith("/")
    return True  # an unknown type: unsupported, not malformed


def _executable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def category_problem(category):
    """Why a catalog category can't be shown here, or None."""
    if not isinstance(category, dict):
        return "not an object"
    if not (isinstance(category.get("id"), str) and APP_ID.fullmatch(category["id"])):
        return "bad id"
    if category["id"] == OTHER_CATEGORY:
        return "reserved id"
    name = category.get("name")
    if not (_str(name, True) or (isinstance(name, dict) and _str(name.get("en"), True)
                                 and all(key in CATEGORY_LANGUAGES and _str(text, True)
                                         for key, text in name.items()))):
        return "bad name"
    if category.get("icon") is not None and icons.name_problem(category["icon"]):
        return "bad icon"
    return _too_new(category)


def entry_problem(app, categories=None, removal=False):
    """Why this catalog entry can't be shown here, or None. Malformed entries
    and ones needing a newer Store are skipped one at a time. categories is
    the set of shown category ids. With removal, only what uninstalling needs
    is checked, so an installed app stays removable after the catalog drops
    or gates it, or an OS rollback brings back an older Store."""
    if not isinstance(app, dict):
        return "not an object"
    if not (isinstance(app.get("id"), str) and APP_ID.fullmatch(app["id"])):
        return "bad id"
    for key in ("name", "category", "icon"):
        if not _str(app.get(key), key != "icon"):
            return "bad " + key
    for key in ("summary", "note"):
        if app.get(key) is not None and not _str(app.get(key)):
            return "bad " + key
    if app.get("desktopOnly") is not None and not isinstance(app["desktopOnly"], bool):
        return "bad desktopOnly"
    template = app.get("controllerTemplate")
    if template is not None and not (isinstance(template, str) and re.fullmatch(r"[a-z0-9_+]+", template)):
        return "bad controllerTemplate"
    install = app.get("install")
    if not isinstance(install, dict) or not _str(install.get("type"), True):
        return "bad install"
    if not _valid_install(install):
        return "bad install for " + install["type"]
    conflicts = app.get("conflicts")
    if conflicts is not None and not (isinstance(conflicts, list) and all(
            isinstance(entry, dict) and _str(entry.get("type"), True)
            and (entry["type"] != "flatpak" or _flatpak_id(entry.get("ref")))
            and (entry["type"] != "appimage" or _safe_name(entry.get("filename")))
            for entry in conflicts)):
        return "bad conflicts"
    if install["type"] not in INSTALL_TYPES:
        return "unsupported install type " + install["type"]
    if removal:
        return None
    # Well formed; now whether this Store and image can handle it.
    if set(install) - INSTALL_FIELDS[install["type"]]:
        return "unsupported install field " + ", ".join(sorted(set(install) - INSTALL_FIELDS[install["type"]]))
    for entry in conflicts or []:
        if entry["type"] not in CONFLICT_TYPES or set(entry) - CONFLICT_FIELDS[entry["type"]]:
            return "unsupported conflict"
    if app["category"] in profile.reserved_categories:
        return "category {} is filled by the plugin itself".format(app["category"])
    if categories is not None and app["category"] not in categories:
        return "no category " + app["category"]
    problem = _too_new(app)
    if problem:
        return problem
    if install["type"] == "system" and not _executable(install["exec"]):
        return "not in this image: " + install["exec"]
    return None


_logged = set()


def _log_skip(revision, what, item_id, problem):
    key = (revision, what, item_id, problem)
    if key not in _logged:
        _logged.add(key)
        print("{}: catalog {} {} skipped: {}".format(profile.name, what, item_id, problem))


def catalog_categories(current=None):
    """The active catalog's categories this plugin can show, before empty ones
    are dropped."""
    current = current or profile.source.active()
    shown = []
    for category in current["categories"]:
        problem = category_problem(category)
        if problem is None:
            shown.append(category)
        else:
            item_id = category.get("id") if isinstance(category, dict) else category
            _log_skip(current["revision"], "category", str(item_id), problem)
    return shown


def catalog_apps(current=None):
    """The active catalog's entries this plugin can show."""
    current = current or profile.source.active()
    categories = {category["id"] for category in catalog_categories(current)}
    apps = []
    for app in current["apps"]:
        problem = "hidden here" if (
            isinstance(app, dict) and isinstance(app.get("id"), str)
            and app["id"] in profile.hidden_ids) else entry_problem(app, categories)
        if problem is None:
            apps.append(app)
        else:
            item_id = app.get("id") if isinstance(app, dict) else app
            _log_skip(current["revision"], "entry", str(item_id), problem)
    return apps


def bundled_apps():
    try:
        doc, _ = profile.source.bundled()
    except (OSError, ValueError):
        return []
    return [app for app in doc["apps"] if entry_problem(app, removal=True) is None]


def retired_apps(offered, state=None):
    """Entries for apps this Store installed that the catalog no longer offers
    (removed, gated, or in a hidden section): kept so they can still be
    uninstalled."""
    state = records.load_state() if state is None else state
    seen = {app["id"] for app in offered} | profile.hidden_ids
    # A system app is "installed" whenever the image has it, so it is only
    # kept while a Steam shortcut the Store added still needs cleaning up.
    shortcut_ids = set(state.get("shortcuts") or {}) | set(state.get("pendingShortcuts") or [])
    retired = []
    for source in (list((state.get("entries") or {}).values()), bundled_apps()):
        for app in source:
            if (isinstance(app, dict) and app.get("id") not in seen
                    and entry_problem(app, removal=True) is None
                    and ((app.get("install") or {}).get("type") != "system" or app["id"] in shortcut_ids)):
                seen.add(app["id"])
                retired.append(dict(app, retired=True))
    return retired


def all_apps(current=None, state=None):
    offered = catalog_apps(current)
    return offered + retired_apps(offered, state) + profile.extra_apps()


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
            ["flatpak", "list", "--system", "--app", "--columns=application,version"],
            capture_output=True,
            text=True,
            timeout=15,
            env=clean_env(),
        )
        versions = parse_flatpak_columns(result.stdout)
        _flatpak_cache.update({"refs": set(versions), "versions": versions})
    except (OSError, subprocess.TimeoutExpired):
        pass
    finally:
        # Stamp even on failure so a broken flatpak backs off instead of hammering.
        _flatpak_cache["at"] = time.monotonic()
        _flatpak_refresh.release()
    return _flatpak_cache["refs"]


def parse_flatpak_columns(output):
    """{application: version} from tab-separated application,version rows."""
    found = {}
    for line in output.splitlines():
        name, _, version = line.strip().partition("\t")
        if name:
            found[name] = version.strip()
    return found


def invalidate_flatpak_cache():
    _flatpak_cache["at"] = 0.0


def installed_info(app, state, refs):
    install = app.get("install") or {}
    kind = install.get("type")
    if kind == "flatpak":
        info = {"installed": install.get("ref") in refs}
        version = _flatpak_cache["versions"].get(install.get("ref"))
        if info["installed"] and version:
            info["version"] = version
        return info
    if kind == "appimage":
        record = (state.get("appimages") or {}).get(app.get("id")) or {}
        # The file that was downloaded, not the one the catalog names now: a
        # rename in the catalog must not make an installed app look absent.
        filename = record.get("filename") or install.get("filename")
        installed = bool(filename and (apps_dir() / filename).exists())
        info = {"installed": installed}
        if installed and record.get("tag"):
            info["version"] = record["tag"]
        if installed and record.get("stamp"):
            info["date"] = record["stamp"]
        return info
    if kind == "system":
        return {"installed": bool(install.get("exec")) and os.path.exists(install["exec"])}
    if kind in COMPONENT_TYPES:
        installed = (component_dir(kind) / app.get("id", "")).is_dir()
        info = {"installed": installed}
        record = (state.get("components") or {}).get(app.get("id")) or {}
        if installed and record.get("tag"):
            info["version"] = record["tag"]
        if installed and record.get("stamp"):
            info["date"] = record["stamp"]
        return info
    if kind == "deckyplugin":
        if install.get("dir"):
            # A fixed folder, possibly seeded by the image rather than by the
            # Store, so the folder itself is the record.
            path = plugins_dir() / install["dir"]
            installed = (path / "plugin.json").is_file()
            info = {"installed": installed}
            if installed:
                try:
                    info["version"] = json.loads((path / "package.json").read_text("utf-8"))["version"]
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            return info
        record = (state.get("plugins") or {}).get(app.get("id")) or {}
        dirname = record.get("dir")
        installed = bool(dirname and "/" not in dirname and (plugins_dir() / dirname).exists())
        info = {"installed": installed}
        if installed and record.get("tag"):
            info["version"] = record["tag"]
        if installed and record.get("stamp"):
            info["date"] = record["stamp"]
        return info
    if kind in profile.kinds:
        return profile.kinds[kind].installed_info(app)
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


def version_label(app, tag):
    """The part of a release tag the entry's version pattern picks, else the tag."""
    pattern = (app.get("install") or {}).get("version")
    if pattern and isinstance(tag, str):
        try:
            found = re.search(pattern, tag)
        except re.error:
            found = None
        if found and found.group(1):
            return found.group(1)
    return tag


def installed_map(current=None):
    state = records.load_state()
    refs = flatpak_refs()
    entries = state.get("entries") or {}
    result = {}
    for app in all_apps(current, state):
        app_id = app.get("id")
        if not app_id:
            continue
        info = installed_info(app, state, refs)
        # Installs from before entries were recorded: keep what they came from
        # before a catalog update can drop or change it.
        if (info.get("installed") and app_id not in entries
                and (app.get("install") or {}).get("type") in INSTALL_TYPES):
            records.adopt_entry(app_id, app)
        conflicts = present_conflicts(app, refs)
        if conflicts:
            info["conflicts"] = conflicts
        if info.get("version"):
            info["version"] = version_label(app, info["version"])
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
    if app.get("desktopOnly"):
        return None
    spec = _launch_command(app)
    if spec and app.get("controllerTemplate"):
        spec["controllerTemplate"] = app["controllerTemplate"]
    return spec


def _launch_command(app):
    install = app.get("install") or {}
    kind = install.get("type")
    home = str(user_home())
    name = app.get("name") or app.get("id") or "App"
    extra = (install.get("launchOptions") or "").strip()
    if kind in profile.kinds:
        return profile.kinds[kind].launch_command(app)
    if kind == "flatpak" and install.get("ref"):
        options = " ".join(filter(None, ("run " + install["ref"], extra)))
        return {"name": name, "exe": "/usr/bin/flatpak", "startDir": home,
                "launchOptions": wrap_launch_options(options)}
    if kind == "appimage" and install.get("filename"):
        # The file that was downloaded while it is there: a catalog rename only
        # takes effect with the next install.
        record = (records.load_state().get("appimages") or {}).get(app.get("id")) or {}
        filename = record.get("filename")
        if not (isinstance(filename, str) and "/" not in filename and (apps_dir() / filename).is_file()):
            filename = install["filename"]
        return {"name": name, "exe": str(apps_dir() / filename),
                "startDir": str(apps_dir()), "launchOptions": wrap_launch_options(extra)}
    if kind == "system" and install.get("exec"):
        return {"name": name, "exe": install["exec"],
                "startDir": os.path.dirname(install["exec"]),
                "launchOptions": wrap_launch_options(extra)}
    return None


def bundled_plugin(app):
    """A plugin the image ships, which boot sync would put straight back."""
    install = app.get("install") or {}
    return (install.get("type") == "deckyplugin" and bool(install.get("dir"))
            and (bundled_plugins_dir() / install["dir"]).is_dir())


def removable(app):
    kind = (app.get("install") or {}).get("type")
    return kind != "system" and not bundled_plugin(app)



def _still_owned(app, state, refs):
    # A retired entry is listed only while something of it is on the device.
    app_id = app.get("id")
    return (installed_info(app, state, refs).get("installed")
            or app_id in (state.get("shortcuts") or {})
            or app_id in (state.get("pendingShortcuts") or []))


def catalog_payload():
    if hasattr(profile.source, "opened"):
        profile.source.opened()
    current = profile.source.active()
    state = records.load_state()
    categories = catalog_categories(current)
    known = {category["id"] for category in categories}
    refs = None
    apps = []
    for app in all_apps(current, state):
        install = app.get("install") or {}
        retired = bool(app.get("retired"))
        if retired:
            refs = flatpak_refs() if refs is None else refs
            if not _still_owned(app, state, refs):
                continue
        category = app.get("category") or ""
        if category not in profile.reserved_categories and category not in known:
            category = OTHER_CATEGORY
        apps.append({
            "id": app.get("id") or "",
            "name": app.get("name") or "",
            "summary": app.get("summary") or "",
            "category": category,
            "icon": app.get("icon") or "",
            "note": app.get("note") or "",
            "installType": install.get("type") or "",
            "imported": install.get("type") in profile.kinds and bool(install.get("path")),
            "canInstall": app.get("canInstall", True) and not retired,
            "retired": retired,
            "removable": removable(app),
            "desktopOnly": bool(app.get("desktopOnly")),
            "launch": launch_spec(app),
            **(profile.payload_extra(app) if profile.payload_extra else {}),
        })
    # A section with nothing in it would only be an empty screen; a reserved
    # one (Android) is filled by the plugin itself, not from this list.
    used = {app["category"] for app in apps}
    sections = [{"id": category["id"], "name": category["name"], "icon": icons.data_uri(category.get("icon"))}
                for category in categories
                if category["id"] in profile.reserved_categories or category["id"] in used]
    if OTHER_CATEGORY in used:
        sections.append({"id": OTHER_CATEGORY, "name": "", "icon": ""})
    return {"apps": apps, "categories": sections, "home": str(user_home()), "revision": current["revision"]}
