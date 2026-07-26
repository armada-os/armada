import json
import math
import os
import re
import shlex
import stat
import struct
import subprocess
import threading
from pathlib import Path

from .privileged import call


OS_VERSION_PATH = Path("/usr/lib/armada/version")
AUTO_HDR_PREFERENCES_PATH = Path("/var/lib/armada/auto-hdr-profiles.json")
HDR_SESSION_FINALIZER = "/usr/libexec/armada/hdr-session-finalize"
TRUSTED_PATH = "/usr/bin:/usr/sbin:/bin:/sbin"
X11_SOCKET_DIR = Path("/tmp/.X11-unix")
XPROP = "/usr/bin/xprop"
RUNUSER = "/usr/sbin/runuser"
SESSION_USER = "armada"

_X_SOCKET_RE = re.compile(r"^X(0|[1-9][0-9]*)$")
_HDR_XPROPS = (
    "GAMESCOPE_XWAYLAND_SERVER_ID",
    "GAMESCOPE_DISPLAY_IS_EXTERNAL",
    "GAMESCOPE_DISPLAY_SUPPORTS_HDR",
    "GAMESCOPE_DISPLAY_HDR_ENABLED",
    "GAMESCOPE_HDR_OUTPUT_FEEDBACK",
    "GAMESCOPE_SDR_ON_HDR_CONTENT_BRIGHTNESS",
    "GAMESCOPE_HDR_ITM_SUPPORTED",
    "GAMESCOPE_HDR_ITM_ENABLE",
    "GAMESCOPE_HDR_ITM_SDR_NITS",
    "GAMESCOPE_HDR_ITM_TARGET_NITS",
    "GAMESCOPE_HDR_ITM_SUPPORTED_MODES",
    "GAMESCOPE_HDR_ITM_MODE",
    "GAMESCOPE_HDR_ITM_EFFECTIVE_MODE",
)

AUTO_HDR_SDR_NITS = 203
AUTO_HDR_TARGET_NITS = 650
AUTO_HDR_MODE_EFFICIENT = 1
AUTO_HDR_MODE_HIGH_QUALITY = 2
AUTO_HDR_SUPPORTED_MODE_EFFICIENT = 1
AUTO_HDR_SUPPORTED_MODE_HIGH_QUALITY = 2
AUTO_HDR_PREFERENCES_VERSION = 2
_APP_ID_RE = re.compile(r"^[1-9][0-9]{0,9}$")
_AUTO_HDR_LOCK = threading.Lock()


def run_cmd(cmd, timeout=5, capture=True):
    try:
        return subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def cpu_device_class():
    return device_env().get("ARMADA_SOC_CLASS", "")


def hdr_capable():
    """Return the immutable image policy's qualified internal-panel state."""
    proc = run_cmd(
        [
            "/usr/bin/env",
            "-i",
            f"PATH={TRUSTED_PATH}",
            "/bin/bash",
            "--noprofile",
            "--norc",
            "-p",
            HDR_SESSION_FINALIZER,
        ]
    )
    if proc is None or proc.returncode != 0:
        return False
    expected = [
        "builtin",
        "export",
        "--",
        "ARMADA_HDR_CAPABLE=1",
        "||",
        "exit",
        "1",
    ]
    for line in proc.stdout.splitlines():
        try:
            if shlex.split(line) == expected:
                return True
        except ValueError:
            return False
    return False


def _x_display_numbers():
    try:
        entries = list(X11_SOCKET_DIR.iterdir())
    except OSError:
        return []

    result = []
    for entry in entries:
        match = _X_SOCKET_RE.fullmatch(entry.name)
        if match is None:
            continue
        try:
            if not stat.S_ISSOCK(entry.stat(follow_symlinks=False).st_mode):
                continue
        except OSError:
            continue
        result.append(int(match.group(1)))
    return sorted(set(result))


def _parse_xprop_cardinal(output, atom):
    pattern = re.compile(rf"^{re.escape(atom)}\(CARDINAL\)\s*=\s*([0-9]+)\s*$")
    values = []
    for line in output.splitlines():
        match = pattern.fullmatch(line.strip())
        if match is not None:
            try:
                values.append(int(match.group(1), 10))
            except ValueError:
                return None
    return values[0] if len(values) == 1 else None


