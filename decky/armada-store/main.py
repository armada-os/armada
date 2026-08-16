import asyncio

from armada_store import catalog, jobs, session, store, updates


class Plugin:
    # Offload blocking work to a thread so a slow call can't stall Decky's asyncio loop.
    async def get_catalog(self):
        return await asyncio.to_thread(catalog.catalog_payload)

    async def get_status(self):
        def build():
            return {
                "jobs": jobs.status(),
                "installed": catalog.installed_map(),
                "shortcuts": store.shortcuts(),
                "pending": store.pending_shortcuts(),
            }

        return await asyncio.to_thread(build)

    async def check_updates(self, force=False):
        return await asyncio.to_thread(updates.available, bool(force))

    async def install_app(self, app_id):
        return await asyncio.to_thread(jobs.start, app_id, "install")

    async def uninstall_app(self, app_id):
        return await asyncio.to_thread(jobs.start, app_id, "uninstall")

    async def replace_app(self, app_id):
        return await asyncio.to_thread(jobs.start, app_id, "replace")

    async def cancel_job(self, app_id):
        return await asyncio.to_thread(jobs.cancel, app_id)

    async def dismiss_job(self, app_id):
        return await asyncio.to_thread(jobs.dismiss, app_id)

    async def prepare_shortcut(self, path):
        return await asyncio.to_thread(catalog.prepare_shortcut, path)

    async def record_shortcut(self, app_id, steam_appid):
        return await asyncio.to_thread(store.record_shortcut, app_id, steam_appid)

    async def clear_shortcut(self, app_id, keep_pending=False, expected=None):
        return await asyncio.to_thread(store.clear_shortcut, app_id, bool(keep_pending), expected)

    async def switch_to_desktop(self):
        return await asyncio.to_thread(session.switch_to_desktop)
