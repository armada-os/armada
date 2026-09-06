import os

from . import catalog, installers, userfs
from .paths import plugin_dir

# Handlers for apps naming one in their catalog "postInstall" field. Updates
# reinstall, so every handler must be idempotent and never clobber a user edit.

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


def _seed_templates(template_dir, dest_parts, overwrite=False):
    """Copy templates that are not already present, leaving edits alone.
    With overwrite, existing files are kept as .bak and replaced."""
    source = plugin_dir() / "templates" / template_dir
    names = sorted(p.name for p in source.iterdir() if p.is_file())
    if not names:
        raise RuntimeError("No templates in " + str(source))
    dir_fd = userfs.open_user_path(list(dest_parts), create=True)
    try:
        for name in names:
            present = True
            try:
                os.close(os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd))
            except FileNotFoundError:
                present = False
            if present and not overwrite:
                continue
            data = (source / name).read_bytes()
            staged = "." + name + ".armada-tmp"
            with userfs.create_file(dir_fd, staged) as fh:
                fh.write(data)
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


def es_de():
    # ES-DE has no ARMSX2 entry at all, so it cannot find that emulator.
    _seed_templates("es-de", ("ES-DE", "custom_systems"))


def seed_config(app, overwrite=False):
    """Apply the app's catalog "config" templates under the user's home."""
    config = (app or {}).get("config") or {}
    templates = config.get("templates")
    dest = config.get("dest")
    if not templates or not dest:
        return False
    _seed_templates(templates, tuple(dest), overwrite)
    return True


def reset_config(app_id):
    app = catalog.find_app(app_id)
    if app is None:
        raise RuntimeError("App is no longer in the catalog")
    if not seed_config(app, overwrite=True):
        raise RuntimeError("No configuration template for " + str(app_id))


HANDLERS = {
    "retroarch-cores-url": retroarch,
    "es-de-custom-systems": es_de,
}


def run(app):
    seed_config(app)
    name = (app or {}).get("postInstall")
    if not name:
        return
    handler = HANDLERS.get(name)
    if handler is None:
        # Shipped data naming a handler that does not exist is a packaging
        # mistake; skipping it silently would install a knowingly broken app.
        raise RuntimeError("Unknown postInstall handler: " + str(name))
    handler()
