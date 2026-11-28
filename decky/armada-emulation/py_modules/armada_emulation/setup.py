import os
import stat
import threading

from armada_apps import installers, userfs
from armada_apps.paths import plugin_dir

# Setup each emulator gets after every install or update. Updates reinstall,
# so every step must be idempotent and never clobber a user edit.

# Config templates shipped in templates/<folder>/, written under the user's
# home only where nothing is there yet; Reset Configuration rewrites them.
TEMPLATES = {
    "melonds": ("melonds", (".config", "melonDS"), ("melonDS.toml",)),
    "azahar": ("azahar", (".config", "azahar-emu"), ("qt-config.ini",)),
    "es-de": ("es-de", ("ES-DE", "custom_systems"), ("es_find_rules.xml", "es_systems.xml")),
}

# Emulator manifests rarely grant removable media, and DuckStation's grants no
# filesystem access at all. Armada mounts cards under /run/media.
BASE_OVERRIDES = ("--filesystem=/var/home/armada", "--filesystem=/home/armada",
                  "--filesystem=/run/media", "--filesystem=/media")

RETROARCH_REF = "org.libretro.RetroArch"
RETROARCH_CONFIG_PARTS = (".var", "app", RETROARCH_REF, "config", "retroarch")
RETROARCH_CONFIG = "retroarch.cfg"
# The RetroArch commit Flathub pins has no aarch64 case in config.def.h, so
# DEFAULT_BUILDBOT_SERVER_URL compiles to "" and the Online Updater has no source.
CORES_URL_KEY = "core_updater_buildbot_cores_url"
CORES_URL = "https://buildbot.libretro.com/nightly/linux/aarch64/latest/"


def _read_at(dir_fd, name):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _skeleton():
    # What RetroArch itself copies when it creates a config, so seeding ahead of
    # first run keeps the asset, database and core-info paths it would have got.
    location = installers.flatpak_location(RETROARCH_REF)
    if not location:
        return None
    try:
        with open(os.path.join(location, "files/etc", RETROARCH_CONFIG), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _set_key(text, key, value):
    kept = []
    for entry in text.splitlines():
        if entry.split("=")[0].strip() != key:
            kept.append(entry)
        elif entry.split("=", 1)[-1].strip().strip('"'):
            return None  # the user picked a value; leave it alone
    kept.append('{} = "{}"'.format(key, value))
    updated = "\n".join(kept) + "\n"
    return None if updated == text else updated


def retroarch():
    dir_fd = userfs.open_user_path(list(RETROARCH_CONFIG_PARTS), create=True)
    try:
        text = _read_at(dir_fd, RETROARCH_CONFIG)
        if text is None:
            text = _skeleton()
            if text is None:
                # A seeded config without the skeleton would lack every path
                # RetroArch needs; leave first run to RetroArch instead.
                return
            text += '\nconfig_save_on_exit = "true"\n'
        updated = _set_key(text, CORES_URL_KEY, CORES_URL)
        if updated is None:
            return
        staged = "." + RETROARCH_CONFIG + ".armada-tmp"
        with userfs.create_file(dir_fd, staged) as fh:
            fh.write(updated.encode("utf-8"))
        userfs.rename(dir_fd, staged, dir_fd, RETROARCH_CONFIG)
    finally:
        os.close(dir_fd)


STEPS = {"retroarch": retroarch}

_seed_lock = threading.Lock()


def _seed_templates(files, dest_parts, overwrite=False):
    """Write {name: bytes} under the user's home, leaving present files alone.
    With overwrite, existing files are kept as .bak and replaced."""
    # The staged names are fixed, so two seeds of one folder must not overlap.
    with _seed_lock:
        dir_fd = userfs.open_user_path(list(dest_parts), create=True)
        try:
            for name in sorted(files):
                try:
                    info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
                except FileNotFoundError:
                    info = None
                # Never open what the user put there: a FIFO would block here.
                if info is not None and not stat.S_ISREG(info.st_mode):
                    raise RuntimeError("Not a regular file: " + name)
                present = info is not None
                if present and not overwrite:
                    continue
                staged = "." + name + ".armada-tmp"
                with userfs.create_file(dir_fd, staged) as fh:
                    fh.write(files[name])
                if not present:
                    userfs.rename(dir_fd, staged, dir_fd, name)
                    continue
                # The live file is never absent: swap in the staged template and
                # only then park the old contents as the backup.
                try:
                    userfs.exchange(dir_fd, staged, dir_fd, name)
                except NotImplementedError:
                    userfs.rename(dir_fd, name, dir_fd, name + ".bak")
                    try:
                        userfs.rename(dir_fd, staged, dir_fd, name)
                    except OSError:
                        userfs.rename(dir_fd, name + ".bak", dir_fd, name)
                        raise
                    continue
                userfs.rename(dir_fd, staged, dir_fd, name + ".bak")
        finally:
            os.close(dir_fd)


def seed_config(app_id, overwrite=False):
    """Apply the app's templates under the user's home; False when it has none.
    Every file is read before any is written, so a missing one never leaves a
    half-seeded folder."""
    if app_id not in TEMPLATES:
        return False
    folder, dest, names = TEMPLATES[app_id]
    files = {name: (plugin_dir() / "templates" / folder / name).read_bytes() for name in names}
    _seed_templates(files, dest, overwrite)
    return True


def after_install(app):
    seed_config(app.get("id"))
    step = STEPS.get(app.get("id"))
    if step:
        step()


def reset_config(app_id):
    if not seed_config(app_id, overwrite=True):
        raise RuntimeError("No configuration template for " + str(app_id))


def payload_extra(app):
    return {"hasConfig": app.get("id") in TEMPLATES and not app.get("retired")}
