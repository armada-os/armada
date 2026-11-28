import asyncio

import armada_emulation  # configures the shared engine before anything uses it
from armada_apps import catalog, installers, jobs, session, records, updates, userfs
from armada_emulation import setup, takeover

# Shown instead of the list on an image that doesn't ship Emulation: its Store
# manages emulators there.
UNSUPPORTED = "This Armada image manages emulators in Armada Store. Update Armada to use Armada Emulation."


def _supported():
    if not takeover.supported():
        raise RuntimeError(UNSUPPORTED)


def _catalog():
    if not takeover.supported():
        return {"apps": [], "categories": [], "notice": UNSUPPORTED, "home": "", "revision": "unsupported"}
    takeover.run(app["id"] for app in catalog.catalog_apps())
    return catalog.catalog_payload()


def _status():
    if not takeover.supported():
        return {"catalogRevision": "unsupported", "jobs": [], "installed": {}, "shortcuts": {}, "pending": []}
    return jobs.status_payload()


def _guarded(work):
    def run(*args):
        _supported()
        return work(*args)
    return run


class Plugin:
    async def _main(self):
        await asyncio.to_thread(userfs.sweep_staging)

    # Offload blocking work to a thread so a slow call can't stall Decky's asyncio loop.
    async def get_catalog(self):
        return await asyncio.to_thread(_catalog)

    async def get_status(self):
        return await asyncio.to_thread(_status)

    async def check_updates(self, force=False):
        if not takeover.supported():
            return {}
        return await asyncio.to_thread(updates.available, bool(force))

    async def install_app(self, app_id):
        return await asyncio.to_thread(_guarded(jobs.start), app_id, "install")

    async def uninstall_app(self, app_id):
        return await asyncio.to_thread(_guarded(jobs.start), app_id, "uninstall")

    async def replace_app(self, app_id):
        return await asyncio.to_thread(_guarded(jobs.start), app_id, "replace")

    async def cancel_job(self, app_id):
        return await asyncio.to_thread(jobs.cancel, app_id)

    async def dismiss_job(self, app_id):
        return await asyncio.to_thread(jobs.dismiss, app_id)

    async def clear_reload(self, name):
        return await asyncio.to_thread(records.clear_pending_reload, name)

    async def restart_decky(self):
        return await asyncio.to_thread(installers.restart_decky)

    async def record_shortcut(self, app_id, steam_appid):
        return await asyncio.to_thread(records.record_shortcut, app_id, steam_appid)

    async def clear_shortcut(self, app_id, keep_pending=False, expected=None):
        return await asyncio.to_thread(records.clear_shortcut, app_id, bool(keep_pending), expected)

    async def reset_config(self, app_id):
        return await asyncio.to_thread(_guarded(setup.reset_config), app_id)

    async def switch_to_desktop(self):
        return await asyncio.to_thread(session.switch_to_desktop)
