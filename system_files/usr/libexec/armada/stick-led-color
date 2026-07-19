#!/usr/bin/env python3
"""Get/set/apply the Retroid Pocket Mini V2 stick RGB (HTR3212, 4 zones per
stick). Mirrors controller-type's get/set/apply + /etc/armada/*.conf pattern.

Modes:
  static            - always the saved color.
  breathing         - saved color, pulsing.
  battery           - color interpolated from current battery capacity (red
                       -> yellow -> green), full green while charging.
  battery-breathing - battery color, pulsing.
  rainbow           - saved color ignored; hue cycles continuously.
  chase             - saved color, a lit zone (with a fading tail) travels
                       around the 4 zones of each stick.
  alternating       - saved color, breathing but the left and right sticks
                       are 180 degrees out of phase (ping-pong).
  reactive          - saved color ignored; each stick's deflection drives its
                       own brightness (centered/idle=off, full throw=bright)
                       and angle drives hue, independently per side. Each
                       button press triggers a brief flash on both sticks,
                       in that button's own configurable color (set-flash-
                       color <button> <RRGGBB>, default white).
  multidot          - three fixed-hue dots (red/green/blue) chase each other
                       around the 4 zones of each stick.
  ambilight         - saved color ignored; each stick tracks the average
                       color of a strip near its own side of the screen
                       (sampled off the DRM framebuffer via ffmpeg's
                       kmsgrab), fading smoothly between samples rather
                       than snapping.

Per-mode tunables (set-param <param> <mode> <value>), persisted per mode
(battery-breathing shares breathing's):
  speed     - animation rate multiplier (0.25-3.0). breathing, chase,
              rainbow, alternating, multidot, ambilight (how fast the color
              chases each new screen sample; the sample rate itself is fixed).
  intensity - how dim the "low point" gets (0.0-0.5): the breathing/
              alternating trough, and the base brightness of chase/multidot's
              unlit zones and reactive's brightness right past its deadzone.
              Higher = less contrast between lit and unlit.
  size      - how many trailing zones stay lit (1-3). chase, multidot.

`daemon` runs forever (see armada-stick-led.service): idles at IDLE_INTERVAL
for the static/battery modes (just enough to track battery level), and
animates at BREATH_INTERVAL for the rest.

screen_link (set-screen-link on|off) scales the final brightness by the
panel backlight's current/max ratio, independent of mode, so the sticks dim
and brighten along with the screen.
"""
import colorsys
import fcntl
import math
import os
import re
import select
import struct
import subprocess
import sys
import time
from pathlib import Path

CONFIG = Path("/etc/armada/stick-led.conf")
# Same flag fake-suspend.sh touches for STATE_FLAG - checked here instead of
# having fake-suspend poke the daemon directly, since it's the daemon (not a
# one-shot "off" command) that would otherwise keep re-lighting the sticks
# every tick regardless of suspend state.
SUSPEND_FLAG = Path("/run/armada/fake-suspend.active")
SUSPEND_POLL_INTERVAL = 0.5
DEFAULT_COLOR = "0050FF"
DEFAULT_MODE = "static"
DEFAULT_SCREEN_LINK = False
MODES = ("static", "breathing", "battery", "battery-breathing", "rainbow", "chase", "alternating", "reactive", "multidot", "ambilight")
ANIMATED_MODES = ("breathing", "battery-breathing", "rainbow", "chase", "alternating", "reactive", "multidot", "ambilight")
LED_BASE = Path("/sys/class/leds")
POWER_SUPPLY_BASE = Path("/sys/class/power_supply")
BACKLIGHT_BASE = Path("/sys/class/backlight")
SIDES = ("l", "r")
ZONES = (1, 2, 3, 4)
IDLE_INTERVAL = 5.0
BREATH_INTERVAL = 0.05
BREATH_PERIOD_S = 3.5
BASE_BREATH_STEP = (2 * math.pi) / (BREATH_PERIOD_S / BREATH_INTERVAL)  # at speed=1.0
CHASE_ZONES_PER_SEC = 1.5  # at speed=1.0
MULTIDOT_ZONES_PER_SEC = 1.2  # at speed=1.0
MULTIDOT_COLORS = ((255, 0, 0), (0, 255, 0), (0, 100, 255))

