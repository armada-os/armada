#!/usr/bin/env python3
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
from touchscreen_trackpad import TouchpadGestureEngine, orient_coordinates


class Sink:
    def __init__(self):
        self.events = []

    def move(self, dx, dy):
        self.events.append(("move", dx, dy))

    def button(self, name, pressed):
        self.events.append(("button", name, pressed))


class TouchpadGestureEngineTest(unittest.TestCase):
    def setUp(self):
        self.sink = Sink()
        self.engine = TouchpadGestureEngine(self.sink, motion_counts=1000)

    def test_single_finger_tap_left_clicks(self):
        self.engine.touch_down(0, 0.5, 0.5, 1.0)
        self.engine.touch_up(0, 1.1)
        self.assertEqual(
            self.sink.events,
            [("button", "left", True), ("button", "left", False)],
        )

    def test_two_finger_tap_right_clicks(self):
        self.engine.touch_down(0, 0.4, 0.5, 1.0)
        self.engine.touch_down(1, 0.6, 0.5, 1.02)
        self.engine.touch_up(0, 1.1)
        self.engine.touch_up(1, 1.12)
        self.assertEqual(
            self.sink.events,
            [("button", "right", True), ("button", "right", False)],
        )

    def test_dragging_moves_relatively_without_clicking(self):
        self.engine.touch_down(0, 0.2, 0.2, 1.0)
        self.engine.touch_move(0, 0.3, 0.25, 1.1)
        self.engine.touch_up(0, 1.4)
        self.assertEqual(self.sink.events, [("move", 99, 49)])

    def test_double_tap_and_hold_drags(self):
        self.engine.touch_down(0, 0.2, 0.2, 1.0)
        self.engine.touch_up(0, 1.1)
        self.engine.touch_down(0, 0.2, 0.2, 1.25)
        self.engine.touch_move(0, 0.3, 0.2, 1.35)
        self.engine.touch_up(0, 1.5)
        self.assertEqual(
            self.sink.events,
            [
                ("button", "left", True),
                ("button", "left", False),
                ("button", "left", True),
                ("move", 99, 0),
                ("button", "left", False),
            ],
        )

    def test_reset_releases_a_held_drag(self):
        self.engine.touch_down(0, 0.2, 0.2, 1.0)
        self.engine.touch_up(0, 1.1)
        self.engine.touch_down(0, 0.2, 0.2, 1.2)
        self.engine.reset()
        self.assertEqual(self.sink.events[-1], ("button", "left", False))

    def test_panel_orientation_matches_display_rotation(self):
        expected = {
            "normal": (0.2, 0.7),
            "left": (0.7, 0.8),
            "right": (0.3, 0.2),
            "inverted": (0.8, 0.3),
        }
        for orientation, coordinates in expected.items():
            actual = orient_coordinates(0.2, 0.7, orientation)
            self.assertAlmostEqual(actual[0], coordinates[0])
            self.assertAlmostEqual(actual[1], coordinates[1])


if __name__ == "__main__":
    unittest.main()