def _xprop_atom_present(output, atom):
    pattern = re.compile(rf"^{re.escape(atom)}(?:\([^)]*\))?\s*=")
    return any(pattern.match(line.strip()) is not None for line in output.splitlines())


def _cardinal_float(value):
    if value is None or value < 0 or value > 0xFFFFFFFF:
        return None
    decoded = struct.unpack("!f", struct.pack("!I", value))[0]
    return decoded if math.isfinite(decoded) and decoded >= 0 else None


def _unavailable_hdr_state(reason):
    return {
        "available": False,
        "display": None,
        "displayIsExternal": None,
        "supportsHdr": False,
        "enabled": False,
        "outputFeedback": False,
        "sdrContentBrightnessNits": None,
        "autoHdrSupported": False,
        "autoHdrEnabled": False,
        "autoHdrSdrNits": None,
        "autoHdrTargetNits": None,
        "autoHdrSupportedModes": 0,
        "autoHdrModeProtocolPresent": False,
        "autoHdrModeProtocol": False,
        "autoHdrMode": None,
        "autoHdrEffectiveMode": None,
        "reason": reason,
    }


def _xprop_command(display):
    command = [XPROP, "-display", display, "-root", *_HDR_XPROPS]
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None or geteuid() != 0:
        return command
    # Decky Loader and plugin backends run as root, but Gamescope's Xwayland
    # socket authorizes the owning session user. Drop privileges and discard
    # the root service environment for this read-only query.
    return [
        RUNUSER,
        "-u",
        SESSION_USER,
        "--",
        "/usr/bin/env",
        "-i",
        f"PATH={TRUSTED_PATH}",
        *command,
    ]


def _xprop_set_command(display, atom, value):
    command = [
        XPROP,
        "-display",
        display,
        "-root",
        "-f",
        atom,
        "32c",
        "-set",
        atom,
        str(value),
    ]
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None or geteuid() != 0:
        return command
    return [
        RUNUSER,
        "-u",
        SESSION_USER,
        "--",
        "/usr/bin/env",
        "-i",
        f"PATH={TRUSTED_PATH}",
        *command,
    ]


