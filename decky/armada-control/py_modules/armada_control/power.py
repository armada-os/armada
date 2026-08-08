import configparser
import shutil
import tempfile
import time
from pathlib import Path

from .privileged import call

POWER_CONFIG = Path("/etc/armada/power-profiles.conf")
FACTORY_POWER_CONFIG = Path("/usr/share/armada/power-profiles.conf")
# Fallback list only; the real profile set is discovered from [profile.*] at parse time.
PROFILES = ("eco", "balanced", "performance")


def default_label(name):
    return name.replace("_", " ").title()


def profile_order(parser):
    names = [s.removeprefix("profile.") for s in parser.sections() if s.startswith("profile.")]
    order = parser.get("general", "profile_order", fallback="").strip()
    if order:
        wanted = [p.strip() for p in order.split(",") if p.strip()]
        if sorted(wanted) == sorted(names):
            return wanted
    return names


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


def parsed_power(parser):
    for section in ("general", "fan"):
        if not parser.has_section(section):
            raise ValueError(f"missing config section [{section}]")
    names = profile_order(parser)
    if not names:
        raise ValueError("no [profile.*] sections")
    data = {
        "general": {"default_profile": parser.get("general", "default_profile")},
        "order": names,
        "profiles": {},
        "fan_curves": {},
        "fan": {},
        "underclocks": {},
    }
    for name in names:
        section = f"profile.{name}"
        data["profiles"][name] = {
            "label": parser.get(section, "label", fallback="") or default_label(name),
            "cpu_governor": parser.get(section, "cpu_governor", fallback="schedutil"),
            "cpu_max": parser.get(section, "cpu_max", fallback="1.00"),
            "cpu_underclock": parser.get(section, "cpu_underclock", fallback="none"),
            "cpu_max_policy0": parser.get(section, "cpu_max_policy0", fallback=""),
            "cpu_max_policy6": parser.get(section, "cpu_max_policy6", fallback=""),
            "gpu_max": parser.get(section, "gpu_max", fallback="1.00"),
            "gpu_min": parser.get(section, "gpu_min", fallback="0.00"),
            "fan_curve": parser.get(section, "fan_curve", fallback=""),
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
        if len(parts) == 3:
            _, device_class, level = parts
            data["underclocks"].setdefault(device_class, {})[level] = dict(parser.items(section))
    data["fan"] = dict(parser.items("fan"))
    return data


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ""


def available_hardware():
    # Real frequency lists for the UI (CPU per-cluster kHz, GPU OPPs in MHz, governors).
    cpu = {}
    base = Path("/sys/devices/system/cpu/cpufreq")
    for policy in sorted(base.glob("policy*")):
        try:
            pid = int(policy.name.removeprefix("policy"))
        except ValueError:
            continue
        freqs = sorted({int(x) for x in _read(policy / "scaling_available_frequencies").split() if x.isdigit()})
        if freqs:
            cpu[str(pid)] = freqs
    governors = _read(base / "policy0" / "scaling_available_governors").split()
    gpu = []
    for dev in sorted(Path("/sys/class/devfreq").glob("*")):
        if "gpu" in dev.name.lower() and (dev / "available_frequencies").exists():
            gpu = sorted({int(x) // 1000000 for x in _read(dev / "available_frequencies").split() if x.isdigit()})
            break
    return {"cpu": cpu, "gpu": gpu, "governors": governors}


# Editable fields written to /etc. cpu_governor is user-selectable; explicit per-policy
# MHz (POLICY_KEYS) override the underclock level in the daemon when present.
EDITABLE_KEYS = ("cpu_governor", "cpu_max", "cpu_underclock", "gpu_max", "gpu_min", "fan_curve")
NUMERIC_KEYS = ("cpu_max", "gpu_max", "gpu_min")
POLICY_KEYS = ("cpu_max_policy0", "cpu_max_policy6")


GPU_RATIO_KEYS = ("gpu_max", "gpu_min")


def profile_overrides(profile):
    out = {}
    for key in EDITABLE_KEYS:
        value = profile.get(key, "")
        if key in GPU_RATIO_KEYS:
            # 4 decimals so a UI-picked GPU MHz survives the daemon's int()+snap round-trip.
            try:
                out[key] = f"{float(value):.4f}"
            except (TypeError, ValueError):
                out[key] = "0.0000"
        elif key in NUMERIC_KEYS:
            try:
                out[key] = f"{float(value):.2f}"
            except (TypeError, ValueError):
                out[key] = "0.00"
        else:
            out[key] = str(value)
    for key in POLICY_KEYS:
        raw = str(profile.get(key, "") or "").strip()
        out[key] = str(int(raw)) if raw.isdigit() and int(raw) > 0 else ""
    return out


def _pwm_at(pts, temp):
    if temp <= pts[0][0]:
        return pts[0][1]
    if temp >= pts[-1][0]:
        return pts[-1][1]
    for i in range(1, len(pts)):
        if temp <= pts[i][0]:
            (t0, p0), (t1, p1) = pts[i - 1], pts[i]
            return p0 + (p1 - p0) * (temp - t0) / (t1 - t0)
    return pts[-1][1]


def _validate_curve(name, raw):
    # Structural + thermal-wall gate. Raised errors travel the SAVE path only, so a bad
    # curve is rejected before write; it never reaches the parse/read path that factory-restores.
    pts = []
    for seg in (raw or "").split(","):
        seg = seg.strip()
        if not seg:
            continue
        try:
            ts, ps = seg.split(":")
            point = (int(ts), int(ps))
        except ValueError:
            raise ValueError(f"fan_curve {name}: bad point '{seg}'")
        pts.append(point)
    if len(pts) < 2:
        raise ValueError(f"fan_curve {name}: need at least 2 points")
    for i, (t, p) in enumerate(pts):
        if not 0 <= t <= 100:
            raise ValueError(f"fan_curve {name}: temp {t} out of range")
        if not 0 <= p <= 255:
            raise ValueError(f"fan_curve {name}: pwm {p} out of range")
        if i and t <= pts[i - 1][0]:
            raise ValueError(f"fan_curve {name}: temps not ascending at {t}")
        if i and p < pts[i - 1][1]:
            raise ValueError(f"fan_curve {name}: pwm decreases at {t}")
    if _pwm_at(pts, 92) < 255:
        raise ValueError(f"fan_curve {name}: must reach 100% (255) by 92C")
    return ",".join(f"{t}:{p}" for t, p in pts)


def render_power(data, factory=None):
    # Self-contained render: our /etc fully specifies every profile (not minimal diffs vs
    # factory), so we always write each profile's editable state and preserve everything else
    # ([fan], fan_curve.*, underclock.*, labels, profile_order).
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(POWER_CONFIG)

    if not parser.has_section("general"):
        parser.add_section("general")
    parser.set("general", "default_profile", str(data["general"]["default_profile"]))
    if data.get("order"):
        parser.set("general", "profile_order", ", ".join(str(n) for n in data["order"]))

    for name, profile in data["profiles"].items():
        section = f"profile.{name}"
        if not parser.has_section(section):
            parser.add_section(section)
        label = str(profile.get("label", "")).strip()
        if label:
            parser.set(section, "label", label)
        overrides = profile_overrides(profile)
        for key in EDITABLE_KEYS:
            parser.set(section, key, overrides[key])
        for key in POLICY_KEYS:
            if overrides[key]:
                parser.set(section, key, overrides[key])
            elif parser.has_option(section, key):
                parser.remove_option(section, key)

    # Fan curves: emit only profile-referenced curves (skips loose factory presets), and
    # validate only the ones that actually changed vs on-disk so an untouched curve can never
    # block an unrelated save. Never write a curve-less section (would factory-nuke on next read).
    used = {str(p.get("fan_curve", "")) for p in data.get("profiles", {}).values()}
    used.discard("")
    for name in used:
        fc = (data.get("fan_curves") or {}).get(name)
        if not fc:
            continue
        section = f"fan_curve.{name}"
        old_raw = parser.get(section, "curve", fallback="") if parser.has_section(section) else ""
        new_raw = str(fc.get("curve", ""))
        if new_raw.replace(" ", "") != old_raw.replace(" ", ""):
            curve = _validate_curve(name, new_raw)
        elif old_raw:
            curve = old_raw
        else:
            raise ValueError(f"fan_curve {name}: empty curve")
        if not parser.has_section(section):
            parser.add_section(section)
        label = str(fc.get("label", "")).strip()
        if label:
            parser.set(section, "label", label)
        parser.set(section, "curve", curve)

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
    if data["general"]["default_profile"] not in (data.get("profiles") or {}):
        raise ValueError("invalid power config")
    try:
        rendered = render_power(data, factory_power_defaults())
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"malformed power config: {exc}")
    call("write_config", name="power", text=rendered)
