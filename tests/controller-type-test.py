#!/usr/bin/env python3
"""controller-type sends a fixed target set instead of reading the live targets back."""

import importlib.machinery
import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/libexec/armada/controller-type"

loader = importlib.machinery.SourceFileLoader("controller_type", str(SCRIPT))
spec = importlib.util.spec_from_loader("controller_type", loader)
ct = importlib.util.module_from_spec(spec)
loader.exec_module(ct)

assert ct.target_devices("deck-uhid") == ["deck-uhid", "keyboard", "mouse"]
assert ct.target_devices("ds5") == ["ds5", "keyboard", "mouse"]
assert ct.target_devices("xbox-series") == ["xbox-series", "keyboard", "mouse", "touchpad"]
assert ct.target_devices("xb360") == ["xb360", "keyboard", "mouse", "touchpad"]

calls = []


def fake_run(command, **kwargs):
    calls.append(command)


ct.composite_paths = lambda: ["/org/shadowblip/InputPlumber/CompositeDevice0"]
ct.subprocess.run = fake_run
assert ct.apply_type("deck-uhid")
assert calls == [[
    "busctl", "--system", "call", ct.SERVICE, "/org/shadowblip/InputPlumber/CompositeDevice0",
    ct.IFACE, "SetTargetDevices", "as", "3", "deck-uhid", "keyboard", "mouse",
]], calls

# Direct mode masks InputPlumber, starts the injector and skips the D-Bus apply.
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    ct.DIRECT_FLAG = tmp / "direct-input"
    ct.CONFIG = tmp / "controller.conf"
    ct.INPUTPLUMBER_RULES = tmp / "rules.d"
    ct.INPUTPLUMBER_RULES.mkdir()
    stale = ct.INPUTPLUMBER_RULES / "50-inputplumber-hide-event5-early.rules"
    stale.write_text("", encoding="utf-8")
    ct.available_types = lambda: ["deck-uhid", "xbox-series", "xb360", "ds5", "direct"]
    ct.direct_nodes = lambda: ["/sys/class/input/event5"]
    calls.clear()
    assert ct.main(["controller-type", "set", "direct"]) == 0
    assert ct.DIRECT_FLAG.exists()
    assert not stale.exists()
    assert ["systemctl", "mask", "--now", "inputplumber.service"] in calls, calls
    assert ["udevadm", "trigger", "--action=add", "/sys/class/input/event5"] in calls, calls
    assert calls[-1] == ["systemctl", "restart", "armada-direct-input.service"], calls
    assert not any(c[0] == "busctl" for c in calls), calls
    assert ct.load_type(ct.available_types()) == "direct"

    calls.clear()
    assert ct.main(["controller-type", "apply"]) == 0
    assert calls == [], calls

    calls.clear()
    assert ct.main(["controller-type", "set", "deck-uhid"]) == 0
    assert not ct.DIRECT_FLAG.exists()
    assert calls.index(["systemctl", "stop", "armada-direct-input.service"]) \
        < calls.index(["systemctl", "unmask", "inputplumber.service"]) \
        < calls.index(["systemctl", "start", "inputplumber.service"]), calls
    assert calls[-1][0] == "busctl", calls
    assert ct.load_type(ct.available_types()) == "deck-uhid"

print("controller-type tests passed")
