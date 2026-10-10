#!/usr/bin/env python3
"""Lease/ownership tests; native pulse-shape tests run in the InputPlumber RPM."""

import ast
import importlib.machinery
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "system_files/usr/libexec/armada/virtual-trackpads"
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
repository = types.ModuleType("gi.repository")
repository.Gio = types.SimpleNamespace()
repository.GLib = types.SimpleNamespace()
loader = importlib.machinery.SourceFileLoader("virtual_trackpads_daemon", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
daemon = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {
    "fcntl": types.ModuleType("fcntl"),
    "gi": types.ModuleType("gi"),
    "gi.repository": repository,
}):
    loader.exec_module(daemon)


class HapticsTests(unittest.TestCase):
    def make_daemon(self, strength=100):
        pads = daemon.VirtualTrackpads.__new__(daemon.VirtualTrackpads)
        pads.config = {"hapticStrength": strength, "enabled": True, "blockTouchscreen": False}
        pads.haptics_token = None
        pads.haptics_native_check_at = 0.0
        pads.haptics_lease_at = 0.0
        pads.native_haptics = False
        pads.fd = 42
        pads.ip = Mock()
        return pads

    def test_daemon_never_synthesizes_or_stops_motor_effects(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        calls = [node.func.attr for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        for forbidden in ("rumble", "stop_rumble", "haptic", "stop_haptics", "pulse_inertia_haptics"):
            self.assertNotIn(forbidden, calls)
        strings = [node.value for node in ast.walk(tree)
                   if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        self.assertNotIn("Rumble", strings)
        self.assertNotIn("Stop", strings)

    def test_native_ack_is_diagnostic_and_never_writes_motor(self):
        pads = self.make_daemon()
        pads.haptics_token = "test-owner"
        with tempfile.TemporaryDirectory() as temporary:
            acknowledgement = Path(temporary) / "ack"
            acknowledgement.write_text("old-owner", encoding="utf-8")
            with patch.object(daemon, "HAPTICS_NATIVE_PATH", acknowledgement), patch.object(
                daemon.time, "monotonic", return_value=10.0
            ):
                self.assertFalse(pads.using_native_haptics())
                acknowledgement.write_text("test-owner", encoding="utf-8")
                pads.haptics_native_check_at = 0.0
                self.assertTrue(pads.using_native_haptics())
                self.assertEqual(pads.ip.mock_calls, [])

    def test_lease_publishes_zero_and_full_strength(self):
        pads = self.make_daemon(0)
        with tempfile.TemporaryDirectory() as temporary:
            owner = Path(temporary) / "owner.json"
            with patch.object(daemon, "HAPTICS_OWNER_PATH", owner):
                pads.refresh_haptics_owner(force=True)
                data = json.loads(owner.read_text(encoding="utf-8"))
                self.assertEqual(data["strength"], 0)
                self.assertEqual(data["token"], pads.haptics_token)
                pads.config["hapticStrength"] = 100
                pads.refresh_haptics_owner(force=True)
                self.assertEqual(json.loads(owner.read_text(encoding="utf-8"))["strength"], 100)
                self.assertEqual(pads.ip.mock_calls, [])

    def test_lease_not_created_for_normal_touch_or_screen_blocking(self):
        pads = self.make_daemon()
        with tempfile.TemporaryDirectory() as temporary:
            owner = Path(temporary) / "owner.json"
            with patch.object(daemon, "HAPTICS_OWNER_PATH", owner):
                pads.config["enabled"] = False
                pads.refresh_haptics_owner(force=True)
                self.assertFalse(owner.exists())
                pads.config.update(enabled=True, blockTouchscreen=True)
                pads.refresh_haptics_owner(force=True)
                self.assertFalse(owner.exists())

    def test_lease_refresh_is_throttled(self):
        pads = self.make_daemon(35)
        with tempfile.TemporaryDirectory() as temporary:
            owner = Path(temporary) / "owner.json"
            with patch.object(daemon, "HAPTICS_OWNER_PATH", owner), patch.object(
                daemon.time, "monotonic", return_value=10.0
            ):
                pads.refresh_haptics_owner()
                pads.config["hapticStrength"] = 80
                pads.refresh_haptics_owner()
                self.assertEqual(json.loads(owner.read_text(encoding="utf-8"))["strength"], 35)


if __name__ == "__main__":
    unittest.main()
