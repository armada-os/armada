from .controller import CONTROLLER_TYPES, controller_type
from .power import factory_power_defaults, parse_power
from .steam import installed_games
from .system import (
    abl_auto_enabled,
    abl_version,
    device_env,
    mtp_enabled,
    os_version,
    perf_info,
    desktop_mode,
    desktop_modes,
    sleep_modes,
    ssh_enabled,
)
from .tweaks import fex_profile_labels, load_fex_contract, load_tweaks


def build_config(include_games=True):
    fex_contract = load_fex_contract()
    env = device_env()
    return {
        "power": parse_power(),
        "powerDefaults": factory_power_defaults(),
        "tweaks": load_tweaks(),
        "installedGames": installed_games() if include_games else [],
        "fexProfiles": fex_profile_labels(fex_contract),
        "perf": perf_info(),
        "cpuDeviceClass": env.get("ARMADA_SOC_CLASS", ""),
        "rgbSupported": bool(env.get("ARMADA_RGB_BACKEND")),
        "protonDefaults": [
            default.strip()
            for default in env.get("ARMADA_PROTON_DEFAULTS", "").split(":")
            if default.strip()
        ],
        "osVersion": os_version(),
        "ablVersion": abl_version(),
        "ablAutoEnabled": abl_auto_enabled(),
        "sshEnabled": ssh_enabled(),
        "mtpEnabled": mtp_enabled(),
        "desktopMode": desktop_mode(),
        "desktopModes": desktop_modes(),
        "sleepMode": env.get("ARMADA_SUSPEND_MODE", "s2idle"),
        "sleepModes": sleep_modes(),
        "controllerType": controller_type(),
        "controllerTypes": [{"data": key, "label": label} for key, label in CONTROLLER_TYPES.items()],
    }
