import asyncio

from armada_control.calibration import (
    begin_session,
    controller_state,
    end_session,
    reset_calibration_params,
    save_calibration,
)
from armada_control.config import build_config
from armada_control.controller import set_controller_type
from armada_control.power import save_power_config
from armada_control.steam import installed_games
from armada_control.system import get_hdr_runtime_state, set_ssh_enabled
from armada_control.tweaks import load_compat_applied, save_compat_applied, save_tweaks


class Plugin:
    # Offload blocking work to a thread so a slow call can't stall Decky's asyncio loop.
    async def get_config(self):
        return await asyncio.to_thread(build_config, False)

    async def get_installed_games(self):
        return await asyncio.to_thread(installed_games)

    async def get_hdr_runtime_state(self):
        return await asyncio.to_thread(get_hdr_runtime_state)

    async def save_power_config(self, data):
        await asyncio.to_thread(save_power_config, data)
        return await self.get_config()

    async def save_tweaks(self, data):
        await asyncio.to_thread(save_tweaks, data)
        return await self.get_config()

    async def get_compat_applied(self):
        return await asyncio.to_thread(load_compat_applied)

    async def save_compat_applied(self, appids):
        return await asyncio.to_thread(save_compat_applied, appids)

    async def set_ssh_enabled(self, enabled):
        return await asyncio.to_thread(set_ssh_enabled, enabled)

    async def set_controller_type(self, value):
        return await asyncio.to_thread(set_controller_type, value)

    async def get_controller_state(self):
        return await asyncio.to_thread(controller_state)

    async def save_calibration(self, capture):
        return await asyncio.to_thread(save_calibration, capture)

    async def reset_calibration(self):
        return await asyncio.to_thread(reset_calibration_params)

    async def begin_calibration_session(self, token=None):
        return await asyncio.to_thread(begin_session, token)

    async def end_calibration_session(self, token=None):
        return await asyncio.to_thread(end_session, token)
