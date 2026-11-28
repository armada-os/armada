import json
import os
from pathlib import Path

from armada_apps import records
from armada_apps.paths import apps_dir, bundled_plugins_dir

PLUGIN = "armada-emulation"
STORE_STATE = "/var/lib/armada-store/state.json"
DONE_KEY = "importedFromStore"


def supported():
    """Emulation lives in homebrew, so it survives a rollback to an image
    whose Store still manages emulators; it only acts where the image ships it."""
    return (bundled_plugins_dir() / PLUGIN).is_dir()


def _store_state():
    path = Path(os.environ.get("ARMADA_EMULATION_STORE_STATE", STORE_STATE))
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}  # the Store never ran: nothing to take over
    if not isinstance(data, dict):
        raise ValueError("Store state is not an object")
    return data


def run(app_ids):
    """Adopt the Store's records for these apps, each record once, so one
    removed here never comes back; later runs pick up what an older image's
    Store recorded after a rollback. The Store's file is only read."""
    try:
        old = _store_state()
    except (OSError, ValueError) as error:
        print("{}: Store records unreadable, will retry: {}".format(PLUGIN, error))
        return
    ids = set(app_ids)

    def pick(key):
        value = old.get(key)
        return {k: v for k, v in value.items() if k in ids} if isinstance(value, dict) else {}

    appimages = {}
    for app_id, record in pick("appimages").items():
        # A record for a file that is gone would claim a version nothing has.
        filename = record.get("filename") if isinstance(record, dict) else None
        if isinstance(filename, str) and "/" not in filename and (apps_dir() / filename).is_file():
            appimages[app_id] = record
    shortcuts = {k: v for k, v in pick("shortcuts").items() if type(v) is int}
    entries = {k: v for k, v in pick("entries").items() if isinstance(v, dict)}
    pending = [app_id for app_id in old.get("pendingShortcuts") or [] if app_id in ids]

    def mutate(state):
        seen = state.get(DONE_KEY)
        first = not isinstance(seen, dict)
        seen = {"appimages": {}, "shortcuts": {}} if first else seen
        for key, values in (("appimages", appimages), ("shortcuts", shortcuts)):
            adopted = seen.setdefault(key, {})
            for app_id, value in values.items():
                if adopted.get(app_id) == value:
                    continue  # adopted before; whatever happened here since stands
                adopted[app_id] = value
                state.setdefault(key, {}).setdefault(app_id, value)
        if first:
            for app_id, value in entries.items():
                state.setdefault("entries", {}).setdefault(app_id, value)
            queue = state.setdefault("pendingShortcuts", [])
            queue.extend(app_id for app_id in pending if app_id not in queue)
        state[DONE_KEY] = seen

    records._mutate_state(mutate)
