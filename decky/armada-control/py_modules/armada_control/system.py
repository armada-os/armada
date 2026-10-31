import json
import os
import shlex
import subprocess
from pathlib import Path

from .privileged import call
from .proc import clean_env


OS_VERSION_PATH = Path("/usr/lib/armada/version")
MEM_SLEEP_PATH = Path("/sys/power/mem_sleep")
SLEEP_DEBUG_COMMAND = Path("/usr/bin/armada-sleep-debug")
SLEEP_DEBUG_MODULE = Path("/usr/lib/armada/armada_sleep_debug.py")
SLEEP_LOG_HOOK_SOURCE = Path(__file__).with_name("sleep_debug_hook.sh")
SLEEP_LOG_HOOK = Path("/etc/armada/sleep-debug-hook")
SLEEP_LOG_DROPIN = Path("/etc/systemd/system/systemd-suspend.service.d/90-armada-sleep-debug.conf")
PANEL_CALIBRATION = "/usr/libexec/armada/panel-calibration"
SLEEP_MODE_LABELS = {
    "s2idle": "Native",
    "fake": "Fake",
}
DESKTOP_MODE_LABELS = {
    "mobile": "Plasma Mobile",
    "desktop": "Plasma Desktop"
}


def run_cmd(cmd, timeout=5, capture=True):
    try:
        return subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            env=clean_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return None


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


def mtp_enabled():
    try:
        return bool(call("get_mtp_enabled").get("enabled"))
    except Exception:
        pass
    active = run_cmd(["/usr/bin/systemctl", "is-active", "armada-mtp.service"])
    active_s = active.stdout.strip() if active else ""
    return active_s == "active"


def os_version():
    return read_text(OS_VERSION_PATH) or "unknown"


def abl_version():
    try:
        return str(call("get_abl_version").get("version") or "unknown")
    except Exception:
        return "unknown"


def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def swipe_gestures_enabled():
    try:
        return bool(call("get_swipe_gestures_enabled")["enabled"])
    except Exception:
        return True


def set_swipe_gestures_enabled(enabled):
    return bool(call("set_swipe_gestures_enabled", enabled=enabled)["enabled"])


def gyro_state():
    try:
        state = call("get_gyro")
        return {"supported": bool(state["supported"]), "enabled": bool(state["enabled"])}
    except Exception:
        return {"supported": False, "enabled": False}


def set_gyro_enabled(enabled):
    return bool(call("set_gyro_enabled", enabled=enabled)["enabled"])


def set_ssh_enabled(enabled):
    return bool(call("set_ssh_enabled", enabled=bool(enabled)).get("enabled"))


def set_mtp_enabled(enabled):
    return bool(call("set_mtp_enabled", enabled=bool(enabled)).get("enabled"))


def panel_tool(mode, *args, timeout=5):
    proc = run_cmd([PANEL_CALIBRATION, mode, *args], timeout=timeout)
    if proc is None or proc.returncode != 0:
        raise RuntimeError(f"panel-calibration {mode} failed")
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def panel_calibration():
    return panel_tool("status")


def panel_rate():
    return panel_tool("rate")


def step_panel(attr, direction):
    return panel_tool("step", attr, direction)


def set_panel(attr, value):
    panel_tool("set", attr, str(int(value)))
    return True


def save_panel(attr):
    return panel_tool("save", attr)


def calibrate_panel():
    # A run is about a dozen 1 s readings at worst.
    return panel_tool("calibrate", timeout=60)


def bottom_screen_enabled():
    try:
        return bool(call("get_bottom_screen_enabled").get("enabled"))
    except Exception:
        return False


def set_bottom_screen_enabled(enabled):
    return bool(call("set_bottom_screen_enabled", enabled=bool(enabled)).get("enabled"))


def bottom_screen_status():
    try:
        result = call("get_bottom_screen_brightness")
        supported = bool(result.get("supported"))
        return {
            "supported": supported,
            "brightness": int(result.get("brightness", 0)) if supported else 0,
            "active": bool(result.get("active")),
        }
    except Exception:
        return {"supported": False, "brightness": 0, "active": False}


def bottom_screen_brightness():
    result = bottom_screen_status()
    return result["brightness"] if result["supported"] else None


def bottom_screen_active():
    return bottom_screen_status()["active"]


def set_bottom_screen_brightness(brightness):
    return int(call("set_bottom_screen_brightness", brightness=brightness).get("brightness", 0))


def set_companion_locked(locked):
    return bool(call("set_companion_locked", locked=bool(locked)).get("locked"))


def desktop_mode() -> str:
    try:
        value = str(call("get_desktop_mode").get("value", ""))
    except Exception:
        return "desktop"

    return value if value in DESKTOP_MODE_LABELS else "desktop"


