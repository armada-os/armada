import colorsys
import glob
import json
import math
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

CONFIG_PATH = Path = "/etc/armada/rgb.json"
FALLBACK_CONFIG = "/var/home/armada/homebrew/settings/rgb.json"
LEDS_BASE_DIR = "/sys/class/leds"

EXCLUDE_KEYWORDS = ["power", "batt", "charge", "charging", "disk", "mmc", "caps", "num", "scroll", "backlight", "input", "default"]
GAMMA = 2.2


def apply_gamma(val_0_to_255: int, factor: float = 1.0) -> int:
    """Applies gamma correction (2.2) so PWM output matches human eye perception."""
    scaled = (max(0, min(255, val_0_to_255)) / 255.0) * factor
    if scaled <= 0.0:
        return 0
    gamma_val = math.pow(scaled, GAMMA)
    return max(0, min(255, int(round(gamma_val * 255))))


class LEDZone:
    def __init__(self, name: str, zone_type: str, data: Dict[str, Any]):
        self.name = name
        self.zone_type = zone_type  # "multicolor" or "discrete"
        self.data = data            # {"path": ...} or {"r": [...], "g": [...], "b": [...]}

    def write(self, rgb: Tuple[int, int, int], brightness_0_to_255: int, quadrant_offsets: Optional[List[Tuple[int, int, int]]] = None):
        if self.zone_type == "multicolor":
            base_path = self.data["path"]
            try:
                # Calculate gamma-corrected RGB intensities
                factor = brightness_0_to_255 / 255.0
                r = apply_gamma(rgb[0], factor)
                g = apply_gamma(rgb[1], factor)
                b = apply_gamma(rgb[2], factor)
                with open(os.path.join(base_path, "multi_intensity"), "w") as f:
                    f.write(f"{r} {g} {b}")
                with open(os.path.join(base_path, "brightness"), "w") as f:
                    f.write("255" if (r > 0 or g > 0 or b > 0) else "0")
            except Exception:
                pass

        elif self.zone_type == "discrete":
            factor = brightness_0_to_255 / 255.0
            r_paths = self.data.get("r", [])
            g_paths = self.data.get("g", [])
            b_paths = self.data.get("b", [])

            for i in range(max(len(r_paths), len(g_paths), len(b_paths))):
                if quadrant_offsets and i < len(quadrant_offsets):
                    col = quadrant_offsets[i]
                else:
                    col = rgb

                r_val = str(apply_gamma(col[0], factor))
                g_val = str(apply_gamma(col[1], factor))
                b_val = str(apply_gamma(col[2], factor))

                if i < len(r_paths):
                    try:
                        with open(os.path.join(r_paths[i], "brightness"), "w") as f:
                            f.write(r_val)
                    except Exception:
                        pass
                if i < len(g_paths):
                    try:
                        with open(os.path.join(g_paths[i], "brightness"), "w") as f:
                            f.write(g_val)
                    except Exception:
                        pass
                if i < len(b_paths):
                    try:
                        with open(os.path.join(b_paths[i], "brightness"), "w") as f:
                            f.write(b_val)
                    except Exception:
                        pass


