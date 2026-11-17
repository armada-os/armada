"""Low-battery red for the multicolor charge LED.

A devicetree opts its charge LED in by giving it the kernel's
battery-charging-orange-full-green trigger, which has no low-battery colour.
Below the thresholds this shows red instead and hands the LED back to that
trigger afterwards. LEDs with any other trigger are left alone.
"""
import pathlib
import re

KERNEL_TRIGGER = "battery-charging-orange-full-green"
CHARGING_RED_BELOW = 20
UNPLUGGED_RED_AT = 15

_UNSET = object()


def _read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def _write(path, value):
    try:
        path.write_text(f"{value}\n")
        return True
    except OSError:
        return False


def active_trigger(led):
    match = re.search(r"\[([^]]+)\]", _read(led / "trigger"))
    return match.group(1) if match else ""


def wanted_mode(status, capacity):
    """None leaves the LED to the kernel trigger; "red" shows solid red."""
    if capacity is None:
        return None
    if status == "Charging" and capacity < CHARGING_RED_BELOW:
        return "red"
    # Blinking would go through the LPG's hardware pattern, which mixes up the channels.
    if status == "Discharging" and capacity <= UNPLUGGED_RED_AT:
        return "red"
    return None


class ChargeLed:
    def __init__(self, sys_class=pathlib.Path("/sys/class"), marker=pathlib.Path("/run/armada/charge-led")):
        self.sys_class = sys_class
        # Names the LED while it shows red, when its trigger reads none.
        self.marker = marker
        self.led = None
        self.battery = None
        self.mode = _UNSET

    # The battery and its trigger may register after armada-powerd starts.
    def discover(self):
        borrowed = _read(self.marker)
        for led in sorted((self.sys_class / "leds").glob("*")):
            if "red" not in _read(led / "multi_index").split():
                continue
            if active_trigger(led) == KERNEL_TRIGGER or led.name == borrowed:
                self.led = led
                break
        for supply in sorted((self.sys_class / "power_supply").glob("*")):
            if _read(supply / "type") == "Battery":
                self.battery = supply
                break

    def update(self):
        if not self.led or not self.battery:
            self.discover()
            if not self.led or not self.battery:
                return
        capacity = _read(self.battery / "capacity")
        mode = wanted_mode(_read(self.battery / "status"), int(capacity) if capacity.isdigit() else None)
        if mode == self.mode:
            return
        if mode is None:
            _write(self.led / "trigger", KERNEL_TRIGGER)
            self.marker.unlink(missing_ok=True)
        else:
            self.marker.parent.mkdir(parents=True, exist_ok=True)
            _write(self.marker, self.led.name)
            _write(self.led / "trigger", "none")
            channels = _read(self.led / "multi_index").split()
            peaks = _read(self.led / "multi_max_intensity").split() or ["255"] * len(channels)
            _write(self.led / "multi_intensity",
                   " ".join(peak if colour == "red" else "0" for colour, peak in zip(channels, peaks)))
            _write(self.led / "brightness", _read(self.led / "max_brightness") or "255")
        self.mode = mode