PARAM_SPECS = {
    "speed": {"min": 0.25, "max": 3.0, "default": 1.0, "modes": ("breathing", "chase", "rainbow", "alternating", "multidot", "ambilight")},
    "intensity": {"min": 0.0, "max": 0.5, "default": 0.15, "modes": ("breathing", "alternating", "chase", "multidot", "reactive")},
    "size": {"min": 1, "max": 3, "default": 2, "modes": ("chase", "multidot")},
}


def alias_mode(mode):
    return "breathing" if mode == "battery-breathing" else mode


def param_key(param, mode):
    spec = PARAM_SPECS[param]
    m = alias_mode(mode)
    return m if m in spec["modes"] else None


def get_param(settings, param, mode):
    spec = PARAM_SPECS[param]
    key = param_key(param, mode)
    return settings.get(f"{param}_{key}", spec["default"]) if key else spec["default"]


def clamp_param(param, value):
    spec = PARAM_SPECS[param]
    return max(spec["min"], min(spec["max"], value))


# --- reactive mode: raw gamepad evdev reader -------------------------------
# Raw gamepad MCU device name, checked against /sys/class/input/event*/device/name.
# Devices sharing the HTR3212 stick RGB hardware use different gamepad
# drivers/MCUs depending on family: Retroid Pocket Mini V2/5/Flip2 use the
# "retroid-gamepad" driver (reports "Retroid Pocket Gamepad"); Retroid Pocket
# 6 shares its InputPlumber composite device config with the AYN family and
# uses the "rsinput" driver instead, reporting "AYN Odin2 Gamepad" even on
# Retroid-branded hardware (confirmed on real Retroid Pocket 6 hardware) -
# unverified whether AYN Odin 2/Mini/Portal/Thor report this same exact
# string or their own variant.
GAMEPAD_NAMES = ("Retroid Pocket Gamepad", "AYN Odin2 Gamepad")
EV_KEY = 0x01
EV_ABS = 0x03
ABS_X, ABS_Y, ABS_RX, ABS_RY = 0x00, 0x01, 0x03, 0x04
INPUT_EVENT_FMT = "llHHi"  # 64-bit timeval (aarch64) + type + code + value
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FMT)
FLASH_DECAY = 0.72
FLASH_DEFAULT_COLOR = "FFFFFF"
# Raw BTN_* codes (linux/input-event-codes.h) mapped to the same logical
# button names InputPlumber's retroid_mcu.yaml capability map translates
# them to (including its North/West swap - BTN_NORTH really is wired to the
# "West" gamepad button and vice versa on this MCU), so a button's flash
# color lines up with whatever Steam itself calls that button. Anything not
# listed here (e.g. BTN_MODE/Guide, or a code we don't recognize) falls into
# the shared "other" bucket.
FLASH_BUTTON_CODES = {
    0x130: "south",       # BTN_SOUTH
    0x131: "east",        # BTN_EAST
    0x132: "r4",          # BTN_C -> RightPaddle1
    0x133: "west",        # BTN_NORTH -> gamepad West (see comment above)
    0x134: "north",       # BTN_WEST -> gamepad North (see comment above)
    0x135: "l4",          # BTN_Z -> LeftPaddle1
    0x136: "l1",          # BTN_TL -> LeftBumper
    0x137: "r1",          # BTN_TR -> RightBumper
    0x13a: "select",      # BTN_SELECT
    0x13b: "start",       # BTN_START
    0x13d: "l3",          # BTN_THUMBL -> LeftStick click
    0x13e: "r3",          # BTN_THUMBR -> RightStick click
    0x220: "dpad_up",      # BTN_DPAD_UP
    0x221: "dpad_down",    # BTN_DPAD_DOWN
    0x222: "dpad_left",    # BTN_DPAD_LEFT
    0x223: "dpad_right",   # BTN_DPAD_RIGHT
}
FLASH_BUTTONS = (
    "south", "east", "north", "west",
    "l1", "r1", "l3", "r3", "l4", "r4",
    "start", "select",
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
    "other",
)


