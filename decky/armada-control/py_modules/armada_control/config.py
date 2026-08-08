from .controller import CONTROLLER_TYPES, controller_type
from .power import factory_power_defaults, parse_power
from .steam import installed_games
from .system import (
    abl_version,
    cpu_device_class,
    mtp_enabled,
    os_version,
    perf_info,
    sm8550_sleep_enabled,
    ssh_enabled,
)
from .tweaks import fex_profile_labels, load_fex_contract, load_tweaks


def build_config(include_games=True):
    fex_contract = load_fex_contract()
    device_class = cpu_device_class()
    return {
        "power": parse_power(),
        "powerDefaults": factory_power_defaults(),
        "tweaks": load_tweaks(),
        "installedGames": installed_games() if include_games else [],
        "fexProfiles": fex_profile_labels(fex_contract),
        "perf": perf_info(),
        "cpuDeviceClass": device_class,
        "osVersion": os_version(),
        "ablVersion": abl_version(),
        "sshEnabled": ssh_enabled(),
        "mtpEnabled": mtp_enabled(),
        "sm8550SleepEnabled": sm8550_sleep_enabled() if device_class == "SM8550" else False,
        "controllerType": controller_type(),
        "controllerTypes": [{"data": key, "label": label} for key, label in CONTROLLER_TYPES.items()],
    }