class RGBEngine:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = True
        self.zones: Dict[str, LEDZone] = {}
        self.discover_all_zones()
        self.state: Dict[str, Any] = {
            "enabled": True,
            "brightness": 255,
            "effect": "static",
            "speed": 5,
            "color": [0, 255, 255],        # Default Cyan
            "sync_zones": True,
            "sticks_color": [0, 255, 255],
            "sides_color": [255, 0, 255],   # Default Magenta for split mode
            "sleep_off": True,
        }
        self.load_config()
        self.anim_thread = threading.Thread(target=self._animation_loop, daemon=True)
        self.anim_thread.start()

    def is_supported(self) -> bool:
        return len(self.zones) > 0

    def discover_all_zones(self):
        self.zones = {}
        if not os.path.exists(LEDS_BASE_DIR):
            return

        entries = sorted(os.listdir(LEDS_BASE_DIR))

        # 1. Check for Unified Multicolor nodes (Odin 2, Odin 2 Mini, Odin 2 Portal, etc.)
        for entry in entries:
            led_path = os.path.join(LEDS_BASE_DIR, entry)
            if not os.path.exists(os.path.join(led_path, "multi_intensity")):
                continue
            lower = entry.lower()
            if any(k in lower for k in EXCLUDE_KEYWORDS):
                continue
            self.zones[entry] = LEDZone(entry, "multicolor", {"path": led_path})

        # 2. Check for Discrete Single-Channel Emitters (Odin 3, Thor, Retroid Pocket 6, HTR3212)
        left_channels: Dict[str, List[str]] = {"r": [], "g": [], "b": []}
        right_channels: Dict[str, List[str]] = {"r": [], "g": [], "b": []}

        for entry in entries:
            led_path = os.path.join(LEDS_BASE_DIR, entry)
            if os.path.exists(os.path.join(led_path, "multi_intensity")):
                continue

            lower = entry.lower()
            if any(k in lower for k in EXCLUDE_KEYWORDS):
                continue

            side = None
            if lower.startswith("l:") or lower.startswith("l_") or "left" in lower:
                side = "left"
            elif lower.startswith("r:") or lower.startswith("r_") or "right" in lower:
                side = "right"

            if not side:
                continue

            target = left_channels if side == "left" else right_channels
            if ":r" in lower or "_r" in lower or "red" in lower:
                target["r"].append(led_path)
            elif ":g" in lower or "_g" in lower or "green" in lower:
                target["g"].append(led_path)
            elif ":b" in lower or "_b" in lower or "blue" in lower:
                target["b"].append(led_path)

        # Sort discrete channel paths so 1..4 are in index order
        for d in (left_channels, right_channels):
            for ch in ("r", "g", "b"):
                d[ch].sort()

        if left_channels["r"] or left_channels["g"] or left_channels["b"]:
            if "left-joystick" not in self.zones:
                self.zones["left-joystick"] = LEDZone("left-joystick", "discrete", left_channels)

        if right_channels["r"] or right_channels["g"] or right_channels["b"]:
            if "right-joystick" not in self.zones:
                self.zones["right-joystick"] = LEDZone("right-joystick", "discrete", right_channels)

    def load_config(self):
        for target in (CONFIG_PATH, FALLBACK_CONFIG):
            if os.path.exists(target):
                try:
                    with open(target, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            self.state.update(data)
                            return
                except Exception:
                    pass

    def save_config(self):
        target = CONFIG_PATH if os.path.exists(os.path.dirname(CONFIG_PATH)) else FALLBACK_CONFIG
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception:
            pass

    def apply_to_hardware(self, per_zone_colors: Optional[Dict[str, Tuple[int, int, int]]] = None, brightness_override: Optional[int] = None, per_zone_quadrants: Optional[Dict[str, List[Tuple[int, int, int]]]] = None):
        with self.lock:
            enabled = self.state["enabled"]
            brightness = self.state["brightness"] if brightness_override is None else brightness_override

            if not enabled or brightness <= 0 or not self.zones:
                for zone in self.zones.values():
                    zone.write((0, 0, 0), 0)
                return

            sync = self.state["sync_zones"]
            base_color = tuple(self.state["color"])
            sticks_color = tuple(self.state["sticks_color"])
            sides_color = tuple(self.state["sides_color"])

            for zone_name, zone_obj in self.zones.items():
                quads = per_zone_quadrants.get(zone_name) if per_zone_quadrants else None
                if per_zone_colors and zone_name in per_zone_colors:
                    col = per_zone_colors[zone_name]
                elif sync:
                    col = base_color
                else:
                    if "joystick" in zone_name or "stick" in zone_name:
                        col = sticks_color
                    else:
                        col = sides_color
                zone_obj.write(col, brightness, quadrant_offsets=quads)

    def _get_battery_level(self) -> int:
        for p in glob.glob("/sys/class/power_supply/*/capacity"):
            try:
                with open(p, "r") as f:
                    return int(f.read().strip())
            except Exception:
                pass
        return 100

    def _get_cpu_temp(self) -> float:
        for p in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
            try:
                with open(p, "r") as f:
                    v = float(f.read().strip())
                    if v > 1000:
                        v /= 1000.0
                    if 20.0 <= v <= 110.0:
                        return v
            except Exception:
                pass
        return 45.0

    def _animation_loop(self):
        step = 0.0
        while self.running:
            try:
                with self.lock:
                    enabled = self.state["enabled"]
                    effect = self.state["effect"]
                    speed = max(1, min(10, self.state.get("speed", 5)))
                    brightness = self.state["brightness"]
                    active_zones = list(self.zones.keys())

                if not enabled or brightness <= 0 or not active_zones:
                    time.sleep(0.2)
                    continue

                if effect == "static":
                    self.apply_to_hardware()
                    time.sleep(0.1)
                    continue

                elif effect == "breathing":
                    rate = 0.016 * (speed / 5.0)
                    step += rate
                    # Sinusoidal curve between 0.05 and 1.0
                    factor = 0.05 + 0.95 * ((math.cos(step) + 1.0) / 2.0)
                    current_bright = int(brightness * factor)
                    self.apply_to_hardware(brightness_override=current_bright)
                    time.sleep(0.016)  # 60 Hz smooth breathing

                elif effect == "rainbow":
                    rate = 0.004 * (speed / 5.0)
                    step = (step + rate) % 1.0
                    
                    per_zone = {}
                    per_quad = {}
                    for i, zone in enumerate(active_zones):
                        zone_hue = (step + (i * 0.15)) % 1.0
                        r, g, b = colorsys.hsv_to_rgb(zone_hue, 1.0, 1.0)
                        per_zone[zone] = (int(r * 255), int(g * 255), int(b * 255))

                        # For discrete 4-quadrant rings (Odin 3), calculate rotating rainbow quadrants
                        quad_list = []
                        for q in range(4):
                            q_hue = (step + (q * 0.25)) % 1.0
                            qr, qg, qb = colorsys.hsv_to_rgb(q_hue, 1.0, 1.0)
                            quad_list.append((int(qr * 255), int(qg * 255), int(qb * 255)))
                        per_quad[zone] = quad_list
                    
                    self.apply_to_hardware(per_zone_colors=per_zone, per_zone_quadrants=per_quad)
                    time.sleep(0.02)

                elif effect == "battery":
                    cap = self._get_battery_level()
                    if cap >= 60:
                        col = (0, 255, 60)
                    elif cap >= 25:
                        col = (255, 180, 0)
                    else:
                        step += 0.08
                        pulse = 0.3 + 0.7 * ((math.sin(step * 4) + 1.0) / 2.0)
                        col = (int(255 * pulse), 0, 0)
                    
                    per_zone = {z: col for z in active_zones}
                    self.apply_to_hardware(per_zone_colors=per_zone)
                    time.sleep(0.1)

                elif effect == "temp":
                    temp = self._get_cpu_temp()
                    if temp < 45.0:
                        col = (0, 200, 255)
                    elif temp < 65.0:
                        ratio = (temp - 45.0) / 20.0
                        r = int(0 + ratio * 255)
                        g = int(200 - ratio * 40)
                        b = int(255 - ratio * 255)
                        col = (r, g, b)
                    else:
                        col = (255, 30, 0)
                    
                    per_zone = {z: col for z in active_zones}
                    self.apply_to_hardware(per_zone_colors=per_zone)
                    time.sleep(0.2)

                else:
                    self.apply_to_hardware()
                    time.sleep(0.1)

            except Exception:
                time.sleep(0.2)


_engine = RGBEngine()


def get_rgb_state() -> Dict[str, Any]:
    with _engine.lock:
        state_copy = dict(_engine.state)
        state_copy["zones"] = list(_engine.zones.keys())
        state_copy["supported"] = _engine.is_supported()
        return state_copy


def save_rgb_config(data: Dict[str, Any]):
    if not isinstance(data, dict):
        raise ValueError("invalid rgb config")
    with _engine.lock:
        for k in ("enabled", "brightness", "effect", "speed", "color", "sync_zones", "sticks_color", "sides_color", "sleep_off"):
            if k in data:
                _engine.state[k] = data[k]
        _engine.save_config()
    _engine.apply_to_hardware()
    return get_rgb_state()