def _eviocgabs(code):
    # _IOR('E', 0x40 + code, struct input_absinfo) - 6 x __s32 = 24 bytes.
    _IOC_READ = 2
    return (_IOC_READ << 30) | (24 << 16) | (ord("E") << 8) | (0x40 + code)


def gamepad_device_path():
    try:
        entries = Path("/sys/class/input").glob("event*")
    except OSError:
        return None
    for d in entries:
        try:
            if (d / "device" / "name").read_text().strip() in GAMEPAD_NAMES:
                return Path("/dev/input") / d.name
        except OSError:
            continue
    return None


class ReactiveInput:
    """Non-exclusive raw evdev reader for the gamepad's raw MCU device -
    InputPlumber keeps reading the same node concurrently for real input
    (passthrough: true on its source device, see 01-retroid-controller.yaml),
    this is just an extra open() for LED purposes, never EVIOCGRAB'd."""

    def __init__(self):
        self.fd = None
        self.ranges = {}
        self.lx = self.ly = self.rx = self.ry = 0.0
        self.flash = 0.0
        self.flash_button = "other"

    def ensure_open(self):
        if self.fd is not None:
            return True
        path = gamepad_device_path()
        if path is None:
            return False
        try:
            fd = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            return False
        self.fd = fd
        self.ranges = {}
        for code in (ABS_X, ABS_Y, ABS_RX, ABS_RY):
            buf = bytearray(24)
            try:
                fcntl.ioctl(fd, _eviocgabs(code), buf)
                _, minimum, maximum, _, _, _ = struct.unpack("iiiiii", buf)
                if maximum > minimum:
                    self.ranges[code] = (minimum, maximum)
            except OSError:
                pass
        return True

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def _normalize(self, code, value):
        lo, hi = self.ranges.get(code, (-32768, 32767))
        span = (hi - lo) or 1
        return max(-1.0, min(1.0, (2 * (value - lo) / span) - 1))

    def poll(self):
        if not self.ensure_open():
            return
        try:
            while select.select([self.fd], [], [], 0)[0]:
                chunk = os.read(self.fd, INPUT_EVENT_SIZE)
                if len(chunk) != INPUT_EVENT_SIZE:
                    break
                _, _, ev_type, code, value = struct.unpack(INPUT_EVENT_FMT, chunk)
                if ev_type == EV_ABS:
                    if code == ABS_X:
                        self.lx = self._normalize(code, value)
                    elif code == ABS_Y:
                        self.ly = self._normalize(code, value)
                    elif code == ABS_RX:
                        self.rx = self._normalize(code, value)
                    elif code == ABS_RY:
                        self.ry = self._normalize(code, value)
                elif ev_type == EV_KEY and value == 1:
                    self.flash = 1.0
                    self.flash_button = FLASH_BUTTON_CODES.get(code, "other")
        except OSError:
            self.close()

    def tick_decay(self):
        self.flash *= FLASH_DECAY
        if self.flash < 0.02:
            self.flash = 0.0


REACTIVE_DEADZONE = 0.12  # below this magnitude, treat the stick as centered/idle (off)


def stick_reactive_rgb(x, y, floor):
    magnitude = min(1.0, math.hypot(x, y))
    if magnitude < REACTIVE_DEADZONE:
        return (0.0, 0.0, 0.0)
    hue = (math.atan2(y, x) % (2 * math.pi)) / (2 * math.pi)
    travel = (magnitude - REACTIVE_DEADZONE) / (1.0 - REACTIVE_DEADZONE)
    level = floor + (1 - floor) * travel
    return tuple(c * 255 * level for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0))