def get_hdr_runtime_state():
    """Return state from Gamescope's primary (server id 0) X root."""
    displays = _x_display_numbers()
    if not displays:
        return _unavailable_hdr_state("no-x11-sockets")

    successful_query = False
    for number in displays:
        display = f":{number}"
        proc = run_cmd(_xprop_command(display), timeout=2)
        if proc is None or proc.returncode != 0:
            continue
        successful_query = True
        if _parse_xprop_cardinal(proc.stdout, "GAMESCOPE_XWAYLAND_SERVER_ID") != 0:
            continue

        brightness_bits = _parse_xprop_cardinal(
            proc.stdout, "GAMESCOPE_SDR_ON_HDR_CONTENT_BRIGHTNESS"
        )
        display_is_external = _parse_xprop_cardinal(
            proc.stdout, "GAMESCOPE_DISPLAY_IS_EXTERNAL"
        )
        auto_hdr_supported = _parse_xprop_cardinal(
            proc.stdout, "GAMESCOPE_HDR_ITM_SUPPORTED"
        ) == 1
        auto_hdr_enabled = _parse_xprop_cardinal(
            proc.stdout, "GAMESCOPE_HDR_ITM_ENABLE"
        ) == 1
        supported_modes_present = _xprop_atom_present(
            proc.stdout, "GAMESCOPE_HDR_ITM_SUPPORTED_MODES"
        )
        requested_mode_present = _xprop_atom_present(
            proc.stdout, "GAMESCOPE_HDR_ITM_MODE"
        )
        effective_mode_present = _xprop_atom_present(
            proc.stdout, "GAMESCOPE_HDR_ITM_EFFECTIVE_MODE"
        )
        supported_modes_raw = _parse_xprop_cardinal(
            proc.stdout, "GAMESCOPE_HDR_ITM_SUPPORTED_MODES"
        )
        requested_mode = _parse_xprop_cardinal(
            proc.stdout, "GAMESCOPE_HDR_ITM_MODE"
        )
        effective_mode = _parse_xprop_cardinal(
            proc.stdout, "GAMESCOPE_HDR_ITM_EFFECTIVE_MODE"
        )
        mode_protocol_present = (
            supported_modes_present
            or requested_mode_present
            or effective_mode_present
        )
        mode_protocol_complete = (
            supported_modes_present
            and requested_mode_present
            and effective_mode_present
        )
        supported_modes_valid = (
            supported_modes_raw is not None
            and supported_modes_raw != 0
            and (supported_modes_raw & ~(
                AUTO_HDR_SUPPORTED_MODE_EFFICIENT |
                AUTO_HDR_SUPPORTED_MODE_HIGH_QUALITY
            )) == 0
        )
        requested_mode_valid = requested_mode in (
            AUTO_HDR_MODE_EFFICIENT,
            AUTO_HDR_MODE_HIGH_QUALITY,
        )
        effective_mode_valid = effective_mode in (
            0,
            AUTO_HDR_MODE_EFFICIENT,
            AUTO_HDR_MODE_HIGH_QUALITY,
        )
        mode_protocol = (
            mode_protocol_complete
            and supported_modes_valid
            and requested_mode_valid
            and effective_mode_valid
            and (supported_modes_raw & requested_mode) != 0
        )
        supported_modes = supported_modes_raw
        if not mode_protocol_present:
            supported_modes = (
                AUTO_HDR_SUPPORTED_MODE_EFFICIENT if auto_hdr_supported else 0
            )
        elif not mode_protocol:
            supported_modes = 0
        if not mode_protocol_present and auto_hdr_supported:
            requested_mode = AUTO_HDR_MODE_EFFICIENT
            effective_mode = AUTO_HDR_MODE_EFFICIENT if auto_hdr_enabled else 0
        elif not mode_protocol:
            requested_mode = None
            effective_mode = None
        return {
            "available": True,
            "display": display,
            "displayIsExternal": (
                bool(display_is_external)
                if display_is_external in (0, 1)
                else None
            ),
            "supportsHdr": _parse_xprop_cardinal(
                proc.stdout, "GAMESCOPE_DISPLAY_SUPPORTS_HDR"
            )
            == 1,
            # Gamescope removes these atoms in some valid off states. Once the
            # primary root is proven, absence is an observable false/disabled
            # state rather than an X query failure.
            "enabled": _parse_xprop_cardinal(
                proc.stdout, "GAMESCOPE_DISPLAY_HDR_ENABLED"
            )
            == 1,
            "outputFeedback": _parse_xprop_cardinal(
                proc.stdout, "GAMESCOPE_HDR_OUTPUT_FEEDBACK"
            )
            == 1,
            "sdrContentBrightnessNits": _cardinal_float(brightness_bits),
            "autoHdrSupported": auto_hdr_supported,
            "autoHdrEnabled": auto_hdr_enabled,
            "autoHdrSdrNits": _parse_xprop_cardinal(
                proc.stdout, "GAMESCOPE_HDR_ITM_SDR_NITS"
            ),
            "autoHdrTargetNits": _parse_xprop_cardinal(
                proc.stdout, "GAMESCOPE_HDR_ITM_TARGET_NITS"
            ),
            "autoHdrSupportedModes": supported_modes,
            "autoHdrModeProtocolPresent": mode_protocol_present,
            "autoHdrModeProtocol": mode_protocol,
            "autoHdrMode": requested_mode,
            "autoHdrEffectiveMode": effective_mode,
            "reason": "ok",
        }

    reason = "primary-gamescope-root-not-found" if successful_query else "xprop-query-failed"
    return _unavailable_hdr_state(reason)


def _normalize_app_id(app_id):
    if isinstance(app_id, bool):
        raise ValueError("Invalid Steam AppID")
    value = str(app_id)
    if _APP_ID_RE.fullmatch(value) is None:
        raise ValueError("Invalid Steam AppID")
    numeric = int(value, 10)
    if numeric == 769 or numeric > 0xFFFFFFFF:
        raise ValueError("Invalid Steam AppID")
    return value


