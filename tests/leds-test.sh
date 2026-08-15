#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 -B - "$ROOT" "$WORK" <<'PYEOF'
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import sys
import time

root = pathlib.Path(sys.argv[1])
work = pathlib.Path(sys.argv[2])

led_dir = work / "leds"
sides = ("l", "r")
channels = ("r", "g", "b")
indexes = (1, 2, 3, 4)
for side in sides:
    for channel in channels:
        for index in indexes:
            path = led_dir / f"{side}:{channel}{index}"
            path.mkdir(parents=True)
            (path / "brightness").write_text("0", encoding="utf-8")

config_path = work / "leds.json"
os.environ["ARMADA_LED_CONFIG"] = str(config_path)
os.environ["ARMADA_LED_DIR"] = str(led_dir)

ledd_path = root / "system_files/usr/libexec/armada/armada-ledd"
loader = importlib.machinery.SourceFileLoader("armada_ledd", str(ledd_path))
spec = importlib.util.spec_from_loader("armada_ledd", loader)
ledd = importlib.util.module_from_spec(spec)
loader.exec_module(ledd)


def read_channel(name):
    return (led_dir / name / "brightness").read_text(encoding="utf-8").strip()


# A missing config leaves the rings dark rather than guessing a colour.
config = ledd.load_config()
assert config["enabled"] is False, config
assert config["mode"] == "static", config

config_path.write_text(json.dumps({
    "enabled": True,
    "mode": "breathing",
    "brightness": 150,
    "period": 900,
    "left": "#00B0FF",
    "right": "nonsense",
}), encoding="utf-8")
config = ledd.load_config()
assert config["enabled"] is True, config
assert config["mode"] == "breathing", config
assert config["brightness"] == 100, config
assert config["period"] == 30.0, config
assert config["left"] == (0, 0xB0, 0xFF), config
# An unparsable colour falls back to the default instead of dropping the ring.
assert config["right"] == (0xFF, 0, 0), config

config_path.write_text(json.dumps({"enabled": True, "mode": "strobe", "brightness": -5}), encoding="utf-8")
config = ledd.load_config()
assert config["mode"] == "static", config
assert config["brightness"] == 0, config

rings = ledd.Rings(led_dir)
assert rings.present()

# Every emitter of a ring carries the same value: the four LEDs are not evenly
# spaced, so per-position output would not line up anyway.
rings.apply({"l": (255, 0, 0), "r": (0, 0, 255)}, 1.0)
for index in indexes:
    assert read_channel(f"l:r{index}") == "255", read_channel(f"l:r{index}")
    assert read_channel(f"l:g{index}") == "0"
    assert read_channel(f"r:b{index}") == "255"
    assert read_channel(f"r:r{index}") == "0"

# Perceptual level is gamma corrected before it reaches the PWM registers.
rings.apply({"l": (255, 255, 255), "r": (255, 255, 255)}, 0.5)
expected = str(int(round(255 * (0.5 ** ledd.GAMMA))))
assert read_channel("l:r1") == expected, (read_channel("l:r1"), expected)
assert expected != "128", "gamma correction is not being applied"

rings.off()
assert read_channel("l:r1") == "0"
rings.close()

# Breathing spans the full range and stays inside it.
levels = [ledd.breath_level(step * 0.05, 4.0) for step in range(80)]
assert min(levels) >= 0.0, min(levels)
assert max(levels) <= 1.0, max(levels)
assert max(levels) > 0.99, max(levels)
assert levels[0] < 0.01, levels[0]

# Only devices with a verified ring layout are driven.
assert ledd.SUPPORTED_DEVICES == ("ayn-odin-3",)

# The shipped colour is fully saturated so the hue slider does something.
assert ledd.DEFAULT_COLOR == "ff0000"
red, green, blue = ledd.parse_color(ledd.DEFAULT_COLOR, (0, 0, 0))
assert round((red - min(red, green, blue)) / red * 100) == 100, (red, green, blue)

# The unit is only useful if the image actually enables it, and the LED
# controllers can probe after it starts, so it must not carry a Condition.
unit = (root / "system_files/usr/lib/systemd/system/armada-leds.service").read_text(encoding="utf-8")
assert not [line for line in unit.splitlines() if line.strip().startswith("Condition")], unit
assert "WantedBy=multi-user.target" in unit, unit
vendor = (root / "build_files/40-vendor-system-files.sh").read_text(encoding="utf-8")
assert "systemctl enable armada-leds.service" in vendor

# Unsupported devices exit instead of driving unknown hardware.
os.environ["ARMADA_DEVICE_ID"] = "ayn-odin-2"
assert ledd.main() == 0

# A supported device with no rings yet waits, then gives up rather than hanging.
os.environ["ARMADA_DEVICE_ID"] = "ayn-odin-3"
ledd.LED_DIR = work / "missing"
ledd.PROBE_TIMEOUT = 0.2
started = time.monotonic()
assert ledd.main() == 0
assert time.monotonic() - started < 5, "probe wait did not time out"

lib = root / "system_files/usr/lib/armada"
sys.path.insert(0, str(lib))
import armada_perf  # noqa: F401

control_path = root / "system_files/usr/libexec/armada/armada-control"
loader = importlib.machinery.SourceFileLoader("armada_control_daemon", str(control_path))
spec = importlib.util.spec_from_loader("armada_control_daemon", loader)
control = importlib.util.module_from_spec(spec)
loader.exec_module(control)

assert "set_leds" in control.ACTIONS
assert "get_leds" in control.ACTIONS

normalized = control.normalize_leds({
    "enabled": 1,
    "mode": "BREATHING",
    "brightness": 250,
    "period": 0.1,
    "left": "#0AF",
    "right": "00b0ff",
})
assert normalized["enabled"] is True, normalized
assert normalized["mode"] == "breathing", normalized
assert normalized["brightness"] == 100, normalized
assert normalized["period"] == 0.5, normalized
# Three digit hex is not expanded; the daemon expects six.
assert normalized["left"] == "ff0000", normalized
assert normalized["right"] == "00b0ff", normalized

for bad in ("string", 5, None, []):
    try:
        control.normalize_leds(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"normalize_leds accepted {bad!r}")

control.LED_DIR = led_dir
assert control.leds_present()
control.LED_DIR = work / "empty"
assert not control.leds_present()

control.LED_CONFIG = work / "control-leds.json"
control.LED_DIR = led_dir
control.device_env = lambda: {"ARMADA_DEVICE_ID": "ayn-odin-3"}
assert control.leds_supported()
control.device_env = lambda: {"ARMADA_DEVICE_ID": "ayn-odin-2"}
assert not control.leds_supported()

try:
    control.action_set_leds({"leds": {"enabled": True}})
except RuntimeError:
    pass
else:
    raise AssertionError("set_leds ran on an unverified device")

# A corrupt config reads back as the defaults instead of raising.
control.LED_CONFIG.write_text("{ not json", encoding="utf-8")
assert control.read_leds() == control.LED_DEFAULTS

print("led test passed")
PYEOF