# --- ambilight mode: DRM framebuffer color sampling ------------------------
# Each stick sits below and to its own side of the panel, not behind the
# whole screen, so this samples a strip near each screen edge instead of
# averaging everything: skip a small margin in from the edge (in case of a
# letterboxed/bezel-masked black border), take a band of pixels beyond that,
# and only look at the lower part of the screen's height (top ~40% is too far
# from either stick to feel connected to it; the very bottom ~5% is often a
# HUD/taskbar strip that isn't representative of "what's on screen"). These
# are screen-position constants, not per-device ones, because only one
# device is supported so far - if a second one needs different numbers this
# should move into device-env instead of growing per-device branches here.
# This SoC's DRM card is not reliably numbered /dev/dri/card0 (confirmed on
# real hardware it's card1, with no card0 node at all), so the right node is
# found at runtime instead of hardcoded.
AMBILIGHT_HWDOWNLOAD_FORMAT = "x2rgb10le"  # this Adreno/msm driver's native scanout
# format (confirmed via `ffmpeg -loglevel verbose ... kmsgrab`) - hwdownload
# fails outright if told to target anything else (tried bgr0 and nv12
# directly; both rejected). A separate `format=bgr0` step after hwdownload
# does the actual software pixel conversion.
AMBILIGHT_CAPTURE_FPS = 2  # fixed ffmpeg output rate - see AmbilightSampler docstring
AMBILIGHT_SMOOTHING = 0.35  # fraction of the way to the new sample each time, at speed=1.0
AMBILIGHT_GRID = 4  # downscale each side's sampled strip to this many pixels per side
AMBILIGHT_EDGE_MARGIN_PX = 10  # skip this many pixels in from the left/right screen edge
AMBILIGHT_EDGE_WIDTH_PX = 100  # sample this many pixels beyond the margin
AMBILIGHT_TOP_EXCLUDE = 0.40  # fraction of screen height excluded from the top
AMBILIGHT_BOTTOM_EXCLUDE = 0.05  # fraction of screen height excluded from the bottom
AMBILIGHT_DEFAULT = (0, 80, 255)
AMBILIGHT_FRAME_SIZE = 2 * AMBILIGHT_GRID * AMBILIGHT_GRID * 4  # bgr0 bytes per output frame


def drm_card_path():
    try:
        cards = sorted(Path("/dev/dri").glob("card*"))
    except OSError:
        return None
    return str(cards[0]) if cards else None


def _ambilight_filter():
    m, w = AMBILIGHT_EDGE_MARGIN_PX, AMBILIGHT_EDGE_WIDTH_PX
    y = f"ih*{AMBILIGHT_TOP_EXCLUDE}"
    h = f"ih*{1.0 - AMBILIGHT_TOP_EXCLUDE - AMBILIGHT_BOTTOM_EXCLUDE}"
    g = AMBILIGHT_GRID
    return (
        f"hwdownload,format={AMBILIGHT_HWDOWNLOAD_FORMAT},format=bgr0,split=2[a][b];"
        f"[a]crop=w={w}:h={h}:x={m}:y={y},scale={g}:{g}[left];"
        f"[b]crop=w={w}:h={h}:x=iw-{m}-{w}:y={y},scale={g}:{g}[right];"
        f"[left][right]hstack=inputs=2[out]"
    )


def _average_region(data, width, x0, x1, y0, y1):
    tr = tg = tb = 0.0
    n = 0
    for y in range(y0, y1):
        row = y * width
        for x in range(x0, x1):
            off = (row + x) * 4
            tb += data[off]
            tg += data[off + 1]
            tr += data[off + 2]
            n += 1
    return (tr / n, tg / n, tb / n) if n else None


