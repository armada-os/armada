#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -B - "$ROOT" <<'PY'
"""Focused input and profile regressions; hardware is mocked."""
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, call, patch

ROOT = Path(sys.argv.pop(1))
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
from touchscreen_trackpad import DIRECT, Slots, TouchpadGestureEngine, orient_coordinates, settings_for_session

C = types.SimpleNamespace(EV_SYN=0, EV_KEY=1, EV_REL=2, EV_ABS=3,
                         SYN_REPORT=0, SYN_DROPPED=3, REL_X=0, REL_Y=1,
                         REL_WHEEL=8, BTN_LEFT=272, BTN_RIGHT=273, BUS_VIRTUAL=6)
loader = importlib.machinery.SourceFileLoader("trackpad", str(ROOT / "system_files/usr/libexec/armada/touchscreen-trackpad"))
daemon = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
with patch.dict(sys.modules, evdev=types.SimpleNamespace(InputDevice=Mock(), UInput=Mock(), ecodes=C, list_devices=Mock())):
    loader.exec_module(daemon)


def slots(tracking=-1):
    return Slots({0: {Slots.TRACKING: tracking, Slots.X: 250, Slots.Y: 250}})


def event(kind, code, value=0, timestamp=1):
    return types.SimpleNamespace(type=kind, code=code, value=value, timestamp=lambda: timestamp)


class Gestures(unittest.TestCase):
    def test_gestures_with_tap_enabled_and_disabled(self):
        one = {0: (.25, .25)}
        two = {0: (.25, .25), 1: (.5, .25)}
        cases = [
            ("tap and drag", [(1, one), (1.1, {}), (1.2, one), (1.3, {0: (.5, .5)}), (1.5, {})],
             [call.button("left", True), call.button("left", False), call.button("left", True),
              call.move(350, 350), call.button("left", False)]),
            ("move and reposition", [(1, one), (1.1, {0: (.5, .25)}), (1.2, {}), (2, {1: (.9, .9)})],
             [call.move(350, 0)]),
            ("two-finger tap", [(1, one), (1.02, two), (1.1, {1: (.5, .25)}), (1.2, {})],
             [call.button("right", True), call.button("right", False)]),
            ("scroll and lift one finger", [(1, two), (1.1, {0: (.25, .5), 1: (.5, .5)}),
                                            (1.15, {1: (.5, .75)}), (1.2, {})], [call.scroll(-10)]),
            ("second finger suppresses movement", [(1, one), (1.1, {0: (.75, .25), 1: (.5, .25)})], []),
            ("three fingers do not click", [(1, {**two, 2: (.75, .25)}), (1.1, {})], []),
            ("long press does not click", [(1, one), (3, {})], []),
            ("replacement contact does not jump", [(1, {(0, 123): (.25, .25)}),
                                                   (1.1, {(0, 124): (.75, .75)}), (1.2, {})], []),
        ]
        for name, frames, expected in cases:
            for tap_enabled in (True, False):
                with self.subTest(gesture=name, tap=tap_enabled):
                    sink = Mock()
                    engine = TouchpadGestureEngine(sink, tap_to_click=tap_enabled)
                    for now, contacts in frames:
                        engine.frame(contacts, now)
                    wanted = expected if tap_enabled else [e for e in expected if e[0] != "button"]
                    self.assertEqual(sink.method_calls, wanted)

    def test_reset_releases_drag_and_cancels_tap(self):
        sink = Mock()
        engine = TouchpadGestureEngine(sink)
        for now, contacts in [(1, {0: (.25, .25)}), (1.1, {}), (1.2, {0: (.25, .25)})]:
            engine.frame(contacts, now)
        sink.reset_mock()
        engine.reset()
        engine.frame({}, 1.3)
        self.assertEqual(sink.method_calls, [call.button("left", False)])

    def test_rotation_and_fractional_motion(self):
        for orientation, expected in {"normal": (.25, .75), "left": (.25, .25),
                                      "right": (.75, .75), "inverted": (.75, .25)}.items():
            self.assertEqual(orient_coordinates(.25, .75, orientation), expected)
        sink = Mock()
        engine = TouchpadGestureEngine(sink)
        # RP6: right decreases raw Y; up decreases raw X.
        for now, point in enumerate([(.5, .5), (.5, .25), (.25, .25)]):
            engine.frame({0: orient_coordinates(*point, "left")}, now)
        self.assertEqual(sink.method_calls, [call.move(350, 0), call.move(0, -350)])
        sink.reset_mock()
        engine = TouchpadGestureEngine(sink, sensitivity=2)
        for i in range(11):
            engine.frame({0: (i / 10000, 0)}, i / 100)
        self.assertEqual(sum(c.args[0] for c in sink.move.call_args_list), 2)


