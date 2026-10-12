#!/usr/bin/python3
"""Install, remove and list game mods. Runs as the device user, never as root.

A folder in mods/ that installed.json does not record was put there by hand
and is never replaced or removed.
"""
import fcntl, json, os, pathlib, re, shutil, subprocess, sys, tarfile, tempfile

ROOT = pathlib.Path(os.environ.get("ARMADA_MODS_HOME", pathlib.Path.home() / ".local/share/armada-mods"))
MODS = ROOT / "mods"
RECORD = ROOT / "installed.json"


def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def read_manifest(d):
    meta = json.loads((d / "mod.json").read_text())
    for key in ("id", "version", "name"):
        if not isinstance(meta.get(key), str) or not meta[key]:
            raise ValueError(f"mod.json has no {key}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", meta["id"]):
        raise ValueError("id must be lowercase letters, digits and dashes")
    appids = meta.get("steam_appids")
    if not isinstance(appids, list) or not appids or not all(type(a) is int for a in appids):
        raise ValueError("steam_appids must be a list of Steam app ids")
    return meta


def record():
    try:
        return json.loads(RECORD.read_text())
    except (OSError, ValueError):
        return {}


def save(rec):
    tmp = RECORD.with_name(RECORD.name + ".tmp")
    tmp.write_text(json.dumps(rec, indent=2) + "\n")
    tmp.replace(RECORD)


def safe_extract(archive, dest):
    with tarfile.open(archive) as tar:
        # Plain files and directories only. A link that is harmless inside the staging
        # directory can point somewhere else once the mod is moved into place.
        for member in tar.getmembers():
            if not (member.isfile() or member.isdir()):
                raise ValueError(f"{member.name}: only files and directories are allowed")
        tar.extractall(dest, filter="data")


def discard(target):
    # overlay work directories left by the launch wrapper are mode 000
    if target.is_dir():
        subprocess.run(["chmod", "-R", "u+rwx", str(target)], check=False)
        shutil.rmtree(target, ignore_errors=True)


HELD = {}


def lock_games(mod):
    # The launch wrapper holds <cache>/<appid>.lock while a game runs with its mods mounted
    # and takes it before reading them, so holding it until exit keeps a launch out too.
    cache = pathlib.Path(os.environ.get("XDG_CACHE_HOME") or pathlib.Path.home() / ".cache") / "armada-mods"
    try:
        appids = read_manifest(mod)["steam_appids"]
    except (OSError, ValueError):
        return
    cache.mkdir(parents=True, exist_ok=True)
    for appid in appids:
        if appid in HELD:
            continue
        lock = open(cache / f"{appid}.lock", "a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fail("Quit the game this mod applies to first")
        HELD[appid] = lock


def install(path, expected=None):
    MODS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=MODS, prefix=".staging-") as tmp:
        tmp = pathlib.Path(tmp)
        try:
            safe_extract(path, tmp)
        except (OSError, ValueError, tarfile.TarError) as e:
            fail(f"Not a mod archive: {e}")
        entries = list(tmp.iterdir())
        src = entries[0] if len(entries) == 1 and entries[0].is_dir() else tmp
        try:
            meta = read_manifest(src)
        except (OSError, ValueError) as e:
            fail(f"Not a mod: {e}")
        if expected and meta["id"] != expected:
            fail(f"Archive is a different mod: {meta['id']}")
        rec = record()
        dest = MODS / meta["id"]
        if dest.exists() and meta["id"] not in rec:
            fail(f"{meta['id']} was installed by hand; remove that folder first")
        lock_games(dest)
        lock_games(src)
        # recorded first: a failure after this leaves an entry that the next install repairs,
        # not a folder the installer no longer recognises as its own
        rec[meta["id"]] = {"version": meta["version"]}
        save(rec)
        old = dest.with_name("." + dest.name + ".old")
        discard(old)
        if dest.exists():
            dest.rename(old)
        src.rename(dest)
        discard(old)
    print(json.dumps({"id": meta["id"], "version": meta["version"]}))


def remove(mod):
    rec = record()
    if mod not in rec:
        fail(f"{mod} was installed by hand; remove its folder yourself")
    lock_games(MODS / mod)
    for target in (MODS / mod, ROOT / "data" / mod):
        discard(target)
    del rec[mod]
    save(rec)


def listing():
    rec, out = record(), []
    for entry in sorted(MODS.iterdir()) if MODS.is_dir() else []:
        try:
            meta = read_manifest(entry)
        except (OSError, ValueError):
            continue
        if meta["id"] != entry.name:
            continue
        out.append({"id": meta["id"], "version": meta["version"], "name": meta["name"],
                    "summary": str(meta.get("summary") or ""), "steamAppids": meta["steam_appids"],
                    "byHand": meta["id"] not in rec})
    print(json.dumps(out))


def main():
    a = sys.argv[1:]
    # one install or remove at a time: both rewrite installed.json
    ROOT.mkdir(parents=True, exist_ok=True)
    lock = open(ROOT / ".lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    if len(a) in (2, 3) and a[0] == "install":
        install(*a[1:])
    elif len(a) == 2 and a[0] == "remove":
        remove(a[1])
    elif a == ["list"]:
        listing()
    else:
        fail("usage: install <archive> [expected id] | remove <id> | list")


if __name__ == "__main__":
    main()