class AmbilightSampler:
    """Keeps a single ffmpeg kmsgrab process alive in the background rather
    than spawning a fresh one per sample - process startup (dynamic linking,
    opening the DRM card, allocating capture buffers) is the dominant cost
    here, not the capture itself, so this amortizes that cost across the
    whole time ambilight mode stays selected instead of paying it on every
    single sample. ffmpeg runs at a fixed, modest output rate regardless of
    the "speed" param; speed instead controls how aggressively the LED color
    chases each incoming sample (see sample()), which is the more
    perceptually relevant knob for a slow ambient effect like this anyway."""

    def __init__(self):
        self.color_l = AMBILIGHT_DEFAULT
        self.color_r = AMBILIGHT_DEFAULT
        self.proc = None
        self.buf = b""

    def ensure_open(self):
        if self.proc is not None and self.proc.poll() is None:
            return True
        self.close()
        card = drm_card_path()
        if card is None:
            return False
        try:
            self.proc = subprocess.Popen(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-f", "kmsgrab", "-device", card, "-i", "-",
                    "-r", str(AMBILIGHT_CAPTURE_FPS),
                    "-filter_complex", _ambilight_filter(),
                    "-map", "[out]",
                    "-f", "rawvideo", "-pix_fmt", "bgr0", "-",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
        except OSError:
            self.proc = None
            return False
        os.set_blocking(self.proc.stdout.fileno(), False)
        self.buf = b""
        return True

    def close(self):
        if self.proc is not None:
            try:
                self.proc.kill()
                self.proc.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                pass
            self.proc = None
        self.buf = b""

    def sample(self, speed):
        if not self.ensure_open():
            return self.color_l, self.color_r
        try:
            while True:
                chunk = os.read(self.proc.stdout.fileno(), 65536)
                if not chunk:
                    self.close()
                    return self.color_l, self.color_r
                self.buf += chunk
        except BlockingIOError:
            pass
        except OSError:
            self.close()
            return self.color_l, self.color_r
        n_frames = len(self.buf) // AMBILIGHT_FRAME_SIZE
        if n_frames == 0:
            return self.color_l, self.color_r
        # Only the newest complete frame matters - if the daemon fell behind,
        # older buffered frames are already stale.
        frame = self.buf[(n_frames - 1) * AMBILIGHT_FRAME_SIZE : n_frames * AMBILIGHT_FRAME_SIZE]
        self.buf = self.buf[n_frames * AMBILIGHT_FRAME_SIZE :]
        g = AMBILIGHT_GRID
        left = _average_region(frame, 2 * g, 0, g, 0, g)
        right = _average_region(frame, 2 * g, g, 2 * g, 0, g)
        if left is None or right is None:
            return self.color_l, self.color_r
        smoothing = min(0.9, AMBILIGHT_SMOOTHING * speed)
        self.color_l = tuple(c * (1 - smoothing) + t * smoothing for c, t in zip(self.color_l, left))
        self.color_r = tuple(c * (1 - smoothing) + t * smoothing for c, t in zip(self.color_r, right))
        return self.color_l, self.color_r


def load_state():
    mode, color, screen_link = DEFAULT_MODE, DEFAULT_COLOR, DEFAULT_SCREEN_LINK
    settings = {}
    flash_colors = {}
    try:
        lines = CONFIG.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return mode, color, screen_link, settings, flash_colors
    for line in lines:
        key, sep, raw = line.partition("=")
        if not sep:
            continue
        key, raw = key.strip(), raw.strip()
        if key == "mode" and raw in MODES:
            mode = raw
        elif key == "color" and re.fullmatch(r"[0-9A-Fa-f]{6}", raw or ""):
            color = raw
        elif key == "screen_link":
            screen_link = raw == "1"
        elif key.startswith("flash_") and key[len("flash_"):] in FLASH_BUTTONS:
            if re.fullmatch(r"[0-9A-Fa-f]{6}", raw or ""):
                flash_colors[key[len("flash_"):]] = raw.upper()
        elif "_" in key and key.split("_", 1)[0] in PARAM_SPECS:
            try:
                settings[key] = float(raw)
            except ValueError:
                pass
    return mode, color, screen_link, settings, flash_colors


def save_state(mode, color, screen_link, settings, flash_colors):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"mode={mode}", f"color={color}", f"screen_link={'1' if screen_link else '0'}"]
    for key in sorted(settings):
        lines.append(f"{key}={settings[key]:.3f}")
    for button in sorted(flash_colors):
        lines.append(f"flash_{button}={flash_colors[button]}")
    tmp = CONFIG.with_name(f".{CONFIG.name}.tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.chmod(0o644)
    tmp.replace(CONFIG)


def flash_color_rgb(flash_colors, button):
    hex_color = flash_colors.get(button, FLASH_DEFAULT_COLOR)
    return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)


