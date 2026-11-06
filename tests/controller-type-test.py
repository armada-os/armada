#!/usr/bin/env python3
"""controller-type sends a fixed target set instead of reading the live targets back."""

import importlib.machinery
import importlib.util
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

print("controller-type tests passed")