def _validate_auto_hdr_preferences(data):
    if not isinstance(data, dict) or set(data) != {"version", "global", "apps"}:
        raise ValueError("Invalid Auto HDR preferences schema")
    if (
        type(data["version"]) is not int
        or data["version"] != AUTO_HDR_PREFERENCES_VERSION
    ):
        raise ValueError("Unsupported Auto HDR preferences version")
    global_preference = data["global"]
    if (
        not isinstance(global_preference, dict)
        or set(global_preference) != {"enabled"}
        or not isinstance(global_preference["enabled"], bool)
    ):
        raise ValueError("Invalid global Auto HDR preference")
    apps = data["apps"]
    if not isinstance(apps, dict):
        raise ValueError("Invalid per-game Auto HDR preferences")
    normalized_apps = {}
    for raw_app_id, override in apps.items():
        app_id = _normalize_app_id(raw_app_id)
        if not isinstance(override, dict) or not override:
            raise ValueError("Invalid per-game Auto HDR override")
        if set(override) != {"enabled"}:
            raise ValueError("Invalid per-game Auto HDR override")
        if not isinstance(override["enabled"], bool):
            raise ValueError("Invalid per-game Auto HDR enabled override")
        normalized_apps[app_id] = {"enabled": override["enabled"]}
    return {
        "version": AUTO_HDR_PREFERENCES_VERSION,
        "global": {"enabled": global_preference["enabled"]},
        "apps": normalized_apps,
    }


def _migrate_auto_hdr_preferences_v1(data):
    if not isinstance(data, dict) or set(data) != {"version", "global", "apps"}:
        raise ValueError("Invalid Auto HDR v1 preferences schema")
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("Unsupported Auto HDR preferences version")
    global_preference = data["global"]
    if (
        not isinstance(global_preference, dict)
        or set(global_preference) != {"enabled", "profile"}
        or not isinstance(global_preference["enabled"], bool)
        or global_preference["profile"] not in {"eco", "quality"}
        or not isinstance(data["apps"], dict)
    ):
        raise ValueError("Invalid Auto HDR v1 preferences")
    apps = {}
    for raw_app_id, override in data["apps"].items():
        app_id = _normalize_app_id(raw_app_id)
        if (
            not isinstance(override, dict)
            or not override
            or not set(override).issubset({"enabled", "profile"})
            or (
                "enabled" in override
                and not isinstance(override["enabled"], bool)
            )
            or (
                "profile" in override
                and override["profile"] not in {"eco", "quality"}
            )
        ):
            raise ValueError("Invalid Auto HDR v1 per-game override")
        if "enabled" in override:
            apps[app_id] = {"enabled": override["enabled"]}
    return {
        "version": AUTO_HDR_PREFERENCES_VERSION,
        "global": {"enabled": global_preference["enabled"]},
        "apps": apps,
    }


def _write_auto_hdr_preferences(preferences):
    validated = _validate_auto_hdr_preferences(preferences)
    text = json.dumps(validated, sort_keys=True, separators=(",", ":")) + "\n"
    call("write_config", name="auto-hdr-profiles", text=text)


def _seed_auto_hdr_preferences_locked():
    runtime = get_hdr_runtime_state()
    enabled = False
    if (
        runtime.get("available") is True
        and runtime.get("autoHdrSupported") is True
        and runtime.get("autoHdrEnabled") in (True, False)
    ):
        enabled = runtime["autoHdrEnabled"]
    preferences = {
        "version": AUTO_HDR_PREFERENCES_VERSION,
        "global": {"enabled": enabled},
        "apps": {},
    }
    _write_auto_hdr_preferences(preferences)
    return preferences


def _load_auto_hdr_preferences_locked():
    try:
        text = AUTO_HDR_PREFERENCES_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _seed_auto_hdr_preferences_locked()
    except OSError as exc:
        raise RuntimeError("Could not read Auto HDR preferences") from exc
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid Auto HDR preferences JSON") from exc
    canonical = (
        _migrate_auto_hdr_preferences_v1(data)
        if isinstance(data, dict) and data.get("version") == 1
        else _validate_auto_hdr_preferences(data)
    )
    if canonical != data:
        _write_auto_hdr_preferences(canonical)
    return canonical


def _validate_auto_hdr_scope(scope, app_id):
    if scope == "global":
        if app_id is not None:
            raise ValueError("Global Auto HDR scope cannot include an AppID")
        return scope, None
    if scope == "game":
        return scope, _normalize_app_id(app_id)
    raise ValueError("Auto HDR scope must be global or game")


def _resolve_auto_hdr_preference(preferences, scope, app_id):
    scope, app_id = _validate_auto_hdr_scope(scope, app_id)
    override = preferences["apps"].get(app_id, {}) if scope == "game" else {}
    return {
        "enabled": override.get("enabled", preferences["global"]["enabled"]),
    }