def screen_scale():
    try:
        devices = sorted(BACKLIGHT_BASE.glob("*"))
    except OSError:
        return 1.0
    for bl in devices:
        try:
            current = int((bl / "brightness").read_text().strip())
            maximum = int((bl / "max_brightness").read_text().strip())
        except (OSError, ValueError):
            continue
        if maximum > 0:
            return max(0.0, min(1.0, current / maximum))
    return 1.0


def write_zone(side, zone, r, g, b):
    ok = False
    for chan, val in (("r", r), ("g", g), ("b", b)):
        led = LED_BASE / f"{side}:{chan}{zone}" / "brightness"
        try:
            led.write_text(str(max(0, min(255, int(round(val))))))
            ok = True
        except OSError:
            pass
    return ok


def apply_rgb(r, g, b):
    ok = False
    for side in SIDES:
        for zone in ZONES:
            if write_zone(side, zone, r, g, b):
                ok = True
    return ok


def apply_side_rgb(side, r, g, b):
    ok = False
    for zone in ZONES:
        if write_zone(side, zone, r, g, b):
            ok = True
    return ok


def apply_chase(r, g, b, pos, scale, size, floor):
    ok = False
    for side in SIDES:
        for idx, zone in enumerate(ZONES):
            dist = abs(idx - pos)
            dist = min(dist, len(ZONES) - dist)
            level = floor + (1 - floor) * max(0.0, 1.0 - dist / size)
            level *= scale
            if write_zone(side, zone, r * level, g * level, b * level):
                ok = True
    return ok


def apply_multidot(base_pos, scale, size, floor):
    ok = False
    spacing = len(ZONES) / len(MULTIDOT_COLORS)
    for side in SIDES:
        totals = [[0.0, 0.0, 0.0] for _ in ZONES]
        for i, (dr, dg, db) in enumerate(MULTIDOT_COLORS):
            dot_pos = (base_pos + i * spacing) % len(ZONES)
            for idx in range(len(ZONES)):
                dist = abs(idx - dot_pos)
                dist = min(dist, len(ZONES) - dist)
                level = floor + (1 - floor) * max(0.0, 1.0 - dist / size)
                totals[idx][0] += dr * level
                totals[idx][1] += dg * level
                totals[idx][2] += db * level
        for idx, zone in enumerate(ZONES):
            r, g, b = totals[idx]
            if write_zone(side, zone, r * scale, g * scale, b * scale):
                ok = True
    return ok


def apply_hex(hex_color, scale=1.0):
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return apply_rgb(r * scale, g * scale, b * scale)


def battery_rgb():
    best = None
    for supply in POWER_SUPPLY_BASE.glob("*"):
        try:
            if (supply / "type").read_text().strip() != "Battery":
                continue
            capacity = int((supply / "capacity").read_text().strip())
            status = (supply / "status").read_text().strip()
        except (OSError, ValueError):
            continue
        best = (capacity, status)
        break
    if best is None:
        return 0, 80, 255  # no battery info - fall back to the default blue
    capacity, status = best
    if status == "Charging" or status == "Full":
        return 0, 200, 0
    capacity = max(0, min(100, capacity))
    if capacity >= 50:
        # green (50%) -> yellow (75%)
        t = (capacity - 50) / 50
        return int(255 * (1 - t)), 200, 0
    # yellow (50%) -> red (0%)
    t = capacity / 50
    return 255, int(200 * t), 0


def base_rgb(mode, color):
    if mode in ("battery", "battery-breathing"):
        return battery_rgb()
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def rainbow_rgb(phase):
    hue = (phase % (2 * math.pi)) / (2 * math.pi)
    return tuple(c * 255 for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0))


