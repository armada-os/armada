from .button_layout import BUTTON_LAYOUTS, button_layout_state
from .controller import CONTROLLER_TYPES, controller_type
from .power import factory_power_defaults, parse_power
from .steam import installed_games
from .system import abl_version, cpu_device_class, os_version, ssh_enabled
from .tweaks import fex_profile_labels, load_fex_contract, load_tweaks


def build_config(include_games=True):
    fex_contract = load_fex_contract()
    layout = button_layout_state()
    return {
        "power": parse_power(),
        "powerDefaults": factory_power_defaults(),
        "tweaks": load_tweaks(),
        "installedGames": installed_games() if include_games else [],
        "fexProfiles": fex_profile_labels(fex_contract),
        "cpuDeviceClass": cpu_device_class(),
        "osVersion": os_version(),
        "ablVersion": abl_version(),
        "sshEnabled": ssh_enabled(),
        "controllerType": controller_type(),
        "controllerTypes": [{"data": key, "label": label} for key, label in CONTROLLER_TYPES.items()],
        "buttonLayout": layout["value"],
        "resolvedButtonLayout": layout["resolved"],
        "buttonLayouts": [{"data": key, "label": label} for key, label in BUTTON_LAYOUTS.items()],
    }
