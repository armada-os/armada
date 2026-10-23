import configparser
import math
import shutil
import tempfile
import time
from pathlib import Path

from .privileged import call
from .system import at_most, device_env, freq_limits

POWER_CONFIG = Path("/etc/armada/power-profiles.conf")
FACTORY_POWER_CONFIG = Path("/usr/share/armada/power-profiles.conf")
PROFILES = ("eco", "balanced", "performance")


def default_label(name):
    return name.replace("_", " ").title()


def restore_factory_power_config(reason):
    # Remove invalid /etc overrides so factory-only sections keep tracking /usr.
    if not POWER_CONFIG.exists():
        raise reason
    backup = POWER_CONFIG.with_name(f"{POWER_CONFIG.name}.invalid-{time.strftime('%Y%m%d-%H%M%S')}")
    try:
        shutil.copy2(POWER_CONFIG, backup)
        POWER_CONFIG.unlink()
    except OSError:
        raise reason


def parse_power(path=None, repair=True):
    parser = configparser.ConfigParser()
    paths = [path] if path is not None else [FACTORY_POWER_CONFIG, POWER_CONFIG]
    try:
        if not parser.read([candidate for candidate in paths if candidate.exists()]):
            raise FileNotFoundError(path or FACTORY_POWER_CONFIG)
        return parsed_power(parser)
    except (configparser.Error, FileNotFoundError, ValueError) as exc:
        # Avoid factory-restore on IO errors or code bugs in the read path.
        if path is None and repair:
            restore_factory_power_config(exc)
            return parse_power(FACTORY_POWER_CONFIG, repair=False)
        raise


