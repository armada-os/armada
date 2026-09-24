"""Touchscreen trackpad policy, type-B slot decoding, and frame-based gestures.

Kept independent of evdev so recorded input frames can be tested off-device.
"""
import math


DIRECT = ("direct", 1.0, True)


def settings_for_session(tweaks, state, pid_alive):
    from armada_game_tweaks import merged_settings

    session = state.get("override")
    if not isinstance(session, dict) or not pid_alive(session.get("pid")):
        return DIRECT
    settings = merged_settings(tweaks, session.get("appid"))
    if settings.get("touchscreenMode") != "trackpad":
        return DIRECT
    speed = settings.get("touchscreenSensitivity", 1.0)
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed):
        speed = 1.0
    return "trackpad", min(3.0, max(0.25, speed)), settings.get("touchscreenTapToClick") is not False


def orient_coordinates(x, y, orientation):
    # Panel orientation describes how the display is mounted. Input needs
    # the inverse transform to return to logical screen coordinates.
    if orientation == "left":
        return 1.0 - y, x
    if orientation == "right":
        return y, 1.0 - x
    if orientation == "inverted":
        return 1.0 - x, 1.0 - y
    return x, y


class Slots:
    # Linux input-event-codes.h, type-B multitouch protocol.
    SLOT, X, Y, TRACKING = 0x2f, 0x35, 0x36, 0x39

    def __init__(self, snapshot, current=0):
        self.values = {slot: dict(values) for slot, values in snapshot.items()}
        self.current = current

    def update(self, code, value):
        if code == self.SLOT:
            self.current = value
        elif code in (self.X, self.Y, self.TRACKING) and self.current in self.values:
            # Coordinates are slot state, even across contact lifetimes. The
            # kernel omits unchanged values on the next touch at the same spot.
            self.values[self.current][code] = value

    def contacts(self, transform):
        return {
            (slot, values[self.TRACKING]): transform(values[self.X], values[self.Y])
            for slot, values in self.values.items() if values[self.TRACKING] >= 0
        }


class TouchpadGestureEngine:
    """Consume complete frames {contact_id: (x, y)} with normalized coordinates.

    Sink implements move(dx, dy), scroll(steps), and button(name, pressed).
    Contact changes form a boundary: never move the pointer between fingers.
    """

    def __init__(self, sink, *, sensitivity=1.0, aspect=1.0, tap_to_click=True):
        self.sink = sink
        self.sensitivity = sensitivity
        self.aspect = aspect
        self.tap_to_click = tap_to_click
        self.dragging = False
        self.reset()

    def frame(self, contacts, now):
        previous = self.contacts
        if not previous and contacts:
            self.started = now
            self.starts = dict(contacts)
            self.max_contacts = 0
            self.moved = False
            self.remainder = [0.0, 0.0]
            self.scroll_remainder = 0.0
            if self.tap_to_click and len(contacts) == 1 and self.last_tap is not None:
                when, position = self.last_tap
                next_position = next(iter(contacts.values()))
                if now - when <= 0.35 and math.dist(position, next_position) <= 0.05:
                    self.dragging = True
                    self.sink.button("left", True)
            self.last_tap = None

        self.max_contacts = max(self.max_contacts, len(contacts))
        if self.dragging and len(contacts) > 1:
            self.sink.button("left", False)
            self.dragging = False
            self.moved = True
        for key, position in contacts.items():
            start = self.starts.setdefault(key, position)
            if math.dist(start, position) > 0.018:
                self.moved = True

        if contacts and contacts.keys() == previous.keys():
            if len(contacts) == 1 and self.max_contacts == 1:
                key = next(iter(contacts))
                for axis, scale in enumerate((1400, 1400 * self.aspect)):
                    self.remainder[axis] += (contacts[key][axis] - previous[key][axis]) * scale * self.sensitivity
                dx, dy = (math.trunc(value) for value in self.remainder)
                self.remainder[0] -= dx
                self.remainder[1] -= dy
                if dx or dy:
                    self.sink.move(dx, dy)
            elif len(contacts) == 2 and self.max_contacts == 2:
                # Average both fingers once per frame, independent of slot order.
                dy = sum(contacts[key][1] - previous[key][1] for key in contacts) / 2
                self.scroll_remainder -= dy * 40
                steps = math.trunc(self.scroll_remainder)
                self.scroll_remainder -= steps
                if steps:
                    self.moved = True
                    self.sink.scroll(steps)
        elif previous and contacts:
            self.remainder = [0.0, 0.0]
            self.scroll_remainder = 0.0
            # A replacement contact with no empty frame is not a tap/drag.
            if not contacts.keys() & previous.keys():
                self.moved = True
                if self.dragging:
                    self.sink.button("left", False)
                    self.dragging = False

        if previous and not contacts:
            if self.dragging:
                self.sink.button("left", False)
                self.dragging = False
            elif self.tap_to_click and not self.moved and now - self.started <= 0.25:
                if self.max_contacts == 1:
                    self.click("left")
                    self.last_tap = (now, next(iter(previous.values())))
                elif self.max_contacts == 2:
                    self.click("right")
        self.contacts = dict(contacts)

    def click(self, button):
        self.sink.button(button, True)
        self.sink.button(button, False)

    def reset(self):
        if self.dragging:
            self.sink.button("left", False)
        self.dragging = False
        self.last_tap = None
        self.contacts = {}
        self.starts = {}
        self.started = 0
        self.max_contacts = 0
        self.moved = False
        self.remainder = [0.0, 0.0]
        self.scroll_remainder = 0.0
