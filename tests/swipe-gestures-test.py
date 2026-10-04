#!/usr/bin/env python3
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REAL_RUN = subprocess.run
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
loader = importlib.machinery.SourceFileLoader(
    "gesture_control", str(ROOT / "system_files/usr/libexec/armada/armada-control"),
)
spec = importlib.util.spec_from_loader(loader.name, loader)
control = importlib.util.module_from_spec(spec)
loader.exec_module(control)
sys.path.insert(0, str(ROOT / "decky/armada-control/py_modules"))
from armada_control import system as plugin_system


class SwipeGesturesTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config = Path(directory.name) / "swipe-gestures.conf"
        self.config = config
        self.live = True
        self.output = None
        self.commands = []
        for target, replacement in (
            ("SWIPE_GESTURES_CONFIG", config),
            ("session_user_command", lambda *args: ["session-user", *args]),
            ("session_systemctl", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0)),
        ):
            mock = patch.object(control, target, replacement)
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch.object(control.subprocess, "run", self.run_gamescopectl)
        mock.start()
        self.addCleanup(mock.stop)

    def run_gamescopectl(self, command, **kwargs):
        self.commands.append(command)
        self.assertIn("GAMESCOPE_WAYLAND_DISPLAY=gamescope-primary", command)
        self.assertEqual(kwargs["timeout"], 5)
        self.assertTrue(kwargs["check"])
        if command[-1] in ("0", "1"):
            self.live = command[-1] == "1"
            output = ""
        else:
            self.assertEqual(command[-1], "help")
            output = self.output if self.output is not None else "enable_touch_gestures: Enable/Disable the usage of touch gestures\n"
        return subprocess.CompletedProcess(command, 0, stdout="", stderr=output)

    def test_default_and_restart_persistence(self):
        self.assertEqual(control.action_get_swipe_gestures_enabled({}), {"enabled": True})
        for enabled in (False, True):
            self.assertEqual(control.action_set_swipe_gestures_enabled({"enabled": enabled}), {"enabled": enabled})
            self.assertEqual(self.live, enabled)
            self.assertEqual(control.action_get_swipe_gestures_enabled({}), {"enabled": enabled})
            expected = f"enabled={int(enabled)}\n"
            self.assertEqual(self.config.read_text(), expected)
            self.assertEqual(self.session_value(), "" if enabled else "1")

    def session_value(self, inherited=""):
        source = (ROOT / "system_files/usr/share/gamescope-session-plus/sessions.d/steam").read_text()
        block = source.split('_armada_swipe_gestures_config=', 1)[1].split('unset _armada_swipe_gestures_config _armada_line', 1)[0]
        script = '_armada_swipe_gestures_config=' + block + '\nprintf "%s" "${DISABLE_TOUCH_GESTURES:-}"'
        result = REAL_RUN(
            ["bash", "-eu", "-c", script], text=True, capture_output=True, check=True,
            env={**os.environ, "ARMADA_SWIPE_GESTURES_CONFIG": str(self.config), "DISABLE_TOUCH_GESTURES": inherited},
        )
        return result.stdout

    def test_missing_config_preserves_session_default(self):
        self.assertEqual(self.session_value(), "")
        self.assertEqual(self.session_value("1"), "1")

    def test_explicit_enable_clears_inherited_disable(self):
        self.config.write_text("enabled=1\n")
        self.assertEqual(self.session_value("1"), "")

    def test_config_parsers_agree(self):
        for text, enabled in (
            ("# comment\nunknown=1\n", True),
            ("enabled=no\n", True),
            (" enabled = 0 \n", False),
            ("enabled=0\nenabled=1", True),
            ("enabled=1\nenabled=0", False),
        ):
            self.config.write_text(text)
            self.assertEqual(control.action_get_swipe_gestures_enabled({})["enabled"], enabled)
            self.assertEqual(self.session_value(), "" if enabled else "1")

    def test_plugin_getter_defaults_on_service_failure(self):
        for error in (RuntimeError("unknown action"), OSError("socket unavailable"), KeyError("enabled")):
            with patch.object(plugin_system, "call", side_effect=error):
                self.assertTrue(plugin_system.swipe_gestures_enabled())
        with patch.object(plugin_system, "call", return_value={"enabled": False}):
            self.assertFalse(plugin_system.swipe_gestures_enabled())

    def test_non_utf8_config_defaults_and_can_be_repaired(self):
        self.config.write_bytes(b"\xff\n")
        self.assertTrue(control.action_get_swipe_gestures_enabled({})["enabled"])
        control.action_set_swipe_gestures_enabled({"enabled": False})
        self.assertEqual(self.config.read_text(), "enabled=0\n")

    def test_unreadable_config_does_not_prevent_replacement(self):
        with patch.object(Path, "read_text", side_effect=PermissionError("unreadable")):
            self.assertTrue(control.action_get_swipe_gestures_enabled({})["enabled"])
            control.action_set_swipe_gestures_enabled({"enabled": False})
        self.assertEqual(self.config.read_text(), "enabled=0\n")

    def test_desktop_only_saves_preference(self):
        with patch.object(control, "session_systemctl", return_value=subprocess.CompletedProcess([], 3)):
            control.action_set_swipe_gestures_enabled({"enabled": False})
        self.assertEqual(self.commands, [])
        self.assertFalse(control.action_get_swipe_gestures_enabled({})["enabled"])

    def test_invalid_values_do_not_change_anything(self):
        for value in (None, 0, 1, "false", [], {}):
            with self.assertRaises(ValueError):
                control.action_set_swipe_gestures_enabled({"enabled": value})
        self.assertFalse(self.config.exists())
        self.assertEqual(self.commands, [])

    def test_unknown_convar_does_not_save(self):
        self.output = "Command not found.\n"
        with self.assertRaisesRegex(RuntimeError, "does not support"):
            control.action_set_swipe_gestures_enabled({"enabled": False})
        self.assertFalse(self.config.exists())

    def test_set_failure_does_not_save(self):
        def fail_set(command, **kwargs):
            if command[-1] == "help":
                return self.run_gamescopectl(command, **kwargs)
            raise subprocess.CalledProcessError(1, command)

        with patch.object(control.subprocess, "run", side_effect=fail_set):
            with self.assertRaises(subprocess.CalledProcessError):
                control.action_set_swipe_gestures_enabled({"enabled": False})
        self.assertFalse(self.config.exists())

    def test_write_failure_restores_live_value(self):
        with patch.object(control, "atomic_write", side_effect=OSError("read-only")):
            with self.assertRaises(OSError):
                control.action_set_swipe_gestures_enabled({"enabled": False})
        self.assertTrue(self.live)
        self.assertFalse(self.config.exists())

    def test_connection_failure_preserves_saved_preference(self):
        self.config.write_text("enabled=0\n")
        with patch.object(control.subprocess, "run", side_effect=subprocess.TimeoutExpired("gamescopectl", 5)):
            with self.assertRaises(subprocess.TimeoutExpired):
                control.action_set_swipe_gestures_enabled({"enabled": True})
        self.assertEqual(self.config.read_text(), "enabled=0\n")


if __name__ == "__main__":
    unittest.main()
