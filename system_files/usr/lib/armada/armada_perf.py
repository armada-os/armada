"""Shared performance helpers and armada-control/armada-powerd state contract."""
import json
import os
import pathlib
import shlex
import subprocess
import tempfile

STATE_FILE = pathlib.Path("/run/armada/perf-state.json")
SESSION_SOCKET = "/run/armada/session.sock"
DEVICE_ENV_HELPER = "/usr/libexec/armada/device-env"

CORE_PRESETS = ("all", "big", "prime", "little")
SCHEDULERS = ("eevdf", "cosmos", "lavd")
GAMESCOPE_COMMS = ("gamescope", "gamescope-wl")
RR_PRIORITY = 40
NICE_MIN, NICE_MAX = -20, 19
GAMESCOPE_NICE_MIN, GAMESCOPE_NICE_MAX = -20, 19

def parse_cpulist(text):
    # Order preserved: feeds WINE_CPU_TOPOLOGY (reported CPU i = host list[i]).
    cpus = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            low, high = part.split("-", 1)
            if not (low.strip().isdigit() and high.strip().isdigit()):
                raise ValueError(f"invalid cpulist range: {part}")
            low, high = int(low), int(high)
            if high < low:
                raise ValueError(f"invalid cpulist range: {part}")
            cpus.extend(range(low, high + 1))
        elif part.isdigit():
            cpus.append(int(part))
        else:
            raise ValueError(f"invalid cpulist entry: {part}")
    if len(set(cpus)) != len(cpus):
        raise ValueError("duplicate cpus in cpulist")
    return cpus


def format_cpulist(cpus):
    # Inverse of parse_cpulist, compact form: [3,4,5,7] -> "3-5,7".
    parts, start, prev = [], None, None
    for cpu in sorted(cpus):
        if start is None:
            start = prev = cpu
            continue
        if cpu == prev + 1:
            prev = cpu
            continue
        parts.append(f"{start}-{prev}" if prev > start else f"{start}")
        start = prev = cpu
    if start is not None:
        parts.append(f"{start}-{prev}" if prev > start else f"{start}")
    return ",".join(parts)


def online_cpus():
    return sorted(os.sched_getaffinity(0) | {c for c in range(os.cpu_count() or 1)})


