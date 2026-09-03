import copy
import json
import pathlib


DEFAULTS_CONFIG = pathlib.Path("/usr/share/armada/game-tweaks.json")
OVERRIDES_CONFIG = pathlib.Path("/etc/armada/game-tweaks.json")


def _read_object(path):
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _normalize(data):
    normalized = copy.deepcopy(data)
    if not isinstance(normalized.get("global"), dict):
        normalized["global"] = {}
    games = normalized.get("games")
    normalized["games"] = {
        str(appid): settings for appid, settings in games.items()
        if str(appid).isdigit() and isinstance(settings, dict)
    } if isinstance(games, dict) else {}
    return normalized


def load_defaults(path=None):
    return _normalize(_read_object(path or DEFAULTS_CONFIG))


def load(defaults_path=None, overrides_path=None):
    data = load_defaults(defaults_path)
    overrides = _read_object(overrides_path or OVERRIDES_CONFIG)
    if isinstance(overrides.get("global"), dict):
        data["global"].update(overrides["global"])
    if isinstance(overrides.get("games"), dict):
        data["games"] = _normalize({"games": overrides["games"]})["games"]
    return data


def merged_settings(tweaks, appid):
    settings = dict(tweaks.get("global") or {})
    if not appid:
        return settings
    game = (tweaks.get("games") or {}).get(str(appid))
    if not isinstance(game, dict) or game.get("enabled") is False:
        return settings
    global_env = settings.get("env")
    settings.update(game)
    if isinstance(global_env, dict) and isinstance(game.get("env"), dict):
        merged_env = {**global_env, **game["env"]}
        settings["env"] = {
            key: value for key, value in merged_env.items() if value is not None
        }
    return settings


def remove_factory_values(data, defaults):
    result = copy.deepcopy(data)
    global_settings = result.get("global")
    factory_global = defaults.get("global")
    if isinstance(global_settings, dict) and isinstance(factory_global, dict):
        result["global"] = {
            key: value for key, value in global_settings.items()
            if key not in factory_global or value != factory_global[key]
        }
    return result