class Profiles(unittest.TestCase):
    def test_profile_resolution(self):
        state = {"override": {"appid": "42", "pid": 100}}
        defaults = {"touchscreenMode": "trackpad", "touchscreenSensitivity": 1.5, "touchscreenTapToClick": False}
        cases = [
            ("idle", {}, {}, True, DIRECT),
            ("exited", state, {}, False, DIRECT),
            ("inherited", state, {}, True, ("trackpad", 1.5, False)),
            ("direct override", state, {"touchscreenMode": "direct"}, True, DIRECT),
            ("game controls", state, {"touchscreenSensitivity": 2, "touchscreenTapToClick": True}, True, ("trackpad", 2, True)),
            ("disabled profile", state, {"enabled": False, "touchscreenMode": "direct"}, True, ("trackpad", 1.5, False)),
        ]
        for name, session, game, alive, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(settings_for_session({"global": defaults, "games": {"42": game}}, session, lambda _: alive), expected)
        for speed, expected in [(None, 1), (True, 1), ("bad", 1), (float("nan"), 1), (float("inf"), 1), (-100, .25), (100, 3)]:
            with self.subTest(speed=speed):
                tweaks = {"global": {**defaults, "touchscreenSensitivity": speed}}
                self.assertEqual(settings_for_session(tweaks, state, lambda _: True), ("trackpad", expected, False))