def _rollback_auto_hdr_runtime_locked(before):
    display = before.get("display")
    previous_mode = before.get("autoHdrMode")
    previous_enabled = before.get("autoHdrEnabled")
    if (
        not display
        or previous_mode not in (
            AUTO_HDR_MODE_EFFICIENT,
            AUTO_HDR_MODE_HIGH_QUALITY,
        )
        or not isinstance(previous_enabled, bool)
    ):
        return False
    for atom, value in (
        ("GAMESCOPE_HDR_ITM_MODE", previous_mode),
        ("GAMESCOPE_HDR_ITM_ENABLE", int(previous_enabled)),
    ):
        proc = run_cmd(_xprop_set_command(display, atom, value), timeout=2)
        if proc is None or proc.returncode != 0:
            return False
    rollback = get_hdr_runtime_state()
    return (
        rollback.get("available") is True
        and rollback.get("display") == display
        and rollback.get("autoHdrModeProtocol") is True
        and rollback.get("autoHdrMode") == previous_mode
        and rollback.get("autoHdrEnabled") == previous_enabled
    )


def _apply_auto_hdr_preference_locked(resolved):
    enabled = resolved["enabled"]
    before = get_hdr_runtime_state()
    if not before.get("available") or before.get("display") is None:
        raise RuntimeError(
            f"Gamescope HDR state unavailable: {before.get('reason', 'unknown')}"
        )
    if not before.get("autoHdrSupported"):
        raise RuntimeError("Gamescope does not advertise Auto HDR support")
    if not before.get("autoHdrModeProtocol"):
        raise RuntimeError("Gamescope Auto HDR mode protocol is unavailable or malformed")
    if not (
        before.get("autoHdrSupportedModes", 0)
        & AUTO_HDR_MODE_HIGH_QUALITY
    ):
        raise RuntimeError("Gamescope does not support the Auto HDR engine")
    if enabled and not (
        before.get("displayIsExternal") is False
        and before.get("supportsHdr") is True
        and before.get("enabled") is True
        and before.get("outputFeedback") is True
    ):
        raise RuntimeError("Auto HDR requires a verified active internal HDR output")

    writes = []
    if enabled:
        writes.extend(
            (
                ("GAMESCOPE_HDR_ITM_SDR_NITS", AUTO_HDR_SDR_NITS),
                ("GAMESCOPE_HDR_ITM_TARGET_NITS", AUTO_HDR_TARGET_NITS),
                ("GAMESCOPE_HDR_ITM_MODE", AUTO_HDR_MODE_HIGH_QUALITY),
                ("GAMESCOPE_HDR_ITM_ENABLE", 1),
            )
        )
    else:
        writes.extend(
            (
                ("GAMESCOPE_HDR_ITM_MODE", AUTO_HDR_MODE_HIGH_QUALITY),
                ("GAMESCOPE_HDR_ITM_ENABLE", 0),
            )
        )

    failure = None
    for atom, value in writes:
        proc = run_cmd(_xprop_set_command(before["display"], atom, value), timeout=2)
        if proc is None or proc.returncode != 0:
            failure = f"Could not write Gamescope property {atom}"
            break
    after = get_hdr_runtime_state() if failure is None else {}
    converged = (
        after.get("available") is True
        and after.get("display") == before["display"]
        and after.get("autoHdrModeProtocol") is True
        and after.get("autoHdrMode") == AUTO_HDR_MODE_HIGH_QUALITY
        and after.get("autoHdrEnabled") == enabled
        and (
            after.get("autoHdrSupportedModes", 0)
            & AUTO_HDR_MODE_HIGH_QUALITY
        )
    )
    if enabled:
        converged = converged and (
            after.get("autoHdrSupported") is True
            and after.get("displayIsExternal") is False
            and after.get("supportsHdr") is True
            and after.get("enabled") is True
            and after.get("outputFeedback") is True
            and after.get("autoHdrSdrNits") == AUTO_HDR_SDR_NITS
            and after.get("autoHdrTargetNits") == AUTO_HDR_TARGET_NITS
        )
    if failure is None and converged:
        return after
    if not _rollback_auto_hdr_runtime_locked(before):
        raise RuntimeError(
            "Gamescope Auto HDR preference rollback failed; state is uncertain"
        )
    raise RuntimeError(failure or "Gamescope Auto HDR preference did not converge")