def set_desktop_mode(value: str) -> str:
    return str(
        call("set_desktop_mode", value=str(value)).get("value")
    )

def desktop_modes():
    modes = ["desktop", "mobile"]
    return [{"data": mode, "label": DESKTOP_MODE_LABELS[mode]} for mode in modes]

def sleep_modes():
    advertised = {word.strip("[]") for word in read_text(MEM_SLEEP_PATH).split()}
    modes = (["s2idle"] if "s2idle" in advertised else []) + ["fake"]
    return [{"data": mode, "label": SLEEP_MODE_LABELS[mode]} for mode in modes]


def set_sleep_mode(value):
    return str(call("set_sleep_mode", value=str(value)).get("value"))


def sleep_log_dropin():
    return (
        "[Service]\n"
        "ExecStartPre=-/etc/armada/sleep-debug-hook prepare\n"
        "ExecStopPost=-/etc/armada/sleep-debug-hook collect\n"
    )


def get_sleep_logs_enabled():
    enabled = SLEEP_LOG_DROPIN.is_file()
    if enabled and SLEEP_DEBUG_MODULE.is_file() and (
        read_text(SLEEP_LOG_DROPIN) != sleep_log_dropin().strip()
        or read_text(SLEEP_LOG_HOOK) != read_text(SLEEP_LOG_HOOK_SOURCE)
    ):
        try:
            set_sleep_logs_enabled(True)
        except (RuntimeError, OSError):
            pass
    return enabled


def sleep_log_directory():
    result = run_cmd([
        "busctl", "--json=short", "get-property", "org.freedesktop.systemd1",
        "/org/freedesktop/systemd1/unit/systemd_2dsuspend_2eservice",
        "org.freedesktop.systemd1.Service", "Environment", "EnvironmentFiles",
        "PassEnvironment", "UnsetEnvironment",
    ])
    if result is None or result.returncode:
        return None
    try:
        environment, files, passed, unset = [json.loads(line)["data"] for line in result.stdout.splitlines()]
        # Let systemd own environment-file parsing; don't show a guessed path.
        if files:
            return None
        values = {}
        if "ARMADA_SLEEP_DEBUG_REPORT_DIR" in passed:
            manager = run_cmd(["busctl", "--json=short", "get-property", "org.freedesktop.systemd1",
                               "/org/freedesktop/systemd1", "org.freedesktop.systemd1.Manager", "Environment"])
            if manager is None or manager.returncode:
                return None
            values.update(entry.split("=", 1) for entry in json.loads(manager.stdout)["data"])
        values.update(entry.split("=", 1) for entry in environment)
        name = "ARMADA_SLEEP_DEBUG_REPORT_DIR"
        for entry in unset:
            key, separator, value = entry.partition("=")
            if not separator or values.get(key) == value:
                values.pop(key, None)
        env = clean_env()
        env.pop(name, None)
        if name in values:
            env[name] = values[name]
        directory = subprocess.run(["/usr/bin/bash", str(SLEEP_LOG_HOOK_SOURCE), "report-directory"],
                                   capture_output=True, text=True, check=True, timeout=5, env=env).stdout.strip()
        return directory if Path(directory).is_absolute() else None
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        return None


def get_sleep_logs_status():
    return {"enabled": get_sleep_logs_enabled(), "directory": sleep_log_directory()}


