from .controller import CONTROLLER_TYPES, controller_type
from .power import factory_power_defaults, parse_power
from .steam import installed_games
from .system import abl_version, cpu_device_class, os_version, perf_info, ssh_enabled, vpn_enabled, vpn_profile
from .tweaks import fex_profile_labels, load_fex_contract, load_tweaks


def build_config(include_games=True):
    fex_contract = load_fex_contract()
    return {
        "power": parse_power(),
        "powerDefaults": factory_power_defaults(),
        "tweaks": load_tweaks(),
        "installedGames": installed_games() if include_games else [],
        "fexProfiles": fex_profile_labels(fex_contract),
        "perf": perf_info(),
        "cpuDeviceClass": cpu_device_class(),
        "osVersion": os_version(),
        "ablVersion": abl_version(),
        "sshEnabled": ssh_enabled(),
        "vpnEnabled": vpn_enabled(),
        "vpnProfile": vpn_profile(),
        "controllerType": controller_type(),
        "controllerTypes": [{"data": key, "label": label} for key, label in CONTROLLER_TYPES.items()],
    }
