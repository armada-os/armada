import math
import os
import re
import shlex
import stat
import struct
import subprocess
from pathlib import Path

from .privileged import call


OS_VERSION_PATH = Path("/usr/lib/armada/version")
HDR_SESSION_FINALIZER = "/usr/libexec/armada/hdr-session-finalize"
TRUSTED_PATH = "/usr/bin:/usr/sbin:/bin:/sbin"
X11_SOCKET_DIR = Path("/tmp/.X11-unix")
XPROP = "/usr/bin/xprop"
RUNUSER = "/usr/sbin/runuser"
SESSION_USER = "armada"

_X_SOCKET_RE = re.compile(r"^X(0|[1-9][0-9]*)$")
_HDR_XPROPS = (
    "GAMESCOPE_XWAYLAND_SERVER_ID",
    "GAMESCOPE_DISPLAY_SUPPORTS_HDR",
    "GAMESCOPE_DISPLAY_HDR_ENABLED",
    "GAMESCOPE_HDR_OUTPUT_FEEDBACK",
    "GAMESCOPE_SDR_ON_HDR_CONTENT_BRIGHTNESS",
)


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
    pattern = re.compile(rf"^{re.escape(atom)}(?:\([^)]*\))?\s*=\s*([0-9]+)\s*$")
    values = []
    for line in output.splitlines():
        match = pattern.fullmatch(line.strip())
        if match is not None:
            try:
                values.append(int(match.group(1), 10))
            except ValueError:
                return None
    return values[0] if len(values) == 1 else None


def _cardinal_float(value):
    if value is None or value < 0 or value > 0xFFFFFFFF:
        return None
    decoded = struct.unpack("!f", struct.pack("!I", value))[0]
    return decoded if math.isfinite(decoded) and decoded >= 0 else None


def _unavailable_hdr_state(reason):
    return {
        "available": False,
        "display": None,
        "supportsHdr": False,
        "enabled": False,
        "outputFeedback": False,
        "sdrContentBrightnessNits": None,
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
        return {
            "available": True,
            "display": display,
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
            "reason": "ok",
        }

    reason = "primary-gamescope-root-not-found" if successful_query else "xprop-query-failed"
    return _unavailable_hdr_state(reason)


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
