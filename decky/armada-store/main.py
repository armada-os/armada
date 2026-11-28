import asyncio

import armada_store  # configures the shared engine before anything uses it
from armada_apps import catalog, installers, jobs, session, records, updates, userfs
from armada_store import android, remote_catalog, shortcuts


class Plugin:
    async def search_android(self, query, page=None, category=None):
        return await asyncio.to_thread(android.search, query, page, category)

    async def import_android(self, path):
        return await asyncio.to_thread(android.import_local, path)

    async def _main(self):
        await asyncio.to_thread(userfs.sweep_staging)

    async def _unload(self):
        # Inline: a to_thread call here can stall shutdown until Decky kills
        # the plugin 5s later.
        android.stop()

    # Offload blocking work to a thread so a slow call can't stall Decky's asyncio loop.
    async def get_catalog(self):
        return await asyncio.to_thread(catalog.catalog_payload)

    async def get_status(self):
        def build():
            # The panel polls this every second; it doubles as the catalog's
            # refresh timer while the Store stays open.
            remote_catalog.maybe_refresh(remote_catalog.POLL_INTERVAL)
            return jobs.status_payload()

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
        return await asyncio.to_thread(shortcuts.prepare_shortcut, path)

    async def clear_reload(self, name):
        return await asyncio.to_thread(records.clear_pending_reload, name)

    async def restart_decky(self):
        return await asyncio.to_thread(installers.restart_decky)

    async def record_shortcut(self, app_id, steam_appid):
        return await asyncio.to_thread(records.record_shortcut, app_id, steam_appid)

    async def clear_shortcut(self, app_id, keep_pending=False, expected=None):
        return await asyncio.to_thread(records.clear_shortcut, app_id, bool(keep_pending), expected)

    async def switch_to_desktop(self):
        return await asyncio.to_thread(session.switch_to_desktop)
