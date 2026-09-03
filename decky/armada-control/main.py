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
from armada_control.rgb import get_rgb, set_rgb
from armada_control.steam import compat_mapped_appids, installed_games
from armada_control.system import (
    reapply_perf,
    restart_game_mode,
    set_abl_auto_enabled,
    set_mtp_enabled,
    set_desktop_mode,
    set_sleep_mode,
    set_ssh_enabled,
)
from armada_control.tweaks import load_compat_applied, save_compat_applied, save_tweaks
from armada_control.fan_curves import get_state as get_fans_state, save_all as save_fan_curves
from armada_control.fan_sensors import get_current_temp


class Plugin:
    # Offload blocking work to a thread so a slow call can't stall Decky's asyncio loop.
    async def get_config(self):
        return await asyncio.to_thread(build_config, False)

    async def get_installed_games(self):
        return await asyncio.to_thread(installed_games)

    async def get_compat_mapped_appids(self, tool):
        return await asyncio.to_thread(compat_mapped_appids, tool)

    async def save_power_config(self, data):
        await asyncio.to_thread(save_power_config, data)
        return await self.get_config()

    async def save_tweaks(self, data):
        await asyncio.to_thread(save_tweaks, data)
        return await self.get_config()

    async def get_compat_applied(self):
        return await asyncio.to_thread(load_compat_applied)

    async def save_compat_applied(self, appids, proton_default=None):
        return await asyncio.to_thread(save_compat_applied, appids, proton_default)

    async def set_ssh_enabled(self, enabled):
        return await asyncio.to_thread(set_ssh_enabled, enabled)

    async def set_mtp_enabled(self, enabled):
        return await asyncio.to_thread(set_mtp_enabled, enabled)

    async def set_abl_auto_enabled(self, enabled):
        return await asyncio.to_thread(set_abl_auto_enabled, enabled)

    async def set_desktop_mode(self, value):
        return await asyncio.to_thread(set_desktop_mode, value)

    async def set_sleep_mode(self, value):
        return await asyncio.to_thread(set_sleep_mode, value)

    async def reapply_perf(self):
        return await asyncio.to_thread(reapply_perf)

    async def restart_game_mode(self):
        return await asyncio.to_thread(restart_game_mode)

    async def set_controller_type(self, value):
        return await asyncio.to_thread(set_controller_type, value)

    async def get_rgb(self):
        return await asyncio.to_thread(get_rgb)

    async def set_rgb(self, enabled, color, brightness):
        return await asyncio.to_thread(set_rgb, enabled, color, brightness)

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

    async def get_fans_state(self):
        return await asyncio.to_thread(get_fans_state)

    async def save_fan_curves(self, fan_curves, fan_settings):
        return await asyncio.to_thread(save_fan_curves, fan_curves, fan_settings)

    # Polled separately from get_fans_state -- see hooks/useCurrentTemp.
    async def get_current_temp(self):
        return await asyncio.to_thread(get_current_temp)
