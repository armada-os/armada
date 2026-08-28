from pathlib import Path

# Read-only, best-effort thermal-zone discovery (same as armada-powerd's discover_temps()).
THERMAL_ZONE_DIR = Path("/sys/class/thermal")
THERMAL_ZONE_KINDS = ("cpu", "gpu", "gpuss", "video", "mem")


def _discover_temp_paths():
    try:
        zones = sorted(THERMAL_ZONE_DIR.glob("thermal_zone*"))
    except OSError:
        return []
    paths = []
    for zone in zones:
        try:
            kind = (zone / "type").read_text(encoding="utf-8").strip().lower()
        except OSError:
            continue
        temp_path = zone / "temp"
        if kind.startswith(THERMAL_ZONE_KINDS) and temp_path.exists():
            paths.append(temp_path)
    return paths


def get_current_temp():
    values = []
    for path in _discover_temp_paths():
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if raw.lstrip("-").isdigit():
            values.append(int(raw) // 1000)
    if not values:
        return None
    # Average of the hottest 3 zones, matching armada-powerd's own fan-tick reading.
    hottest = sorted(values, reverse=True)[:3]
    return sum(hottest) // len(hottest)