def set_sleep_logs_enabled(enabled):
    if enabled:
        if not all(p.is_file() for p in (SLEEP_DEBUG_COMMAND, SLEEP_DEBUG_MODULE, SLEEP_LOG_HOOK_SOURCE)):
            raise RuntimeError("Native sleep logging is unavailable.")
        SLEEP_LOG_HOOK.parent.mkdir(parents=True, exist_ok=True)
        SLEEP_LOG_HOOK.write_bytes(SLEEP_LOG_HOOK_SOURCE.read_bytes())
        os.chmod(SLEEP_LOG_HOOK, 0o755)
        SLEEP_LOG_DROPIN.parent.mkdir(parents=True, exist_ok=True)
        SLEEP_LOG_DROPIN.write_text(
            sleep_log_dropin(),
            encoding="utf-8",
        )
    else:
        SLEEP_LOG_DROPIN.unlink(missing_ok=True)
        run_cmd([str(SLEEP_DEBUG_COMMAND), "restore"])

    try:
        subprocess.run(
            ["/usr/bin/systemctl", "daemon-reload"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr.strip() or "Could not reload systemd sleep logging.") from exc
    except subprocess.SubprocessError as exc:
        raise RuntimeError("Could not reload systemd sleep logging.") from exc

    return bool(enabled)


CORE_PRESET_VARS = (
    ("big", "Big Cores", "ARMADA_BIG_CORES"),
    ("prime", "Prime Cores", "ARMADA_PRIME_CORES"),
    ("little", "Little Cores", "ARMADA_LITTLE_CORES"),
)


def perf_info(env=None):
    governors = [
        g for g in read_text(
            Path("/sys/devices/system/cpu/cpufreq/policy0/scaling_available_governors")
        ).split()
        # userspace = kernel does no scaling, waits for a scaling_setspeed
        # writer; nothing on the image writes it, so it would freeze clocks.
        if g != "userspace"
    ]
    schedulers = ["eevdf"] + [
        name for name in ("cosmos", "lavd") if Path(f"/usr/bin/scx_{name}").exists()
    ]
    env = device_env() if env is None else env
    presets = [{"data": "all", "label": "All Cores"}]
    for key, label, var in CORE_PRESET_VARS:
        cpulist = env.get(var, "")
        if cpulist:
            presets.append({"data": key, "label": f"{label} ({cpulist})"})
    return {
        "governors": governors,
        "schedulers": schedulers,
        "corePresets": presets,
        "cpuCount": os.cpu_count() or 8,
    }


def reapply_perf():
    return call("reapply_perf")


def at_most(freqs, target):
    below = [freq for freq in freqs if freq <= target]
    return below[-1] if below else freqs[0] if freqs else 0


def freq_list(path):
    return sorted(int(v) for v in read_text(path).split() if v.isdigit())


def gpu_devfreq(sysfs):
    devfreq = sysfs / "class" / "devfreq"
    for path in sorted(devfreq.glob("*.gpu")):
        if (path / "available_frequencies").exists():
            return path
    for path in sorted(devfreq.glob("*")):
        if "gpu" in path.name.lower() and (path / "governor").exists() and (path / "available_frequencies").exists():
            return path
    return None


def cpu_policy_freqs(policy):
    freqs = freq_list(policy / "scaling_available_frequencies")
    if freqs:
        return freqs
    low = read_text(policy / "cpuinfo_min_freq")
    high = read_text(policy / "cpuinfo_max_freq")
    if low.isdigit() and high.isdigit():
        return [int(low), int(high)]
    return []


def cpu_list_text(cpus):
    if cpus == list(range(cpus[0], cpus[-1] + 1)):
        return str(cpus[0]) if len(cpus) == 1 else f"{cpus[0]}-{cpus[-1]}"
    return ",".join(str(cpu) for cpu in cpus)


def cpu_policy_cpus(policy, policy_id):
    for name in ("related_cpus", "affected_cpus"):
        cpus = sorted(int(v) for v in read_text(policy / name).split() if v.isdigit())
        if cpus:
            return cpu_list_text(cpus)
    return str(policy_id)


def cpu_policies(sysfs):
    policies = []
    for policy in (sysfs / "devices" / "system" / "cpu" / "cpufreq").glob("policy*"):
        suffix = policy.name.removeprefix("policy")
        if not suffix.isdigit():
            continue
        khz = sorted(cpu_policy_freqs(policy))
        if khz:
            policy_id = int(suffix)
            policies.append({
                "id": policy_id,
                "cpus": cpu_policy_cpus(policy, policy_id),
                "khz": khz,
                "mhz": [k // 1000 for k in khz],
            })
    return sorted(policies, key=lambda policy: policy["id"])


def freq_limits(env=None, sysfs=Path("/sys")):
    env = device_env() if env is None else env
    gpu = gpu_devfreq(sysfs)
    gpu_hz = freq_list(gpu / "available_frequencies") if gpu else []
    stock = str(env.get("ARMADA_GPU_STOCK_MAX_MHZ", "")).strip()
    stock_hz = 0
    if gpu_hz:
        stock_hz = gpu_hz[-1]
        if stock.isdigit() and int(stock) > 0:
            stock_hz = at_most(gpu_hz, int(stock) * 1_000_000 + 999_999)
    return {
        "gpuMhz": list(dict.fromkeys(hz // 1_000_000 for hz in gpu_hz)),
        "gpuStockMaxMhz": stock_hz // 1_000_000,
        "gpuStockHz": stock_hz,
        "gpuHz": gpu_hz,
        "cpuPolicies": cpu_policies(sysfs),
        "cpuTopology": {
            "big": str(env.get("ARMADA_BIG_CORES", "")).strip(),
            "prime": str(env.get("ARMADA_PRIME_CORES", "")).strip(),
            "little": str(env.get("ARMADA_LITTLE_CORES", "")).strip(),
        },
    }


def restart_game_mode():
    return bool(call("restart_game_mode").get("ok"))
