from .controller import CONTROLLER_TYPES, controller_type
from .lighting import stick_led_state
from .power import factory_power_defaults, parse_power
from .steam import installed_games
from .system import cpu_device_class, os_version, ssh_enabled
from .tweaks import fex_profile_labels, load_fex_contract, load_tweaks


def build_config(include_games=True):
    fex_contract = load_fex_contract()
    return {
        "power": parse_power(),
        "powerDefaults": factory_power_defaults(),
        "tweaks": load_tweaks(),
        "installedGames": installed_games() if include_games else [],
        "fexProfiles": fex_profile_labels(fex_contract),
        "cpuDeviceClass": cpu_device_class(),
        "osVersion": os_version(),
        "sshEnabled": ssh_enabled(),
        "controllerType": controller_type(),
        "controllerTypes": [{"data": key, "label": label} for key, label in CONTROLLER_TYPES.items()],
        "stickLed": stick_led_state(),
    }