def _auto_hdr_snapshot(preferences, active_scope, active_app_id, runtime):
    scope, app_id = _validate_auto_hdr_scope(active_scope, active_app_id)
    override = preferences["apps"].get(app_id) if scope == "game" else None
    return {
        "version": AUTO_HDR_PREFERENCES_VERSION,
        "global": dict(preferences["global"]),
        "override": dict(override) if override is not None else None,
        "scope": scope,
        "appId": app_id,
        "resolved": _resolve_auto_hdr_preference(preferences, scope, app_id),
        "runtime": runtime,
    }


def get_auto_hdr_preferences(active_scope="global", active_app_id=None):
    with _AUTO_HDR_LOCK:
        preferences = _load_auto_hdr_preferences_locked()
        return _auto_hdr_snapshot(
            preferences,
            active_scope,
            active_app_id,
            get_hdr_runtime_state(),
        )


def reconcile_auto_hdr(active_scope="global", active_app_id=None):
    with _AUTO_HDR_LOCK:
        preferences = _load_auto_hdr_preferences_locked()
        resolved = _resolve_auto_hdr_preference(
            preferences, active_scope, active_app_id
        )
        runtime = _apply_auto_hdr_preference_locked(resolved)
        return _auto_hdr_snapshot(
            preferences, active_scope, active_app_id, runtime
        )


def update_auto_hdr_preferences(
    target_scope,
    target_app_id,
    active_scope,
    active_app_id,
    patch,
):
    target_scope, target_app_id = _validate_auto_hdr_scope(
        target_scope, target_app_id
    )
    active_scope, active_app_id = _validate_auto_hdr_scope(
        active_scope, active_app_id
    )
    if not isinstance(patch, dict) or not patch:
        raise ValueError("Auto HDR preference patch must not be empty")
    if set(patch) != {"enabled"}:
        raise ValueError("Invalid Auto HDR preference patch")

    with _AUTO_HDR_LOCK:
        current = _load_auto_hdr_preferences_locked()
        updated = {
            "version": current["version"],
            "global": dict(current["global"]),
            "apps": {
                app_id: dict(override)
                for app_id, override in current["apps"].items()
            },
        }
        target = (
            updated["global"]
            if target_scope == "global"
            else updated["apps"].setdefault(target_app_id, {})
        )
        for key, value in patch.items():
            if value is None:
                if target_scope == "global":
                    raise ValueError("Global Auto HDR preferences cannot inherit")
                target.pop(key, None)
            elif not isinstance(value, bool):
                raise ValueError("Auto HDR enabled preference must be a boolean")
            else:
                target[key] = value
        if target_scope == "game" and not target:
            updated["apps"].pop(target_app_id, None)
        updated = _validate_auto_hdr_preferences(updated)
        resolved = _resolve_auto_hdr_preference(
            updated, active_scope, active_app_id
        )
        runtime = _apply_auto_hdr_preference_locked(resolved)
        try:
            _write_auto_hdr_preferences(updated)
        except Exception as exc:
            previous_resolved = _resolve_auto_hdr_preference(
                current, active_scope, active_app_id
            )
            try:
                _apply_auto_hdr_preference_locked(previous_resolved)
            except Exception as rollback_exc:
                raise RuntimeError(
                    "Auto HDR preference file write and runtime rollback failed"
                ) from rollback_exc
            raise RuntimeError("Could not persist Auto HDR preferences") from exc
        return _auto_hdr_snapshot(updated, active_scope, active_app_id, runtime)


def device_env():
    try:
        env = call("get_device_env").get("env")
        if isinstance(env, dict):
            return {str(k): str(v) for k, v in env.items()}
    except Exception:
        pass
    helper = os.environ.get("ARMADA_DEVICE_ENV", "/usr/libexec/armada/device-env")
    proc = run_cmd([helper])
    env = {}
    if proc is None:
        return env
    for line in proc.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            try:
                env[key] = shlex.split(value)[0] if value else ""
            except ValueError:
                env[key] = value
    return env


def ssh_enabled():
    try:
        return bool(call("get_ssh_enabled").get("enabled"))
    except Exception:
        pass
    active = run_cmd(["/usr/bin/systemctl", "is-active", "sshd"])
    active_s = active.stdout.strip() if active else ""
    return active_s == "active"


def os_version():
    return read_text(OS_VERSION_PATH) or "unknown"


def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def set_ssh_enabled(enabled):
    return bool(call("set_ssh_enabled", enabled=bool(enabled)).get("enabled"))