class Capture(unittest.TestCase):
    def mock(self, owner, name, **kwargs):
        patcher = patch.object(owner, name, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def setUp(self):
        self.device = Mock(path="/dev/input/event0", fd=7)
        self.device.name = "test panel"
        self.device.absinfo.return_value = types.SimpleNamespace(min=0, max=1000)
        self.virtual = self.mock(daemon, "UInput").return_value
        self.snapshot = self.mock(daemon, "snapshot", side_effect=lambda _: slots())
        self.mock(daemon.fcntl, "ioctl")
        self.settings = self.mock(daemon, "configured_settings", return_value=DIRECT)
        self.ready = self.mock(daemon.select, "select", return_value=([], [], []))
        self.mock(daemon, "suspend_clock_offset", return_value=0)

    def run_trackpad(self):
        daemon.run_trackpad(self.device, "normal", ("trackpad", 1, True))

    def test_support_probe_never_grabs_input(self):
        self.mock(daemon, "device_environment", return_value={})
        self.mock(daemon.signal, "signal")
        find = self.mock(daemon, "find_touchscreen")
        with patch.object(sys, "argv", ["touchscreen-trackpad", "--supported"]):
            for device, expected in [(None, 1), (self.device, 0)]:
                find.return_value = device
                self.assertEqual(daemon.main(), expected)
        self.device.close.assert_called_once()
        self.device.grab.assert_not_called()
        self.virtual.write.assert_not_called()

    def test_slot_reuse_keeps_unchanged_coordinates(self):
        state = slots()
        for code, value in [(Slots.TRACKING, 10), (Slots.X, 300), (Slots.TRACKING, -1), (Slots.TRACKING, 11)]:
            state.update(code, value)
        self.assertEqual(state.contacts(lambda x, y: (x, y)), {(0, 11): (300, 250)})

    def test_waits_for_fingers_before_capture(self):
        self.snapshot.side_effect = lambda _: slots(1)
        self.run_trackpad()
        self.device.grab.assert_not_called()

    def test_mode_change_releases_capture(self):
        self.run_trackpad()
        self.device.grab.assert_called_once()
        self.device.ungrab.assert_called_once()
        self.virtual.close.assert_called_once()

    def test_failed_grab_preserves_other_owner(self):
        self.device.grab.side_effect = OSError("busy")
        with self.assertRaises(OSError):
            self.run_trackpad()
        self.device.ungrab.assert_not_called()
        self.virtual.close.assert_called_once()

    def test_dropped_events_resync_and_discard_incomplete_gesture(self):
        self.snapshot.side_effect = [slots(), slots(), slots(7)]
        self.ready.side_effect = [([], [], []), ([self.device], [], []), ([], [], []), OSError("unplugged")]
        self.settings.return_value = ("trackpad", 1, True)
        self.device.read.return_value = [event(C.EV_SYN, C.SYN_DROPPED), event(C.EV_ABS, Slots.X, 900),
                                        event(C.EV_SYN, C.SYN_REPORT), event(C.EV_ABS, Slots.TRACKING, -1)]
        with self.assertRaises(OSError):
            self.run_trackpad()
        self.assertEqual(self.snapshot.call_count, 3)
        self.virtual.write.assert_not_called()
        self.device.ungrab.assert_called_once()
        self.virtual.close.assert_called_once()

    def test_settings_change_releases_drag(self):
        for next_settings in (DIRECT, ("trackpad", 1, False), ("trackpad", 2, True)):
            with self.subTest(settings=next_settings):
                self.virtual.reset_mock()
                self.device.read.return_value = [
                    event(C.EV_ABS, Slots.TRACKING, 1), event(C.EV_SYN, C.SYN_REPORT, timestamp=1),
                    event(C.EV_ABS, Slots.TRACKING, -1), event(C.EV_SYN, C.SYN_REPORT, timestamp=1.1),
                    event(C.EV_ABS, Slots.TRACKING, 2), event(C.EV_SYN, C.SYN_REPORT, timestamp=1.2),
                ]
                self.ready.side_effect = [([], [], []), ([self.device], [], [])]
                self.settings.side_effect = [("trackpad", 1, True), next_settings]
                with patch.object(daemon.time, "monotonic", side_effect=[0, daemon.POLL_SECONDS]):
                    self.run_trackpad()
                self.assertEqual(self.virtual.write.call_args_list, [
                    call(C.EV_KEY, C.BTN_LEFT, 1), call(C.EV_KEY, C.BTN_LEFT, 0),
                    call(C.EV_KEY, C.BTN_LEFT, 1), call(C.EV_KEY, C.BTN_LEFT, 0),
                ])
                self.virtual.close.assert_called_once()

    def test_resume_resets_gestures(self):
        engine = self.mock(daemon, "TouchpadGestureEngine").return_value
        self.mock(daemon, "suspend_clock_offset", side_effect=[0, 10])
        self.settings.side_effect = [("trackpad", 1, True), DIRECT]
        with patch.object(daemon.time, "monotonic", side_effect=[0, daemon.POLL_SECONDS]):
            self.run_trackpad()
        self.assertEqual(engine.reset.call_count, 2)  # resume and final release

    def test_primary_selection_never_captures_secondary_or_ambiguous_panels(self):
        for names, primary, secondary, expected in [
            (["one", "two"], "", "", None),
            (["bottom"], "top", "bottom", None),
            (["bottom", "top"], "top", "bottom", 1),
        ]:
            with self.subTest(names=names):
                devices = [Mock() for _ in names]
                for device, name in zip(devices, names):
                    device.name = name
                    device.capabilities.return_value = {C.EV_ABS: [Slots.SLOT, Slots.X, Slots.Y, Slots.TRACKING]}
                with patch.object(daemon, "list_devices", return_value=names), \
                     patch.object(daemon, "InputDevice", side_effect=devices), \
                     patch.object(daemon.subprocess, "check_output", return_value="ID_INPUT_TOUCHSCREEN=1\n"):
                    selected = daemon.find_touchscreen(primary, secondary)
                self.assertIs(selected, devices[expected] if expected is not None else None)
                for device in devices:
                    self.assertEqual(device.close.call_count, 0 if device is selected else 1)


unittest.main()
PY
