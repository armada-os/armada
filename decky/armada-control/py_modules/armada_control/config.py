from .controller import CONTROLLER_TYPES, controller_type, inputplumber_targets
from .power import factory_power_defaults, parse_power
from .rgb import rgb_supported
from .steam import installed_games
from .system import (
    abl_auto_enabled,
    abl_version,
    bottom_screen_brightness,
    bottom_screen_enabled,
    device_env,
    mtp_enabled,
    os_version,
    perf_info,
    desktop_mode,
    desktop_modes,
    sleep_modes,
    software_dim_enabled,
    software_dim_percent,
    ssh_enabled,
)
from .tweaks import fex_profile_labels, load_fex_contract, load_tweaks


def build_config(include_games=True):
    fex_contract = load_fex_contract()
    env = device_env()
    secondary_brightness = bottom_screen_brightness()
    return {
        "power": parse_power(),
        "powerDefaults": factory_power_defaults(),
        "tweaks": load_tweaks(),
        "installedGames": installed_games() if include_games else [],
        "fexProfiles": fex_profile_labels(fex_contract),
        "perf": perf_info(),
        "cpuDeviceClass": env.get("ARMADA_SOC_CLASS", ""),
        "rgbSupported": rgb_supported(),
        "protonDefaults": [
            default.strip()
            for default in env.get("ARMADA_PROTON_DEFAULTS", "").split(":")
            if default.strip()
        ],
        "osVersion": os_version(),
        "ablVersion": abl_version(),
        "ablAutoEnabled": abl_auto_enabled(),
        "softwareDimEnabled": software_dim_enabled(),
        "softwareDimPercent": software_dim_percent(),
        "bottomScreenSupported": bool(
            env.get("ARMADA_SECONDARY_CONNECTOR") and env.get("ARMADA_SECONDARY_TOUCHSCREEN")
        ),
        "bottomScreenEnabled": bottom_screen_enabled(),
        "bottomScreenBrightnessSupported": secondary_brightness is not None,
        "bottomScreenBrightness": secondary_brightness or 0,
        "sshEnabled": ssh_enabled(),
        "mtpEnabled": mtp_enabled(),
        "desktopMode": desktop_mode(),
        "desktopModes": desktop_modes(),
        "sleepMode": env.get("ARMADA_SUSPEND_MODE", "s2idle"),
        "sleepModes": sleep_modes(),
        "controllerType": controller_type(),
        "controllerTypes": [
            {"data": key, "label": CONTROLLER_TYPES[key]} for key in inputplumber_targets(env)
        ],
    }