def apply_current():
    mode, color, screen_link, _, _ = load_state()
    scale = screen_scale() if screen_link else 1.0
    r, g, b = rainbow_rgb(0.0) if mode == "rainbow" else base_rgb(mode, color)
    return apply_rgb(r * scale, g * scale, b * scale)


def run_daemon():
    phase = 0.0
    chase_pos = 0.0
    multidot_pos = 0.0
    reactive = ReactiveInput()
    ambilight = AmbilightSampler()
    while True:
        if SUSPEND_FLAG.exists():
            reactive.close()
            ambilight.close()
            apply_rgb(0, 0, 0)
            phase = chase_pos = multidot_pos = 0.0
            time.sleep(SUSPEND_POLL_INTERVAL)
            continue
        mode, color, screen_link, settings, flash_colors = load_state()
        scale = screen_scale() if screen_link else 1.0
        if mode != "reactive":
            reactive.close()
        if mode != "ambilight":
            ambilight.close()
        if mode in ANIMATED_MODES:
            if mode == "rainbow":
                r, g, b = rainbow_rgb(phase)
                apply_rgb(r * scale, g * scale, b * scale)
                phase = (phase + BASE_BREATH_STEP * get_param(settings, "speed", mode)) % (2 * math.pi)
            elif mode == "chase":
                r, g, b = base_rgb(mode, color)
                size = get_param(settings, "size", mode)
                floor = get_param(settings, "intensity", mode)
                apply_chase(r, g, b, chase_pos, scale, size, floor)
                chase_pos = (chase_pos + CHASE_ZONES_PER_SEC * get_param(settings, "speed", mode) * BREATH_INTERVAL) % len(ZONES)
            elif mode == "multidot":
                size = get_param(settings, "size", mode)
                floor = get_param(settings, "intensity", mode)
                apply_multidot(multidot_pos, scale, size, floor)
                multidot_pos = (multidot_pos + MULTIDOT_ZONES_PER_SEC * get_param(settings, "speed", mode) * BREATH_INTERVAL) % len(ZONES)
            elif mode == "alternating":
                r, g, b = base_rgb(mode, color)
                floor = get_param(settings, "intensity", mode)
                level_l = floor + (1 - floor) * (0.5 + 0.5 * math.sin(phase))
                level_r = floor + (1 - floor) * (0.5 + 0.5 * math.sin(phase + math.pi))
                apply_side_rgb("l", r * level_l * scale, g * level_l * scale, b * level_l * scale)
                apply_side_rgb("r", r * level_r * scale, g * level_r * scale, b * level_r * scale)
                phase = (phase + BASE_BREATH_STEP * get_param(settings, "speed", mode)) % (2 * math.pi)
            elif mode == "reactive":
                reactive.poll()
                floor = get_param(settings, "intensity", mode)
                lr, lg, lb = stick_reactive_rgb(reactive.lx, -reactive.ly, floor)
                rr, rg, rb = stick_reactive_rgb(reactive.rx, -reactive.ry, floor)
                flash = reactive.flash
                fr, fg, fb = flash_color_rgb(flash_colors, reactive.flash_button)
                blend = lambda c, f: c * (1 - flash) + f * flash  # noqa: E731
                apply_side_rgb("l", blend(lr, fr) * scale, blend(lg, fg) * scale, blend(lb, fb) * scale)
                apply_side_rgb("r", blend(rr, fr) * scale, blend(rg, fg) * scale, blend(rb, fb) * scale)
                reactive.tick_decay()
            elif mode == "ambilight":
                (lr, lg, lb), (rr, rg, rb) = ambilight.sample(get_param(settings, "speed", mode))
                apply_side_rgb("l", lr * scale, lg * scale, lb * scale)
                apply_side_rgb("r", rr * scale, rg * scale, rb * scale)
            else:
                r, g, b = base_rgb(mode, color)
                floor = get_param(settings, "intensity", mode)
                level = scale * (floor + (1 - floor) * (0.5 + 0.5 * math.sin(phase)))
                apply_rgb(r * level, g * level, b * level)
                phase = (phase + BASE_BREATH_STEP * get_param(settings, "speed", mode)) % (2 * math.pi)
            time.sleep(BREATH_INTERVAL)
        else:
            r, g, b = base_rgb(mode, color)
            apply_rgb(r * scale, g * scale, b * scale)
            phase = chase_pos = multidot_pos = 0.0
            time.sleep(IDLE_INTERVAL if not screen_link else BREATH_INTERVAL * 4)


