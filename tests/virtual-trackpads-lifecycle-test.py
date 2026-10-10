#!/usr/bin/env python3
"""Worker lifecycle, validated shortcut API, and physical chord regressions."""

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
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
from armada_virtual_trackpads import ShortcutHold, sanitize_config, trackpad_rect


def load_script(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


with patch.dict(sys.modules, {
    "grp": types.ModuleType("grp"), "pwd": types.ModuleType("pwd"),
    "armada_game_tweaks": types.ModuleType("armada_game_tweaks"),
    "armada_perf": types.SimpleNamespace(SESSION_SOCKET="/run/armada/perf.sock"),
}):
    control = load_script("control_lifecycle_test", "system_files/usr/libexec/armada/armada-control")

ecodes = types.SimpleNamespace(
    ABS_Z=2, ABS_RZ=5, ABS_BRAKE=10, ABS_GAS=9, EV_KEY=1, EV_ABS=3,
    EV_SYN=0, SYN_DROPPED=3,
)
with patch.dict(sys.modules, {
    "evdev": types.SimpleNamespace(InputDevice=Mock(), ecodes=ecodes, ff=Mock()),
}):
    shortcut = load_script("shortcut_lifecycle_test", "system_files/usr/libexec/armada/virtual-trackpads-shortcut")

with patch.dict(sys.modules, {
    "fcntl": types.SimpleNamespace(ioctl=Mock()),
    "gi": types.ModuleType("gi"),
    "gi.repository": types.SimpleNamespace(Gio=types.SimpleNamespace(), GLib=types.SimpleNamespace()),
}):
    daemon = load_script("daemon_lifecycle_test", "system_files/usr/libexec/armada/virtual-trackpads")


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        control.VIRTUAL_TRACKPADS_LIFECYCLE.clear()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.notice_path = Path(self.directory.name) / "notice.json"
        patch.object(control, "VIRTUAL_TRACKPADS_NOTICE", self.notice_path).start()
        self.run_patch = patch.object(control, "run")
        self.run = self.run_patch.start()
        self.session_patch = patch.object(control, "session_systemctl", return_value=types.SimpleNamespace(returncode=0))
        self.session = self.session_patch.start()
        self.game_patch = patch.object(control, "game_mode_active", return_value=True)
        self.game = self.game_patch.start()
        self.addCleanup(patch.stopall)

    def actions(self):
        return [call.args[0][1:] for call in self.run.call_args_list]

    def test_disabled_boot_only_starts_optional_shortcut_and_does_not_poll_systemctl(self):
        config = sanitize_config({})
        control.sync_virtual_trackpads(config)
        self.assertEqual(self.actions(), [
            ["stop", control.VIRTUAL_TRACKPADS_SERVICE],
            ["reload-or-restart", control.VIRTUAL_TRACKPADS_SHORTCUT_SERVICE],
        ])
        self.assertEqual(self.session.call_args.args, ("stop", control.VIRTUAL_TRACKPADS_OVERLAY_SERVICE))
        self.run.reset_mock()
        self.session.reset_mock()
        control.sync_virtual_trackpads(config)
        self.run.assert_not_called()
        self.session.assert_not_called()

    def test_toggle_off_stops_capture_and_overlay_but_keeps_shortcut(self):
        config = sanitize_config({"enabled": True})
        control.sync_virtual_trackpads(config)
        self.run.reset_mock()
        self.session.reset_mock()
        control.sync_virtual_trackpads({**config, "enabled": False})
        self.assertEqual(self.actions(), [["stop", control.VIRTUAL_TRACKPADS_SERVICE]])
        self.assertEqual(self.session.call_args.args, ("stop", control.VIRTUAL_TRACKPADS_OVERLAY_SERVICE))

    def test_every_worker_stops_when_shortcut_is_disabled_too(self):
        control.sync_virtual_trackpads(sanitize_config({"enabled": True}))
        self.run.reset_mock()
        control.sync_virtual_trackpads(sanitize_config({"enabled": False, "shortcutEnabled": False}))
        self.assertEqual(self.actions(), [
            ["stop", control.VIRTUAL_TRACKPADS_SERVICE],
            ["stop", control.VIRTUAL_TRACKPADS_SHORTCUT_SERVICE],
        ])

    def test_game_mode_only_stops_in_desktop_and_restarts_on_return(self):
        config = sanitize_config({"enabled": True})
        control.sync_virtual_trackpads(config)
        self.run.reset_mock()
        self.game.return_value = False
        control.sync_virtual_trackpads(config)
        self.assertEqual(self.actions(), [["stop", control.VIRTUAL_TRACKPADS_SERVICE]])
        self.run.reset_mock()
        self.game.return_value = True
        control.sync_virtual_trackpads(config)
        self.assertEqual(self.actions(), [["reload-or-restart", control.VIRTUAL_TRACKPADS_SERVICE]])

    def test_desktop_opt_in_captures_without_starting_overlay(self):
        self.game.return_value = False
        control.sync_virtual_trackpads(sanitize_config({"enabled": True, "gameModeOnly": False}))
        self.assertIn(["reload-or-restart", control.VIRTUAL_TRACKPADS_SERVICE], self.actions())
        self.assertEqual(self.session.call_args.args[0], "stop")

    def test_independent_touch_blocking_needs_capture_without_overlay(self):
        control.sync_virtual_trackpads(sanitize_config({"blockTouchscreen": True}))
        self.assertIn(["reload-or-restart", control.VIRTUAL_TRACKPADS_SERVICE], self.actions())
        self.assertEqual(self.session.call_args.args[0], "stop")

    def test_secondary_change_restarts_overlay_and_reloads_capture(self):
        config = sanitize_config({"enabled": True})
        control.sync_virtual_trackpads(config)
        self.run.reset_mock()
        self.session.reset_mock()
        control.sync_virtual_trackpads({**config, "screen": "secondary"})
        self.assertEqual(self.actions(), [["reload-or-restart", control.VIRTUAL_TRACKPADS_SERVICE]])
        self.assertEqual(self.session.call_args.args, ("restart", control.VIRTUAL_TRACKPADS_OVERLAY_SERVICE))

    def test_screen_modes_need_capture_without_overlay(self):
        for mode in ("halves", "fullLeft", "fullRight"):
            with self.subTest(mode=mode):
                control.VIRTUAL_TRACKPADS_LIFECYCLE.clear()
                self.run.reset_mock()
                self.session.reset_mock()
                control.sync_virtual_trackpads(sanitize_config({"enabled": True, "mode": mode}))
                self.assertIn(["reload-or-restart", control.VIRTUAL_TRACKPADS_SERVICE], self.actions())
                self.assertEqual(self.session.call_args.args[0], "stop")

    def test_closing_secondary_session_releases_capture_and_opening_it_restores(self):
        config = sanitize_config({"enabled": True, "screen": "secondary"})
        control.sync_virtual_trackpads(config)
        self.run.reset_mock()
        self.session.reset_mock()
        self.game.side_effect = lambda **kwargs: kwargs.get("screen") != "secondary"
        control.sync_virtual_trackpads(config)
        self.assertEqual(self.actions(), [["stop", control.VIRTUAL_TRACKPADS_SERVICE]])
        self.assertEqual(self.session.call_args.args[0], "stop")
        self.game.side_effect = None
        self.run.reset_mock()
        control.sync_virtual_trackpads(config)
        self.assertEqual(self.actions(), [["reload-or-restart", control.VIRTUAL_TRACKPADS_SERVICE]])
        self.assertEqual(self.session.call_args.args[0], "restart")

    def test_failed_start_is_retried_on_next_reconciliation(self):
        config = sanitize_config({"enabled": True})
        self.run.side_effect = RuntimeError("could not start")
        with self.assertRaises(RuntimeError):
            control.sync_virtual_trackpads(config)
        self.run.side_effect = None
        self.run.reset_mock()
        control.sync_virtual_trackpads(config)
        self.assertEqual(self.actions()[0], ["reload-or-restart", control.VIRTUAL_TRACKPADS_SERVICE])

    def test_shortcut_off_recovers_overlay_that_exited_before_notice_publication(self):
        config = sanitize_config({"enabled": True})
        control.sync_virtual_trackpads(config)
        self.run.reset_mock()
        self.session.reset_mock()
        with patch.object(control.time, "time", return_value=100.0):
            config["enabled"] = False
            control.sync_virtual_trackpads(config, shortcut_notice=True)
            self.assertEqual(self.actions(), [["stop", control.VIRTUAL_TRACKPADS_SERVICE]])
            # The overlay can observe the persisted off config and exit while
            # stopping capture. The cached same-screen key must not suppress
            # its restart after the notice has been published.
            self.assertIsNone(control.VIRTUAL_TRACKPADS_LIFECYCLE.get("capture"))
            self.assertEqual(self.session.call_args.args, ("restart", control.VIRTUAL_TRACKPADS_OVERLAY_SERVICE))
            notice = json.loads(self.notice_path.read_text())
            self.assertFalse(notice["enabled"])
            self.assertEqual(notice["expires"], 102.0)
        self.run.reset_mock()
        with patch.object(control.time, "time", return_value=102.1):
            control.sync_virtual_trackpads(config)
        self.run.assert_not_called()
        self.assertEqual(self.session.call_args.args, ("stop", control.VIRTUAL_TRACKPADS_OVERLAY_SERVICE))

    def test_shortcut_in_screen_modes_opens_notice_then_stops_only_overlay(self):
        for mode in ("halves", "fullLeft", "fullRight"):
            control.VIRTUAL_TRACKPADS_LIFECYCLE.clear()
            self.run.reset_mock()
            config = sanitize_config({"enabled": True, "mode": mode})
            with patch.object(control.time, "time", return_value=100.0):
                control.sync_virtual_trackpads(config, shortcut_notice=True)
            self.assertIn(["reload-or-restart", control.VIRTUAL_TRACKPADS_SERVICE], self.actions())
            self.assertEqual(self.session.call_args.args, ("restart", control.VIRTUAL_TRACKPADS_OVERLAY_SERVICE))
            self.run.reset_mock()
            with patch.object(control.time, "time", return_value=102.1):
                control.sync_virtual_trackpads(config)
            self.run.assert_not_called()
            self.assertEqual(self.session.call_args.args, ("stop", control.VIRTUAL_TRACKPADS_OVERLAY_SERVICE))

    def test_failed_capture_start_does_not_publish_success_notice(self):
        self.run.side_effect = RuntimeError("could not start")
        with self.assertRaises(RuntimeError):
            control.sync_virtual_trackpads(sanitize_config({"enabled": True}), shortcut_notice=True)
        self.assertFalse(self.notice_path.exists())

    def test_shortcut_after_expired_notice_restarts_overlay_without_capture(self):
        config = sanitize_config({})
        with patch.object(control.time, "time", return_value=100.0):
            control.sync_virtual_trackpads(config, shortcut_notice=True)
        self.run.reset_mock()
        self.session.reset_mock()
        # Overlay may have exited, but control's two-second reconciliation
        # has not yet cleared its remembered screen.
        with patch.object(control.time, "time", return_value=102.1):
            control.sync_virtual_trackpads(config, shortcut_notice=True)
        self.run.assert_not_called()
        self.assertEqual(self.session.call_args.args, ("restart", control.VIRTUAL_TRACKPADS_OVERLAY_SERVICE))
        self.assertAlmostEqual(json.loads(self.notice_path.read_text())["expires"], 104.1)

    def test_off_notice_falls_back_to_primary_when_secondary_session_closed(self):
        self.game.side_effect = lambda **kwargs: kwargs.get("screen") != "secondary"
        with patch.object(control.time, "time", return_value=100.0):
            control.sync_virtual_trackpads(sanitize_config({"screen": "secondary"}), shortcut_notice=True)
        self.assertEqual(json.loads(self.notice_path.read_text())["screen"], "primary")
        self.assertEqual(self.session.call_args.args, ("restart", control.VIRTUAL_TRACKPADS_OVERLAY_SERVICE))
        self.assertNotIn(["reload-or-restart", control.VIRTUAL_TRACKPADS_SERVICE], self.actions())

    def test_desktop_notice_uses_session_notification_without_overlay_or_capture(self):
        self.game.return_value = False
        with patch.object(control, "session_user_command", side_effect=lambda *args: list(args)) as session_user, patch.object(
            control.subprocess, "run"
        ) as notify:
            control.sync_virtual_trackpads(sanitize_config({}), shortcut_notice=True)
        self.assertEqual(session_user.call_args.args[-1], "Virtual trackpads disabled")
        self.assertEqual(notify.call_args.args[0][0], "/usr/bin/notify-send")
        self.assertFalse(self.notice_path.exists())
        self.assertNotIn(["reload-or-restart", control.VIRTUAL_TRACKPADS_SERVICE], self.actions())
        self.assertEqual(self.session.call_args.args[0], "stop")

    def test_notice_ignores_malformed_or_expired_state(self):
        for value in ({}, [], {"enabled": True, "created": 98, "expires": 102, "screen": "primary"},
                      {"enabled": True, "created": 100, "expires": 102, "screen": "unknown"},
                      {"enabled": True, "created": 98, "expires": 100, "screen": "primary"}):
            with self.subTest(value=value), patch.object(control.time, "time", return_value=100.0):
                self.notice_path.write_text(json.dumps(value))
                self.assertIsNone(control.virtual_trackpads_notice())

    def test_notice_timestamps_are_normalized_before_lifecycle_deadline_comparison(self):
        self.notice_path.write_text(json.dumps({
            "enabled": False, "created": "100.0", "expires": "102.0", "screen": "primary",
        }))
        with patch.object(control.time, "time", return_value=100.5):
            notice = control.virtual_trackpads_notice()
            self.assertIsInstance(notice["created"], float)
            self.assertIsInstance(notice["expires"], float)
            control.sync_virtual_trackpads(sanitize_config({}))
        with patch.object(control.time, "time", return_value=102.1):
            control.sync_virtual_trackpads(sanitize_config({}))
        self.assertEqual(self.session.call_args.args, ("stop", control.VIRTUAL_TRACKPADS_OVERLAY_SERVICE))


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config_path = Path(self.directory.name) / "config.json"
        patch.object(control, "VIRTUAL_TRACKPADS_CONFIG", self.config_path).start()
        self.sync = patch.object(control, "sync_virtual_trackpads").start()
        patch.object(control, "action_get_controller_type", return_value={"value": "deck-uhid"}).start()
        patch.object(control, "bottom_screen_supported", return_value=False).start()
        self.addCleanup(patch.stopall)

    def test_toggle_persists_and_clears_independent_blocking(self):
        self.config_path.write_text(json.dumps(sanitize_config({"blockTouchscreen": True})))
        result = control.action_toggle_virtual_trackpads({})
        self.assertTrue(result["enabled"])
        self.assertFalse(result["blockTouchscreen"])
        self.assertEqual(result["shortcutButtons"], ["L3", "R3"])
        self.assertEqual(result["shortcutHoldSeconds"], 3)
        self.assertTrue(json.loads(self.config_path.read_text())["enabled"])
        self.sync.assert_called_once()
        self.assertTrue(self.sync.call_args.kwargs["shortcut_notice"])

    def test_disabled_shortcut_cannot_toggle(self):
        self.config_path.write_text(json.dumps(sanitize_config({"shortcutEnabled": False})))
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            control.action_toggle_virtual_trackpads({})
        self.sync.assert_not_called()

    def test_invalid_controller_cannot_toggle_or_publish_notice(self):
        with patch.object(control, "action_get_controller_type", return_value={"value": "xbox-series"}):
            with self.assertRaisesRegex(RuntimeError, "Steam Deck"):
                control.action_toggle_virtual_trackpads({})
        self.sync.assert_not_called()
        self.assertFalse(self.config_path.exists())

    def test_menu_changes_do_not_publish_shortcut_notices(self):
        control.action_set_virtual_trackpads({"config": sanitize_config({"enabled": True})})
        self.assertFalse(self.sync.call_args.kwargs["shortcut_notice"])

    def test_strict_api_rejects_invalid_shortcuts_without_writing(self):
        for invalid in ([], ["A", "A"], ["A", "B", "X", "Y", "L3"], ["Unknown"], "L3+R3"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    control.action_set_virtual_trackpads({"config": {**sanitize_config({}), "shortcutButtons": invalid}})
        for invalid in (-1, 1, True, "3", 3.0):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    control.action_set_virtual_trackpads({"config": {**sanitize_config({}), "shortcutHoldSeconds": invalid}})
        self.assertFalse(self.config_path.exists())

    def test_unsupported_explicit_secondary_is_rejected_but_migrated_config_falls_back(self):
        config = sanitize_config({"screen": "secondary"})
        with self.assertRaisesRegex(ValueError, "secondary"):
            control.action_set_virtual_trackpads({"config": config})
        self.config_path.write_text(json.dumps(config))
        self.assertEqual(control.virtual_trackpads_config()["screen"], "primary")

    def test_supported_secondary_and_immediate_shortcut_are_persisted(self):
        with patch.object(control, "bottom_screen_supported", return_value=True):
            result = control.action_set_virtual_trackpads({"config": sanitize_config({
                "screen": "secondary", "shortcutButtons": ["Steam", "R3"], "shortcutHoldSeconds": 0,
            })})
        self.assertEqual(result["screen"], "secondary")
        self.assertEqual(result["shortcutHoldSeconds"], 0)

    def test_legacy_orientation_is_dropped_when_loading_and_saving(self):
        legacy = {**sanitize_config({}), "touchRotation": "right", "touchMirror": True}
        self.config_path.write_text(json.dumps(legacy))
        config = control.virtual_trackpads_config()
        self.assertNotIn("touchRotation", config)
        self.assertNotIn("touchMirror", config)
        control.action_set_virtual_trackpads({"config": config})
        self.assertEqual(json.loads(self.config_path.read_text()), config)

    def test_api_enforces_single_side_and_shortcut_preserves_mode(self):
        for mode, side in (("fullLeft", "left"), ("fullRight", "right")):
            with self.subTest(mode=mode):
                config = {**sanitize_config({"mode": mode}), "leftEnabled": False, "rightEnabled": False}
                saved = control.action_set_virtual_trackpads({"config": config})
                self.assertEqual(saved["leftEnabled"], side == "left")
                self.assertEqual(saved["rightEnabled"], side == "right")
                for enabled in (True, False, True):
                    toggled = control.action_toggle_virtual_trackpads({})
                    self.assertEqual(toggled["enabled"], enabled)
                    self.assertEqual(toggled["mode"], mode)
                    self.assertEqual(toggled["leftEnabled"], side == "left")
                    self.assertEqual(toggled["rightEnabled"], side == "right")

    def test_enabling_secondary_requires_its_game_mode_session_but_disabling_is_always_allowed(self):
        config = sanitize_config({"enabled": True, "screen": "secondary"})
        with patch.object(control, "bottom_screen_supported", return_value=True), patch.object(
            control, "game_mode_active", side_effect=lambda **kwargs: kwargs.get("screen") != "secondary"
        ):
            with self.assertRaisesRegex(RuntimeError, "enable the secondary screen"):
                control.action_set_virtual_trackpads({"config": config})
            self.assertFalse(self.config_path.exists())
            self.config_path.write_text(json.dumps(config))
            result = control.action_set_virtual_trackpads({"config": {**config, "enabled": False}})
            self.assertFalse(result["enabled"])


class ShortcutTests(unittest.TestCase):
    def test_axis_triggers_support_unsigned_and_signed_ranges(self):
        for minimum, maximum in ((0, 255), (-32768, 32767)):
            self.assertFalse(shortcut.trigger_down(minimum, minimum, maximum))
            self.assertTrue(shortcut.trigger_down(maximum, minimum, maximum))
        self.assertFalse(shortcut.trigger_down(0, 0, 0))

    def test_instant_chord_press_release_in_same_batch_is_not_lost(self):
        listener = shortcut.ShortcutListener.__new__(shortcut.ShortcutListener)
        listener.config = sanitize_config({"shortcutHoldSeconds": 0})
        device = Mock()
        device.read.return_value = [
            types.SimpleNamespace(type=1, code=317, value=1),
            types.SimpleNamespace(type=1, code=318, value=1),
            types.SimpleNamespace(type=1, code=317, value=0),
            types.SimpleNamespace(type=1, code=318, value=0),
        ]
        entry = {"device": device, "keys": set(), "axes": {}, "hold": ShortcutHold(0)}
        listener.devices = {"pad": entry}
        listener.read("pad")
        self.assertTrue(entry["pending"])
        self.assertEqual(entry["keys"], set())

    def test_two_controllers_cannot_complete_each_others_chord(self):
        listener = shortcut.ShortcutListener.__new__(shortcut.ShortcutListener)
        listener.config = sanitize_config({"shortcutHoldSeconds": 0})
        first = {"keys": {317}, "axes": {}, "hold": ShortcutHold(0)}
        second = {"keys": {318}, "axes": {}, "hold": ShortcutHold(0)}
        listener.update_hold(first)
        listener.update_hold(second)
        self.assertFalse(first.get("pending", False))
        self.assertFalse(second.get("pending", False))


class CaptureLifecycleTests(unittest.TestCase):
    def test_visible_pad_acquires_and_resumes_same_contact_on_reentry(self):
        pads = daemon.VirtualTrackpads.__new__(daemon.VirtualTrackpads)
        pads.config = sanitize_config({
            "enabled": True, "limitToBounds": True,
        })
        pads.device_env = {}
        pads.x_range, pads.y_range = (0, 1920), (0, 1080)
        pads.pixel_height, pads.aspect_ratio = 1080, 1920 / 1080
        pads.pad_slots, pads.press_releases = {}, {}
        pads.suspended_slots = set()
        pads.last_zones, pads.last_positions, pads.last_touches = {}, {}, {}
        pads.write_state, pads.ip = Mock(), Mock()
        pads.slots = {0: {"tracking": 7, "x": 960, "y": 540}}
        pads.update_slot(0)
        pads.ip.touch.assert_not_called()

        # Use the same rectangle as the overlay, then move the
        # held finger into it without a new touch-down event.
        x, y, width, height = trackpad_rect("left", "bottom", pads.config)
        center = {"x": x + width / 2, "y": y + height / 2}
        pads.slots[0].update(center)
        pads.update_slot(0)
        self.assertEqual(pads.ip.touch.call_args.args[:3], ("left", 0, True))
        self.assertAlmostEqual(pads.ip.touch.call_args.args[3], 0.5)
        self.assertAlmostEqual(pads.ip.touch.call_args.args[4], 0.5)
        self.assertEqual(pads.pad_slots[0][:2], ("left", "bottom"))

        pads.slots[0].update({"x": 960, "y": 540})
        pads.update_slot(0)
        self.assertEqual(pads.ip.touch.call_args.args[:3], ("left", 0, False))
        self.assertIn(0, pads.suspended_slots)
        self.assertTrue(pads.slots[0]["cancelTap"])
        pads.ip.touch.reset_mock()
        pads.update_slot(0)
        pads.ip.touch.assert_not_called()

        pads.slots[0].update(center)
        pads.update_slot(0)
        self.assertEqual(pads.ip.touch.call_args.args[:3], ("left", 0, True))
        self.assertAlmostEqual(pads.ip.touch.call_args.args[3], 0.5)
        self.assertAlmostEqual(pads.ip.touch.call_args.args[4], 0.5)
        self.assertNotIn(0, pads.suspended_slots)
        self.assertEqual(pads.slots[0]["tracking"], 7)

    def test_full_screen_routes_motion_across_center_and_taps_to_selected_pad(self):
        for mode, side in (("fullLeft", "left"), ("fullRight", "right")):
            with self.subTest(mode=mode):
                pads = daemon.VirtualTrackpads.__new__(daemon.VirtualTrackpads)
                pads.config = sanitize_config({"enabled": True, "mode": mode})
                pads.device_env = {}
                pads.x_range, pads.y_range = (0, 1920), (0, 1080)
                pads.pixel_height, pads.aspect_ratio = 1080, 1920 / 1080
                pads.pad_slots, pads.press_releases = {}, {}
                pads.suspended_slots = set()
                pads.last_zones, pads.last_positions, pads.last_touches = {}, {}, {}
                pads.write_state, pads.ip, pads.mouse_click = Mock(), Mock(), Mock()
                pads.slots = {0: {"tracking": 7, "x": 480, "y": 540}}
                pads.update_slot(0)
                self.assertEqual(pads.ip.touch.call_args.args, (side, 0, True, 0.25, 0.5))
                pads.slots[0]["x"] = 1440
                pads.update_slot(0)
                self.assertEqual(pads.ip.touch.call_args.args, (side, 0, True, 0.75, 0.5))
                self.assertEqual(pads.pad_slots[0][:2], (side, "full"))
                pads.release_slot(0)
                self.assertEqual(pads.ip.touch.call_args.args, (side, 0, False, 0.75, 0.5))
                pads.mouse_click.click.assert_not_called()
                # A stationary contact is still a click anywhere on the screen.
                pads.slots[0] = {"tracking": 8, "x": 960, "y": 270}
                pads.update_slot(0)
                pads.release_slot(0)
                pads.mouse_click.click.assert_called_once()
                self.assertEqual(pads.ip.touch.call_args.args, (side, 0, False, 0.5, 0.25))
                self.assertTrue(all(call.args[0] == side for call in pads.ip.touch.call_args_list))

    def test_720p_capture_uses_eight_physical_pixels_for_edge_gap(self):
        pads = daemon.VirtualTrackpads.__new__(daemon.VirtualTrackpads)
        pads.config = sanitize_config({"enabled": True, "edgeGap": 8})
        pads.device_env = {}
        pads.x_range, pads.y_range = (0, 1280), (0, 720)
        pads.pixel_height = 720
        pads.aspect_ratio = 1280 / 720
        pads.slots = {0: {"tracking": 1, "x": 7, "y": 650}}
        pads.pad_slots, pads.press_releases = {}, {}
        pads.suspended_slots = set()
        pads.last_zones, pads.last_positions, pads.last_touches = {}, {}, {}
        pads.write_state = Mock()
        pads.ip = Mock()
        pads.update_slot(0)
        pads.ip.touch.assert_not_called()
        pads.slots[0]["x"] = 9
        pads.update_slot(0)
        self.assertEqual(pads.ip.touch.call_args.args[:3], ("left", 0, True))
        self.assertAlmostEqual(pads.ip.touch.call_args.args[3], 1 / 252)
        # Continuing motion uses the same pixel geometry as the initial hit.
        pads.slots[0]["x"] = 10
        pads.update_slot(0)
        self.assertAlmostEqual(pads.ip.touch.call_args.args[3], 2 / 252)

    def test_disabled_main_allocates_no_input_or_uinput_resources(self):
        with patch.object(daemon, "load_config", return_value=sanitize_config({})), patch.object(
            daemon, "game_mode_active", return_value=True
        ), patch.object(daemon, "VirtualTrackpads") as pads:
            daemon.main()
        pads.assert_not_called()

    def test_secondary_selection_never_falls_back_to_primary_touchscreen(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_root, sysfs = root / "input", root / "sys"
            input_root.mkdir()
            for event, name in (("event0", "top_touchscreen"), ("event1", "bottom_touchscreen")):
                (input_root / event).touch()
                device = sysfs / event / "device"
                device.mkdir(parents=True)
                (device / "name").write_text(name)
            values = {"ARMADA_PRIMARY_TOUCHSCREEN": "top_touchscreen", "ARMADA_SECONDARY_TOUCHSCREEN": "bottom_touchscreen"}
            with patch.object(daemon, "is_touchscreen", return_value=True):
                self.assertEqual(daemon.find_touchscreen(values, "secondary", input_root, sysfs).name, "event1")
                (input_root / "event1").unlink()
                with self.assertRaisesRegex(RuntimeError, "secondary"):
                    daemon.find_touchscreen(values, "secondary", input_root, sysfs)

    def test_stopping_capture_releases_grab_contacts_and_haptic_ownership(self):
        pads = daemon.VirtualTrackpads.__new__(daemon.VirtualTrackpads)
        pads.fd = 12
        pads.ip = Mock()
        pads.pad_slots = {0: ("left", "bottom", 0.1, 0.9)}
        pads.suspended_slots = {0}
        pads.slots = {0: {}}
        pads.dirty_slots = {0}
        pads.press_releases = {}
        pads.write_state = Mock()
        with tempfile.TemporaryDirectory() as temporary:
            owner = Path(temporary) / "owner"
            owner.write_text("leased")
            with patch.object(daemon, "HAPTICS_OWNER_PATH", owner), patch.object(daemon.os, "close") as close:
                pads.close_device()
                close.assert_called_once_with(12)
            self.assertFalse(owner.exists())
        daemon.fcntl.ioctl.assert_called_with(12, daemon.EVIOCGRAB, 0)
        pads.ip.touch.assert_called_once_with("left", 0, False, 0.0, 0.0)
        self.assertIsNone(pads.fd)
        self.assertEqual(pads.pad_slots, {})
        self.assertEqual(pads.slots, {})
        self.assertEqual(pads.haptics_token, None)


if __name__ == "__main__":
    unittest.main()
