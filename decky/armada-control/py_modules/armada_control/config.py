from .calibration import calibration_metadata
from .controller import CONTROLLER_TYPES, controller_type, inputplumber_targets
from .fan_curves import charging_fan_supported
from .power import factory_power_defaults, parse_power, resolve_limits
from .rgb import rgb_supported
from .steam import installed_games
from .system import (
    abl_version,
    bottom_screen_status,
    bottom_screen_enabled,
    device_env,
    freq_limits,
    gyro_state,
    mtp_enabled,
    os_version,
    perf_info,
    panel_calibration,
    desktop_mode,
    desktop_modes,
    sleep_modes,
    ssh_enabled,
    swipe_gestures_enabled,
)
from .tweaks import (
    fex_profile_labels,
    load_env_presets,
    load_fex_contract,
    load_tweak_defaults,
    load_tweaks,
    turnip_drivers,
)


def build_initial_config(env=None, include_games=False):
    env = device_env() if env is None else env
    return {
        "tweaks": load_tweaks(),
        "tweaksDefaults": load_tweak_defaults(),
        "installedGames": installed_games() if include_games else [],
        "fexProfiles": fex_profile_labels(load_fex_contract()),
        "turnipDrivers": turnip_drivers(),
        "envPresets": load_env_presets(),
        "perf": perf_info(env),
        "cpuDeviceClass": env.get("ARMADA_SOC_CLASS", ""),
        "rgbSupported": rgb_supported(),
        "protonDefaults": [
            default.strip()
            for default in env.get("ARMADA_PROTON_DEFAULTS", "").split(":")
            if default.strip()
        ],
    }


def build_profiles_config(power=None, env=None):
    env = device_env() if env is None else env
    limits = freq_limits(env)
    soc = env.get("ARMADA_SOC_CLASS", "")
    return {
        "power": resolve_limits(parse_power() if power is None else power, limits, soc),
        "powerDefaults": resolve_limits(factory_power_defaults(), limits, soc),
        "freqLimits": {key: limits[key] for key in ("gpuMhz", "gpuStockMaxMhz", "cpuPolicies", "cpuTopology")},
    }


def build_controller_config(env=None):
    env = device_env() if env is None else env
    return {
        "controllerType": controller_type(),
        "gyro": gyro_state(),
        **calibration_metadata(),
        "controllerTypes": [
            {"data": key, "label": CONTROLLER_TYPES[key]} for key in inputplumber_targets(env)
        ],
    }


def build_device_config(power=None):
    power = parse_power() if power is None else power
    try:
        panel_supported = bool(panel_calibration().get("supported"))
    except (RuntimeError, OSError, ValueError):
        panel_supported = False
    return {
        "panelCalibrationSupported": panel_supported,
        "chargingFanPwm": int(power["fan"].get("charging_pwm", 0)),
        "chargingFanSupported": charging_fan_supported(),
    }


def build_experimental_config(env=None):
    env = device_env() if env is None else env
    secondary = bottom_screen_status()
    return {
        "bottomScreenSupported": bool(
            env.get("ARMADA_SECONDARY_CONNECTOR") and env.get("ARMADA_SECONDARY_TOUCHSCREEN")
        ),
        "bottomScreenEnabled": bottom_screen_enabled(),
        "bottomScreenBrightnessSupported": secondary["supported"],
        "bottomScreenActive": secondary["active"],
        "bottomScreenBrightness": secondary["brightness"],
        "swipeGesturesEnabled": swipe_gestures_enabled(),
        "mtpEnabled": mtp_enabled(),
        "desktopMode": desktop_mode(),
        "desktopModes": desktop_modes(),
        "sleepMode": env.get("ARMADA_SUSPEND_MODE", "s2idle"),
        "sleepModes": sleep_modes(),
    }


def build_about_config():
    return {"osVersion": os_version(), "ablVersion": abl_version(), "sshEnabled": ssh_enabled()}


def build_config(include_games=True):
    env = device_env()
    power = parse_power()
    return {
        **build_initial_config(env, include_games),
        **build_profiles_config(power, env),
        **build_controller_config(env),
        **build_device_config(power),
        **build_experimental_config(env),
        **build_about_config(),
    }
