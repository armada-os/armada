"""Gesture state machine for Armada's touchscreen trackpad mode."""

from dataclasses import dataclass
import math


def orient_coordinates(x, y, orientation):
    """Rotate native-panel coordinates into the displayed orientation."""
    if orientation == "left":
        return y, 1.0 - x
    if orientation == "right":
        return 1.0 - y, x
    if orientation == "inverted":
        return 1.0 - x, 1.0 - y
    return x, y


@dataclass
class Contact:
    start_x: float
    start_y: float
    x: float
    y: float


class TouchpadGestureEngine:
    """Translate normalized touch contacts into relative mouse gestures.

    The sink must provide ``move(dx, dy)`` and ``button(name, pressed)``.
    Coordinates passed to this class are normalized to the range 0..1.
    """

    def __init__(
        self,
        sink,
        *,
        motion_counts=1400,
        tap_seconds=0.25,
        double_tap_seconds=0.35,
        tap_move_threshold=0.018,
    ):
        self.sink = sink
        self.motion_counts = motion_counts
        self.tap_seconds = tap_seconds
        self.double_tap_seconds = double_tap_seconds
        self.tap_move_threshold = tap_move_threshold
        self.contacts = {}
        self.session_started = None
        self.session_max_contacts = 0
        self.session_moved = False
        self.last_single_tap = None
        self.dragging = False
        self.x_remainder = 0.0
        self.y_remainder = 0.0

    def touch_down(self, slot, x, y, timestamp):
        if slot in self.contacts:
            return
        if not self.contacts:
            self.session_started = timestamp
            self.session_max_contacts = 0
            self.session_moved = False
            if (
                self.last_single_tap is not None
                and timestamp - self.last_single_tap <= self.double_tap_seconds
            ):
                self.dragging = True
                self.last_single_tap = None
                self.sink.button("left", True)
            elif self.last_single_tap is not None:
                self.last_single_tap = None
        self.contacts[slot] = Contact(x, y, x, y)
        self.session_max_contacts = max(self.session_max_contacts, len(self.contacts))

    def touch_move(self, slot, x, y, timestamp):
        del timestamp
        contact = self.contacts.get(slot)
        if contact is None:
            return
        dx = x - contact.x
        dy = y - contact.y
        contact.x = x
        contact.y = y
        if math.hypot(x - contact.start_x, y - contact.start_y) > self.tap_move_threshold:
            self.session_moved = True
        if len(self.contacts) != 1:
            return
        self.x_remainder += dx * self.motion_counts
        self.y_remainder += dy * self.motion_counts
        move_x = math.trunc(self.x_remainder)
        move_y = math.trunc(self.y_remainder)
        self.x_remainder -= move_x
        self.y_remainder -= move_y
        if move_x or move_y:
            self.sink.move(move_x, move_y)

    def touch_up(self, slot, timestamp):
        if self.contacts.pop(slot, None) is None or self.contacts:
            return
        if self.dragging:
            self.sink.button("left", False)
            self.dragging = False
            self._finish_session()
            return
        duration = timestamp - self.session_started if self.session_started is not None else 0
        if duration <= self.tap_seconds and not self.session_moved:
            if self.session_max_contacts == 1:
                self._click("left")
                self.last_single_tap = timestamp
            elif self.session_max_contacts >= 2:
                self._click("right")
                self.last_single_tap = None
        else:
            self.last_single_tap = None
        self._finish_session()

    def reset(self):
        if self.dragging:
            self.sink.button("left", False)
        self.contacts.clear()
        self.dragging = False
        self.last_single_tap = None
        self.x_remainder = 0.0
        self.y_remainder = 0.0
        self._finish_session()

    def _click(self, name):
        self.sink.button(name, True)
        self.sink.button(name, False)

    def _finish_session(self):
        self.session_started = None
        self.session_max_contacts = 0
        self.session_moved = False
