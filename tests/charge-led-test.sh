#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

grep -q 'linux,default-trigger = "battery-charging-orange-full-green"' \
    "$ROOT/packages/kernel/dts/qcs8550-ayn-common.dtsi.patch"
grep -q 'charge_led.update()' "$ROOT/system_files/usr/libexec/armada/armada-powerd"

python3 - "$ROOT" "$WORK" <<'PYEOF'
import pathlib
import sys

root, work = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path.insert(0, str(root / "system_files/usr/lib/armada"))
import armada_charge_led as charge_led


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


for status, capacity, want in [
    ("Charging", 5, "red"), ("Charging", 19, "red"), ("Charging", 20, None),
    ("Full", 100, None), ("Discharging", 15, "red"), ("Discharging", 16, None),
    ("Not charging", 5, None), ("Unknown", None, None),
]:
    if charge_led.wanted_mode(status, capacity) != want:
        fail(f"{status} {capacity}%: expected {want}")

sys_class = work / "class"
marker = work / "run/charge-led"
led = sys_class / "leds/charger"
battery = sys_class / "power_supply/battery"
led.mkdir(parents=True)
KERNEL = "battery-charging-orange-full-green"


def write(path, text):
    path.write_text(text + "\n")


def read(name, path=None):
    return ((path or led) / name).read_text().strip()


def set_battery(status, capacity):
    write(battery / "status", status)
    write(battery / "capacity", str(capacity))


def multicolor(path, trigger):
    path.mkdir(parents=True, exist_ok=True)
    write(path / "multi_index", "red green blue")
    write(path / "multi_max_intensity", "511 511 511")
    write(path / "max_brightness", "511")
    write(path / "trigger", trigger)


chargeled = charge_led.ChargeLed(sys_class, marker)
chargeled.update()  # nothing registered yet

# The stick LEDs, and a power-led without the trigger (as on the AYANEO trees), are not opted in.
multicolor(sys_class / "leds/power-led", f"[none] timer {KERNEL}")
multicolor(sys_class / "leds/rgb:l1", f"[none] {KERNEL}")
multicolor(led, f"none timer [{KERNEL}]")
battery.mkdir(parents=True)
write(battery / "type", "Battery")
(sys_class / "power_supply/qcom-battmgr-usb").mkdir()
write(sys_class / "power_supply/qcom-battmgr-usb/type", "USB")

set_battery("Charging", 50)
chargeled.update()
if read("trigger") != KERNEL:
    fail("opted-in LED not left to the kernel trigger")

set_battery("Charging", 12)
chargeled.update()
if (read("trigger"), read("multi_intensity"), read("brightness")) != ("none", "511 0 0", "511"):
    fail(f"low charging not solid red: {read('trigger')} {read('multi_intensity')} {read('brightness')}")
if marker.read_text().strip() != "charger":
    fail("borrowed LED not recorded")

set_battery("Discharging", 10)
write(led / "trigger", "untouched")
chargeled.update()
if read("trigger") != "untouched":
    fail("rewrote the LED going from low charging to low unplugged")

# A restart while red finds the LED through the marker, as its trigger now reads none.
write(led / "trigger", f"[none] timer {KERNEL}")
set_battery("Charging", 30)
restarted = charge_led.ChargeLed(sys_class, marker)
restarted.update()
if read("trigger") != KERNEL or marker.exists():
    fail("LED borrowed before a restart not handed back")

for other in ("power-led", "rgb:l1"):
    if read("trigger", sys_class / "leds" / other) != f"[none]{' timer' if other == 'power-led' else ''} {KERNEL}":
        fail(f"touched {other}, which is not opted in")
    if (sys_class / "leds" / other / "multi_intensity").exists():
        fail(f"changed the colour of {other}")
print("charge LED tests passed")
PYEOF