def print_state():
    mode, color, screen_link, settings, flash_colors = load_state()
    print(f"mode={mode}")
    print(f"color={color}")
    print(f"screen_link={'1' if screen_link else '0'}")
    for param in PARAM_SPECS:
        for m in PARAM_SPECS[param]["modes"]:
            print(f"{param}_{m}={get_param(settings, param, m):.3f}")
    for button in FLASH_BUTTONS:
        print(f"flash_{button}={flash_colors.get(button, FLASH_DEFAULT_COLOR)}")


def main(argv):
    command = argv[1] if len(argv) > 1 else "get"
    if command == "get":
        print_state()
        return 0
    if command == "set":
        if len(argv) != 3 or not re.fullmatch(r"[0-9A-Fa-f]{6}", argv[2]):
            print("usage: stick-led-color set <RRGGBB hex>", file=sys.stderr)
            return 2
        value = argv[2].upper()
        _, _, screen_link, settings, flash_colors = load_state()
        if not apply_hex(value, screen_scale() if screen_link else 1.0):
            return 1
        save_state("static", value, screen_link, settings, flash_colors)
        return 0
    if command == "set-mode":
        if len(argv) != 3 or argv[2] not in MODES:
            print(f"usage: stick-led-color set-mode <{'|'.join(MODES)}>", file=sys.stderr)
            return 2
        _, color, screen_link, settings, flash_colors = load_state()
        save_state(argv[2], color, screen_link, settings, flash_colors)
        return 0 if apply_current() else 1
    if command == "set-screen-link":
        if len(argv) != 3 or argv[2] not in ("on", "off"):
            print("usage: stick-led-color set-screen-link <on|off>", file=sys.stderr)
            return 2
        mode, color, _, settings, flash_colors = load_state()
        save_state(mode, color, argv[2] == "on", settings, flash_colors)
        return 0 if apply_current() else 1
    if command == "set-param":
        if len(argv) != 5 or argv[2] not in PARAM_SPECS:
            print(f"usage: stick-led-color set-param <{'|'.join(PARAM_SPECS)}> <mode> <value>", file=sys.stderr)
            return 2
        param, target_mode = argv[2], argv[3]
        key = param_key(param, target_mode)
        if key is None:
            print(f"{param} does not apply to mode {target_mode}", file=sys.stderr)
            return 2
        try:
            value = clamp_param(param, float(argv[4]))
        except ValueError:
            print("invalid value", file=sys.stderr)
            return 2
        mode, color, screen_link, settings, flash_colors = load_state()
        settings[f"{param}_{key}"] = value
        save_state(mode, color, screen_link, settings, flash_colors)
        return 0
    if command == "set-flash-color":
        if len(argv) != 4 or argv[2] not in FLASH_BUTTONS or not re.fullmatch(r"[0-9A-Fa-f]{6}", argv[3]):
            print(f"usage: stick-led-color set-flash-color <{'|'.join(FLASH_BUTTONS)}> <RRGGBB hex>", file=sys.stderr)
            return 2
        mode, color, screen_link, settings, flash_colors = load_state()
        flash_colors[argv[2]] = argv[3].upper()
        save_state(mode, color, screen_link, settings, flash_colors)
        return 0
    if command == "apply":
        return 0 if apply_current() else 1
    if command == "daemon":
        run_daemon()
        return 0
    print(
        "usage: stick-led-color get|set <RRGGBB>|set-mode <mode>|set-screen-link <on|off>"
        "|set-param <param> <mode> <value>|set-flash-color <button> <RRGGBB>|apply|daemon",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
