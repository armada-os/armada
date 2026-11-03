import json
import pathlib
import sys


OVERLAYS = pathlib.Path("/usr/share/armada/fex-thunk-overlays.json")
# FEX expands this only to Debian multiarch or lib64 dirs.
# This misses the Arch guest's and Steam runtime's libraries.
PREFIX_LIB = "@PREFIX_LIB@/"


def _read_json(path):
    with pathlib.Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def merge(db, extras):
    for name in extras["Thunks"]:
        overlay = db.get("DB", {}).get(name, {}).get("Overlay")
        if not isinstance(overlay, list):
            continue
        libs = [path.removeprefix(PREFIX_LIB) for path in overlay if path.startswith(PREFIX_LIB)]
        for library_dir in extras["LibraryDirs"]:
            for lib in libs:
                path = f"{library_dir}/{lib}"
                if path not in overlay:
                    overlay.append(path)


def merged_text(db_path, only_ours=False):
    db = _read_json(db_path)
    extras = _read_json(OVERLAYS)
    missing = [name for name in extras["Thunks"] if name not in db.get("DB", {})]
    merge(db, extras)
    if only_ours:
        db = {"DB": {name: db["DB"][name] for name in extras["Thunks"] if name not in missing}}
    return json.dumps(db, indent=2) + "\n", missing


if __name__ == "__main__":
    # Image build: merge into the system FEX's DB in place.
    db_path = pathlib.Path(sys.argv[1])
    text, missing = merged_text(db_path)
    if missing:
        sys.exit(f"{db_path} has no thunks named {', '.join(missing)}")
    db_path.write_text(text, encoding="utf-8")