def device_env():
    env = {}
    try:
        out = subprocess.check_output([DEVICE_ENV_HELPER], text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return env
    for line in out.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            env[key] = shlex.split(value)[0] if value else ""
        except ValueError:
            env[key] = value
    return env


def resolve_cores(value, env=None):
    # None/"" = unset (inherit). "all" and empty presets return the explicit
    # full set: a per-game "all" must clear a restrictive global.
    if value in (None, ""):
        return None
    available = online_cpus()
    if value == "all":
        return list(available)
    if value in CORE_PRESETS:
        env = env if env is not None else device_env()
        cpulist = env.get(f"ARMADA_{value.upper()}_CORES", "")
        if not cpulist:
            return list(available)
        cpus = parse_cpulist(cpulist)
    else:
        cpus = parse_cpulist(value)
    unknown = [c for c in cpus if c not in available]
    if unknown:
        raise ValueError(f"unknown cpus: {unknown}")
    return cpus


def clamp(value, low, high):
    return max(low, min(high, int(value)))


def sanitize_perf(settings, env=None):
    # Validated subset of the perf keys, bad values dropped key-by-key.
    clean = {}
    if "cores" in settings:
        try:
            cores = resolve_cores(settings.get("cores"), env)
            if cores is not None:
                clean["cores"] = cores
        except ValueError:
            pass
    if isinstance(settings.get("wineTopology"), bool):
        clean["wineTopology"] = settings["wineTopology"]
    if isinstance(settings.get("nice"), int):
        clean["nice"] = clamp(settings["nice"], NICE_MIN, NICE_MAX)
    if isinstance(settings.get("gamescopeNice"), int):
        clean["gamescopeNice"] = clamp(
            settings["gamescopeNice"], GAMESCOPE_NICE_MIN, GAMESCOPE_NICE_MAX)
    if isinstance(settings.get("gamescopeRr"), bool):
        clean["gamescopeRr"] = settings["gamescopeRr"]
    if "gamescopeCores" in settings:
        try:
            gs_cores = resolve_cores(settings.get("gamescopeCores"), env)
            if gs_cores is not None:
                clean["gamescopeCores"] = gs_cores
        except ValueError:
            pass
    if settings.get("scheduler") in SCHEDULERS:
        clean["scheduler"] = settings["scheduler"]
    return clean


def read_state():
    try:
        with STATE_FILE.open(encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def write_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{STATE_FILE.name}.", dir=STATE_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1, sort_keys=True)
            f.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, STATE_FILE)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def effective_state(state):
    values = {
        "gamescopeNice": 0,
        "gamescopeRr": False,
        "gamescopeCores": None,
        "scheduler": "eevdf",
        "schedulerDomain": None,
    }
    for layer in (state.get("global"), state.get("override")):
        if not isinstance(layer, dict):
            continue
        for key in values:
            if key in layer and layer[key] is not None:
                values[key] = layer[key]
    return values


def gamescope_pids():
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/comm", encoding="utf-8") as f:
                comm = f.read().strip()
        except OSError:
            continue
        if comm in GAMESCOPE_COMMS:
            pids.append(int(entry))
    return pids


def process_tids(pid):
    try:
        return [int(t) for t in os.listdir(f"/proc/{pid}/task") if t.isdigit()]
    except OSError:
        return []


def child_pids(pid):
    children = []
    for tid in process_tids(pid):
        try:
            with open(f"/proc/{pid}/task/{tid}/children", encoding="utf-8") as f:
                children.extend(int(c) for c in f.read().split())
        except OSError:
            continue
    return children


def descendant_pids(pid):
    seen, stack = [], [pid]
    while stack:
        current = stack.pop()
        for child in child_pids(current):
            if child not in seen:
                seen.append(child)
                stack.append(child)
    return seen


def _policy(tid):
    try:
        return os.sched_getscheduler(tid) & ~os.SCHED_RESET_ON_FORK
    except OSError:
        return -1


def apply_gamescope(values):
    # Idempotent per-tick enforcement. RESET_ON_FORK covers RR/negative nice
    # in children but NOT affinity, hence the direct-child reset below.
    nice = clamp(values.get("gamescopeNice", 0), GAMESCOPE_NICE_MIN, GAMESCOPE_NICE_MAX)
    want_rr = bool(values.get("gamescopeRr"))
    cores = values.get("gamescopeCores") or None
    all_cpus = set(online_cpus())
    mask = set(cores) & all_cpus if cores else all_cpus
    if not mask:
        mask = all_cpus
    for pid in gamescope_pids():
        for tid in process_tids(pid):
            policy = _policy(tid)
            try:
                # nice block must see the post-promotion policy, or RR +
                # negative nice would promote then demote every tick
                if want_rr and policy == os.SCHED_OTHER:
                    os.sched_setscheduler(
                        tid, os.SCHED_RR | os.SCHED_RESET_ON_FORK,
                        os.sched_param(RR_PRIORITY))
                    policy = os.SCHED_RR
                elif not want_rr and policy == os.SCHED_RR:
                    os.sched_setscheduler(
                        tid, os.SCHED_OTHER | os.SCHED_RESET_ON_FORK,
                        os.sched_param(0))
                    policy = os.SCHED_OTHER
                if policy in (os.SCHED_OTHER, os.SCHED_BATCH):
                    if nice < 0 and policy == os.SCHED_OTHER:
                        os.sched_setscheduler(
                            tid, os.SCHED_OTHER | os.SCHED_RESET_ON_FORK,
                            os.sched_param(0))
                    os.setpriority(os.PRIO_PROCESS, tid, nice)
                os.sched_setaffinity(tid, mask)
            except (OSError, PermissionError):
                continue
        if mask != all_cpus:
            for child in child_pids(pid):
                try:
                    with open(f"/proc/{child}/comm", encoding="utf-8") as f:
                        if f.read().strip() in GAMESCOPE_COMMS:
                            continue
                except OSError:
                    continue
                for tid in process_tids(child):
                    try:
                        os.sched_setaffinity(tid, all_cpus)
                    except OSError:
                        continue