def parse_mhz(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        mhz = int(value)
    except (TypeError, ValueError):
        return None
    return mhz if mhz > 0 else None


def parse_ratio(value):
    if not math.isfinite(float(value)):
        raise ValueError("ratio must be a finite number")
    return value


def parse_khz(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_policy_caps(parser, section):
    caps = {}
    for key, value in parser.items(section):
        policy_id = key.removeprefix("cpu_max_policy")
        if policy_id == key or not policy_id.isdigit():
            continue
        khz = parse_khz(value)
        if khz is not None:
            caps[f"cpu_max_policy{int(policy_id)}"] = khz
    return caps


def parsed_power(parser):
    for section in ("general", "fan"):
        if not parser.has_section(section):
            raise ValueError(f"missing config section [{section}]")
    data = {
        "general": {"default_profile": parser.get("general", "default_profile")},
        "profiles": {},
        "fan_curves": {},
        "fan": {},
        "underclocks": {},
    }
    for name in PROFILES:
        section = f"profile.{name}"
        if not parser.has_section(section):
            raise ValueError(f"missing config section [{section}]")
        data["profiles"][name] = {
            "label": parser.get(section, "label", fallback="") or default_label(name),
            "cpu_governor": parser.get(section, "cpu_governor"),
            "cpu_max": parse_ratio(parser.get(section, "cpu_max")),
            "cpu_underclock": parser.get(section, "cpu_underclock"),
            "gpu_max": parse_ratio(parser.get(section, "gpu_max")),
            "gpu_max_mhz": parse_mhz(parser.get(section, "gpu_max_mhz", fallback="")),
            "gpu_min": parse_ratio(parser.get(section, "gpu_min")),
            "gpu_min_mhz": parse_mhz(parser.get(section, "gpu_min_mhz", fallback="")),
            "fan_curve": parser.get(section, "fan_curve"),
            **parse_policy_caps(parser, section),
        }
    for section in parser.sections():
        if section.startswith("fan_curve."):
            name = section.split(".", 1)[1]
            data["fan_curves"][name] = {
                "label": parser.get(section, "label", fallback="") or default_label(name),
                "curve": parser.get(section, "curve"),
            }
            continue
        if not section.startswith("underclock."):
            continue
        parts = section.split(".")
        if len(parts) == 3 and parse_policy_caps(parser, section):
            _, device_class, level = parts
            data["underclocks"].setdefault(device_class, {})[level] = dict(parser.items(section))
    data["fan"] = dict(parser.items("fan"))
    return data


EDITABLE_KEYS = ("cpu_governor", "cpu_underclock", "fan_curve")
LIMIT_KEYS = (("gpu_max_mhz", "gpu_max"), ("gpu_min_mhz", "gpu_min"))
UNDERCLOCK_OFF = ("", "none", "stock", "custom")


def ratio(value):
    return min(max(float(value), 0.0), 1.0)


def ratio_text(value):
    return f"{float(value):.2f}"


def policy_key(policy):
    return f"cpu_max_policy{policy['id']}"


def policy_keys(limits):
    return [policy_key(policy) for policy in limits["cpuPolicies"]]


def underclock_caps(profile, device_class, underclocks):
    level = str(profile.get("cpu_underclock", "")).strip().lower()
    if level in UNDERCLOCK_OFF:
        return {}
    return underclocks.get(device_class, {}).get(level, {})


def derived_limits(profile, limits, device_class, underclocks):
    gpu_hz = limits["gpuHz"]
    gpu_mhz = None
    gpu_min_mhz = None
    if gpu_hz:
        stock_hz = limits["gpuStockHz"]
        gpu_mhz = at_most(gpu_hz, int(stock_hz * ratio(profile["gpu_max"]))) // 1_000_000
        gpu_min_mhz = min(at_most(gpu_hz, int(stock_hz * ratio(profile["gpu_min"]))) // 1_000_000, gpu_mhz)
    derived = {"gpu_max_mhz": gpu_mhz, "gpu_min_mhz": gpu_min_mhz}
    table = underclock_caps(profile, device_class, underclocks)
    for policy in limits["cpuPolicies"]:
        khz = policy["khz"]
        preset = parse_khz(table.get(policy_key(policy)))
        if preset is not None:
            derived[policy_key(policy)] = at_most(khz, preset)
        elif device_class in underclocks:
            derived[policy_key(policy)] = khz[-1]
        else:
            derived[policy_key(policy)] = at_most(khz, int(khz[-1] * ratio(profile["cpu_max"])))
    return derived


def resolve_limits(data, limits, device_class):
    underclocks = data.get("underclocks", {})
    for profile in data["profiles"].values():
        for key, value in derived_limits(profile, limits, device_class, underclocks).items():
            if profile.get(key) is None:
                profile[key] = value
        if limits["gpuHz"]:
            profile["gpu_min_mhz"] = min(profile["gpu_min_mhz"], profile["gpu_max_mhz"])
    return data


def profile_overrides(profile, limits):
    out = {}
    for key in EDITABLE_KEYS:
        out[key] = str(profile[key])
    out["cpu_max"] = ratio_text(profile["cpu_max"])
    for mhz_key, ratio_key in LIMIT_KEYS:
        out[mhz_key] = parse_mhz(profile.get(mhz_key))
        out[ratio_key] = ratio_text(profile[ratio_key])
    for policy in limits["cpuPolicies"]:
        khz = parse_khz(profile.get(policy_key(policy)))
        out[policy_key(policy)] = None if khz is None else at_most(policy["khz"], khz)
    return out


def set_or_clear(parser, section, key, value, keep):
    if keep:
        if not parser.has_section(section):
            parser.add_section(section)
        parser.set(section, key, value)
    elif parser.has_section(section) and parser.has_option(section, key):
        parser.remove_option(section, key)


def render_power(data, factory, limits, device_class):
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(POWER_CONFIG)

    set_or_clear(parser, "general", "default_profile", data["general"]["default_profile"],
                 data["general"]["default_profile"] != factory["general"]["default_profile"])
    underclocks = data["underclocks"]
    preset_class = device_class in underclocks
    cpu_keys = policy_keys(limits)
    limit_keys = (*(mhz_key for mhz_key, _ in LIMIT_KEYS), *cpu_keys)
    for name in PROFILES:
        section = f"profile.{name}"
        profile = data["profiles"][name]
        overrides = profile_overrides(profile, limits)
        factory_overrides = profile_overrides(factory["profiles"][name], limits)
        derived = derived_limits(profile, limits, device_class, underclocks)
        in_etc = {key: overrides[key] is not None and parser.has_option(section, key)
                  for key in limit_keys if derived[key] is not None}
        for key in limit_keys:
            if overrides[key] is None and derived[key] is not None:
                overrides[key] = derived[key]
        if preset_class:
            cpu_write = (overrides["cpu_underclock"].strip().lower() == "custom"
                         or any(overrides[key] != derived[key] for key in cpu_keys))
            if cpu_write:
                overrides["cpu_underclock"] = "custom"
        else:
            cpu_write = (any(overrides[key] != derived[key] for key in cpu_keys)
                         or any(in_etc[key] for key in cpu_keys))
        edited = overrides != factory_overrides or any(in_etc.values())
        stale = [key for key in (parser.options(section) if parser.has_section(section) and cpu_keys else [])
                 if key.lower().startswith("cpu_max_policy") and key not in cpu_keys]
        for key in stale:
            set_or_clear(parser, section, key, "", False)
        for key in EDITABLE_KEYS:
            set_or_clear(parser, section, key, overrides[key], edited)
        if not edited:
            for key in ("cpu_max", *cpu_keys, *(key for pair in LIMIT_KEYS for key in pair)):
                set_or_clear(parser, section, key, "", False)
            continue
        for mhz_key, ratio_key in LIMIT_KEYS:
            value = overrides[mhz_key]
            if derived[mhz_key] is None:
                continue
            if value != derived[mhz_key] or in_etc[mhz_key]:
                set_or_clear(parser, section, mhz_key, str(value), True)
                set_or_clear(parser, section, ratio_key, "", False)
            else:
                set_or_clear(parser, section, mhz_key, "", False)
                set_or_clear(parser, section, ratio_key, overrides[ratio_key],
                             overrides[ratio_key] != factory_overrides[ratio_key])
        for key in cpu_keys:
            set_or_clear(parser, section, key, str(int(overrides[key])), cpu_write)
        if not preset_class:
            set_or_clear(parser, section, "cpu_max", overrides["cpu_max"],
                         not cpu_write and overrides["cpu_max"] != factory_overrides["cpu_max"])
        shadowed = [ratio_key for mhz_key, ratio_key in LIMIT_KEYS
                    if derived[mhz_key] is None
                    and parse_mhz(parser.get(section, mhz_key, fallback=None)) is not None]
        if ((preset_class or not cpu_keys) and parser.has_section(section)
                and parse_policy_caps(parser, section)):
            shadowed.append("cpu_max")
        for key in shadowed:
            set_or_clear(parser, section, key, "", False)

    for section in ("general", *(f"profile.{name}" for name in PROFILES)):
        if parser.has_section(section) and not parser.options(section):
            parser.remove_section(section)

    with tempfile.TemporaryFile("w+", encoding="utf-8") as f:
        parser.write(f)
        f.seek(0)
        return f.read()


def factory_power_defaults():
    try:
        return parse_power(FACTORY_POWER_CONFIG)
    except OSError:
        return parse_power()


def save_power_config(data):
    if not isinstance(data, dict) or not isinstance(data.get("general"), dict):
        raise ValueError("invalid power config")
    data["general"]["default_profile"] = data["general"].get("default_profile", "")
    if data["general"]["default_profile"] not in PROFILES:
        raise ValueError("invalid power config")
    env = device_env()
    limits = freq_limits(env)
    soc = env.get("ARMADA_SOC_CLASS", "")
    try:
        factory = resolve_limits(factory_power_defaults(), limits, soc)
        rendered = render_power(data, factory, limits, soc)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"malformed power config: {exc}")
    call("write_config", name="power", text=rendered)
