import json
import os
import sys
from pathlib import Path

from .privileged import call

sys.path.insert(0, os.environ.get("ARMADA_GAME_TWEAKS_LIB", "/usr/lib/armada"))
import armada_game_tweaks

COMPAT_APPLIED_STATE = Path("/var/lib/armada/compat-applied.json")
FEX_PROFILES_CONFIG = Path("/usr/share/armada/fex-profiles.json")
PLUGIN_FEX_PROFILES_CONFIG = Path(__file__).resolve().parent.parent / "fex-profiles.json"


def load_fex_contract():
    path = FEX_PROFILES_CONFIG if FEX_PROFILES_CONFIG.exists() else PLUGIN_FEX_PROFILES_CONFIG
    with path.open(encoding="utf-8") as f:
        contract = json.load(f)
    profiles = contract.get("profiles")
    if not isinstance(profiles, dict) or "default" not in profiles:
        raise ValueError("invalid FEX profile contract")
    for profile in profiles.values():
        if not isinstance(profile, dict) or not isinstance(profile.get("config"), dict):
            raise ValueError("invalid FEX profile contract")
    return contract


def fex_profile_labels(contract):
    return {
        name: {"label": profile.get("label", name.title()), "config": profile.get("config", {})}
        for name, profile in contract["profiles"].items()
        if isinstance(profile, dict)
    }


def load_tweaks():
    return armada_game_tweaks.load()


def sanitize_tweaks(data):
    if not isinstance(data, dict):
        raise ValueError("tweaks must be an object")
    if len(json.dumps(data)) > 256 * 1024:
        raise ValueError("tweaks payload too large")
    clean = {"global": {}, "games": {}}
    if isinstance(data.get("global"), dict):
        clean["global"] = data["global"]
    raw_games = data.get("games")
    if isinstance(raw_games, dict):
        for gid, game in raw_games.items():
            if str(gid).isdigit() and isinstance(game, dict):
                clean["games"][str(gid)] = game
    return clean


def tweak_overrides(data):
    clean = sanitize_tweaks(data)
    return armada_game_tweaks.remove_factory_values(
        clean, armada_game_tweaks.load_defaults())


def save_tweaks(data):
    call("write_config", name="tweaks", text=json.dumps(tweak_overrides(data), indent=2, sort_keys=True) + "\n")


def load_compat_applied():
    try:
        with COMPAT_APPLIED_STATE.open(encoding="utf-8") as f:
            loaded = json.load(f)
    except (OSError, ValueError):
        loaded = {}
    appids = loaded.get("appids") if isinstance(loaded, dict) else None
    if not isinstance(appids, list):
        appids = []
    proton_default = loaded.get("protonDefault") if isinstance(loaded, dict) else ""
    return {
        "appids": sorted({str(appid) for appid in appids if str(appid).isdigit()}, key=int),
        "protonDefault": proton_default if isinstance(proton_default, str) else "",
    }


def save_compat_applied(appids, proton_default=None):
    clean = sorted({str(appid) for appid in appids if str(appid).isdigit()}, key=int)
    if proton_default is None:
        proton_default = load_compat_applied()["protonDefault"]
    state = {
        "appids": clean,
        "protonDefault": proton_default if isinstance(proton_default, str) else "",
    }
    text = json.dumps(state, indent=2, sort_keys=True) + "\n"
    call("write_config", name="compat-applied", text=text)
    return state
