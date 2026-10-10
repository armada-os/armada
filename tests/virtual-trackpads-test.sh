#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ARMADA_TEST_ROOT="$ROOT" PYTHONPATH="$ROOT/system_files/usr/lib/armada" python3 - <<'PYEOF'
import ast
import os
import socket
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from armada_virtual_trackpads import DEFAULT_CONFIG, SHORTCUT_BUTTONS, ShortcutHold, display_dimensions, game_mode_active, panel_aspect_ratio, point_in_trackpad_bounds, rotate_touch, sanitize_config, should_capture_touch, trackpad_at, trackpad_coordinates, trackpad_rect, transform_touch

config = sanitize_config({
    "enabled": True,
    "blockTouchscreen": False,
    "leftEnabled": True,
    "rightEnabled": True,
    "mode": "corners",
    "tapToClick": True,
    "limitToBounds": True,
    "leftSize": 35,
    "rightSize": 40,
    "hapticStrength": 500,
    "borderOpacity": -4,
    "backgroundOpacity": 45,
})
assert config["hapticStrength"] == 100
assert config["borderOpacity"] == 0
assert config["backgroundOpacity"] == 45
assert sanitize_config({"borderOpacity": 100, "backgroundOpacity": 100, "centerDotOpacity": 100})["borderOpacity"] == 50
assert sanitize_config({"borderOpacity": 100, "backgroundOpacity": 100, "centerDotOpacity": 100})["backgroundOpacity"] == 50
assert sanitize_config({"borderOpacity": 100, "backgroundOpacity": 100, "centerDotOpacity": 100})["centerDotOpacity"] == 50
assert sanitize_config({"borderWidth": 99})["borderWidth"] == 10
assert sanitize_config({"backgroundStyle": "solid"})["backgroundStyle"] == "solid"
assert sanitize_config({"backgroundStyle": "none"})["backgroundStyle"] == "none"
assert sanitize_config({"backgroundStyle": "bad"})["backgroundStyle"] == "dots"
assert sanitize_config({"hideDelay": 99})["hideDelay"] == 5
assert sanitize_config({"gameModeOnly": True})["gameModeOnly"] is True
assert sanitize_config({})["enabled"] is False
assert not should_capture_touch(sanitize_config({}), True)
assert {key: DEFAULT_CONFIG[key] for key in (
    "enabled", "blockTouchscreen", "gameModeOnly", "leftEnabled", "rightEnabled",
    "mode", "edgeGap", "limitToBounds", "hapticStrength",
    "shortcutEnabled", "shortcutButtons", "shortcutHoldSeconds", "screen",
    "autoHide", "hideDelay", "borderWidth", "borderOpacity", "borderRadius",
    "backgroundStyle", "dotSize", "dotGap", "backgroundOpacity", "centerDotEnabled",
)} == {
    "enabled": False, "blockTouchscreen": False, "gameModeOnly": True,
    "leftEnabled": True, "rightEnabled": True, "mode": "simple",
    "edgeGap": 8, "limitToBounds": True,
    "shortcutEnabled": True, "shortcutButtons": ["L3", "R3"], "shortcutHoldSeconds": 3,
    "screen": "primary",
    "hapticStrength": 60, "autoHide": True, "hideDelay": 1,
    "borderWidth": 2, "borderOpacity": 30, "borderRadius": 24,
    "backgroundStyle": "dots", "dotSize": 1, "dotGap": 4,
    "backgroundOpacity": 30, "centerDotEnabled": False,
}
fallback_source = Path(os.environ["ARMADA_TEST_ROOT"]) / "decky/armada-control/py_modules/armada_control/trackpads.py"
fallback = next(ast.literal_eval(node.value) for node in ast.parse(fallback_source.read_text()).body
                if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "DEFAULT" for target in node.targets))
assert fallback == {"supported": False, "secondaryAvailable": False, **DEFAULT_CONFIG}
only_game = sanitize_config({"enabled": True, "leftEnabled": True, "gameModeOnly": True})
assert not should_capture_touch(only_game, False)
assert should_capture_touch(only_game, True)
assert should_capture_touch({**only_game, "gameModeOnly": False}, False)
assert not should_capture_touch({**only_game, "enabled": False, "blockTouchscreen": True}, False)
assert should_capture_touch({**only_game, "enabled": False, "blockTouchscreen": True}, True)
assert sanitize_config({"borderColor": "#ff0000"}).get("borderColor") is None
assert sanitize_config({"leftEnabled": 1})["leftEnabled"] is True
assert sanitize_config({"enabled": False, "leftEnabled": True})["enabled"] is False
assert sanitize_config({"leftEnabled": True})["enabled"] is True
assert sanitize_config({"blockTouchscreen": True})["blockTouchscreen"] is True
assert sanitize_config({"enabled": True, "blockTouchscreen": True})["enabled"] is False
assert sanitize_config({"tapToClick": False})["tapToClick"] is True
assert set(config) == set(DEFAULT_CONFIG)
assert "fixedBottom" not in DEFAULT_CONFIG
assert "deckLikeSize" not in DEFAULT_CONFIG
assert sanitize_config({"deckLikeSize": True, "leftSize": 38})["leftSize"] == 38
assert sanitize_config({"shortcutHoldSeconds": 0})["shortcutHoldSeconds"] == 0
for invalid in (True, False, 1, -1, "3", 3.0):
    assert sanitize_config({"shortcutHoldSeconds": invalid})["shortcutHoldSeconds"] == 3
for invalid in ([], ["L3", "L3"], ["Unknown"], ["A", "B", "X", "Y", "L3"], "L3+R3"):
    assert sanitize_config({"shortcutButtons": invalid})["shortcutButtons"] == ["L3", "R3"]
assert sanitize_config({"shortcutButtons": ["Steam", "R3"]})["shortcutButtons"] == ["Steam", "R3"]
copy = sanitize_config({})
copy["shortcutButtons"].append("A")
assert DEFAULT_CONFIG["shortcutButtons"] == ["L3", "R3"]
assert sanitize_config({"screen": "secondary", "touchRotation": "upside_down", "touchMirror": True})["screen"] == "secondary"
assert sanitize_config({"screen": "invalid", "touchRotation": "invalid"})["screen"] == "primary"
assert "touchRotation" not in sanitize_config({"touchRotation": "right"})
assert "touchMirror" not in sanitize_config({"touchMirror": True})
with tempfile.TemporaryDirectory() as directory:
    runtime = Path(directory)
    user_runtime = runtime / str(os.getuid())
    user_runtime.mkdir()
    with patch("armada_virtual_trackpads.pwd.getpwnam", return_value=SimpleNamespace(pw_uid=os.getuid())):
        assert not game_mode_active(runtime_root=runtime)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as gamescope:
            gamescope.bind(str(user_runtime / "gamescope-test"))
            (user_runtime / "gamescope-primary").symlink_to("gamescope-test")
            assert game_mode_active(runtime_root=runtime)
            assert not game_mode_active(runtime_root=runtime, screen="secondary")
            (user_runtime / "gamescope-secondary").symlink_to("gamescope-test")
            assert game_mode_active(runtime_root=runtime, screen="secondary")
            (user_runtime / "gamescope-primary").unlink()
            assert not game_mode_active(runtime_root=runtime)
            assert game_mode_active(runtime_root=runtime, screen="secondary")
with tempfile.TemporaryDirectory() as directory:
    drm = Path(directory)
    primary, secondary = drm / "card0-DSI-2", drm / "card0-DSI-1"
    primary.mkdir()
    secondary.mkdir()
    (primary / "modes").write_text("1080x1920\n")
    (secondary / "modes").write_text("960x1280\n")
    device = {"ARMADA_PRIMARY_CONNECTOR": "DSI-2", "ARMADA_SECONDARY_CONNECTOR": "DSI-1"}
    assert display_dimensions(device, "primary", drm) == (1920, 1080)
    assert panel_aspect_ratio(device, "secondary", drm) == 4 / 3
    # A missing selected display must never use the other display's dimensions.
    (secondary / "modes").unlink()
    assert display_dimensions(device, "secondary", drm) == (1920, 1080)
assert sanitize_config({"leftSize": 100})["leftSize"] == 80
hold = ShortcutHold(3.0)
hold.update(True, False, 0.0)
assert not hold.ready(10.0)
hold.update(True, True, 10.0)
assert not hold.ready(12.99)
assert hold.ready(13.0)
assert not hold.ready(20.0)
hold.update(False, True, 20.1)
hold.update(True, True, 21.0)
assert hold.ready(24.0)
instant = ShortcutHold(0)
instant.update_pressed({"Steam"}, {"Steam", "R3"}, 1.0)
assert not instant.ready(1.0)
instant.update_pressed({"Steam", "R3"}, {"Steam", "R3"}, 2.0)
assert instant.ready(2.0)
assert not instant.ready(3.0)
instant.update_pressed(set(), {"Steam", "R3"}, 3.1)
instant.update_pressed({"Steam", "R3"}, {"Steam", "R3"}, 4.0)
assert instant.ready(4.0)

assert rotate_touch(0.25, 0.75, "left") == (0.75, 0.75)
assert rotate_touch(0.25, 0.75, "right") == (0.25, 0.25)
assert rotate_touch(0.25, 0.75, "normal") == (0.25, 0.75)
# Match the compositor's inverse scanout transform: RP6 panel left maps
# raw top-left to visible top-right, without a second device-specific quirk.
assert transform_touch(0, 0, {"ARMADA_PANEL_ORIENTATION": "left"}, config) == (1, 0)
assert transform_touch(0, 0, {"ARMADA_PANEL_ORIENTATION": "right"}, config) == (0, 1)
assert transform_touch(0.2, 0.3, {}, config) == (0.2, 0.3)
assert transform_touch(0, 0, {"ARMADA_PANEL_ORIENTATION": "upside_down"}, config) == (1, 1)
# Old manual settings must not rotate the geometry or override panel metadata.
for rotation in ("normal", "right", "upside_down", "left"):
    migrated = sanitize_config({**config, "touchRotation": rotation, "touchMirror": True})
    assert migrated == config
    assert transform_touch(0, 0, {"ARMADA_PANEL_ORIENTATION": "left"}, migrated) == (1, 0)

# 35% high square in a 16:9 viewport occupies 19.6875% of its width.
left = trackpad_at(0.05, 0.9, config)
right = trackpad_at(0.95, 0.9, config)
assert left and left[0] == "left"
assert right and right[0] == "right"
assert trackpad_at(0.5, 0.5, config) is None
assert all(0 <= value <= 1 for value in left[1:] + right[1:])

only_left = {**config, "rightEnabled": False}
assert trackpad_at(0.95, 0.9, only_left) is None

from armada_virtual_trackpads import trackpad_zone_at
top_left = trackpad_zone_at(0.05, 0.1, config)
bottom_left = trackpad_zone_at(0.05, 0.9, config)
top_right = trackpad_zone_at(0.95, 0.1, config)
bottom_right = trackpad_zone_at(0.95, 0.9, config)
assert top_left and top_left[:2] == ("left", "top")
assert bottom_left and bottom_left[:2] == ("left", "bottom")
assert top_right and top_right[:2] == ("right", "top")
assert bottom_right and bottom_right[:2] == ("right", "bottom")
simple = {**config, "mode": "simple"}
assert trackpad_zone_at(0.05, 0.1, simple) is None
assert trackpad_zone_at(0.05, 0.9, simple)[:2] == ("left", "bottom")
assert trackpad_zone_at(0.2, 0.9, {**simple, "leftSize": 66}, 3 / 2)[:2] == ("left", "bottom")
assert trackpad_zone_at(0.05, 0.9, {**simple, "enabled": False}) is None

floating = {**config, "mode": "floating"}
assert trackpad_zone_at(0.45, 0.42, floating) == ("left", "floating", 0.5, 0.5)
assert trackpad_zone_at(0.55, 0.68, floating) == ("right", "floating", 0.5, 0.5)

halves = {**config, "mode": "halves"}
assert trackpad_zone_at(0.25, 0.4, halves) == ("left", "half", 0.5, 0.4)
assert trackpad_zone_at(0.75, 0.6, halves) == ("right", "half", 0.5, 0.6)
assert trackpad_coordinates(0.3, 0.4, "left", "half", halves) == (0.6, 0.4)
right_half = trackpad_coordinates(0.8, 0.6, "right", "half", halves)
assert abs(right_half[0] - 0.6) < 1e-9 and right_half[1] == 0.6
floating_center = trackpad_coordinates(0.25, 0.5, "left", "floating", floating, 0.25, 0.5)
assert floating_center == (0.5, 0.5)
floating_move = trackpad_coordinates(0.27, 0.53, "left", "floating", floating, 0.25, 0.5)
assert floating_move[0] > 0.5 and floating_move[1] > 0.5
assert point_in_trackpad_bounds(0.26, 0.52, "left", "floating", floating, 0.25, 0.5)
assert not point_in_trackpad_bounds(0.49, 0.52, "left", "floating", floating, 0.25, 0.5)
assert point_in_trackpad_bounds(0.05, 0.9, "left", "bottom", simple)
assert not point_in_trackpad_bounds(0.3, 0.9, "left", "bottom", simple)

# Input boundaries and local pad positions must match the overlay's pixel
# rectangles on both primary and secondary screens, regardless of resolution.
for pixel_width, pixel_height in ((1280, 720), (1280, 960), (1920, 1080)):
    aspect = pixel_width / pixel_height
    geometry = {**simple, "edgeGap": 80, "leftSize": 35, "rightSize": 35}
    size = pixel_height * 0.35
    for side in ("left", "right"):
        origin_x = 80 if side == "left" else pixel_width - 80 - size
        for zone in ("top", "bottom"):
            origin_y = 80 if zone == "top" else pixel_height - 80 - size
            x = (origin_x + size / 2) / pixel_width
            y = (origin_y + size / 2) / pixel_height
            corners = {**geometry, "mode": "corners"}
            hit = trackpad_zone_at(x, y, corners, aspect, pixel_height)
            assert hit[:2] == (side, zone)
            local = trackpad_coordinates(x, y, side, zone, corners, aspect_ratio=aspect, pixel_height=pixel_height)
            assert all(abs(value - 0.5) < 1e-9 for value in local)
            assert point_in_trackpad_bounds(x, y, side, zone, corners, aspect_ratio=aspect, pixel_height=pixel_height)
            # One pixel beyond the visible left edge must not be captured.
            outside_x = (origin_x - 1) / pixel_width
            assert not point_in_trackpad_bounds(outside_x, y, side, zone, corners, aspect_ratio=aspect, pixel_height=pixel_height)
            assert trackpad_zone_at(outside_x, y, corners, aspect, pixel_height) is None
            if zone == "bottom":
                assert trackpad_at(x, y, geometry, aspect, pixel_height)[0] == side

# A single screen-wide pad spans both halves continuously, including all edges,
# irrespective of old zone toggles, visual settings, size or selected resolution.
for mode, side in (("fullLeft", "left"), ("fullRight", "right")):
    full = sanitize_config({**config, "mode": mode, "leftEnabled": False, "rightEnabled": False})
    assert full["leftEnabled"] is (side == "left")
    assert full["rightEnabled"] is (side == "right")
    assert should_capture_touch(full, True)
    assert not should_capture_touch({**full, "enabled": False}, True)
    for pixel_width, pixel_height in ((1920, 1080), (1280, 960)):
        aspect = pixel_width / pixel_height
        assert trackpad_rect(side, "full", full, aspect_ratio=aspect, pixel_height=pixel_height) == (0, 0, pixel_width, pixel_height)
        for x, y in ((0, 0), (1, 0), (0, 1), (1, 1), (0.25, 0.3), (0.49, 0.5), (0.5, 0.5), (0.51, 0.5), (0.75, 0.7)):
            assert trackpad_zone_at(x, y, full, aspect, pixel_height) == (side, "full", x, y)
            assert trackpad_coordinates(x, y, side, "full", full, aspect_ratio=aspect, pixel_height=pixel_height) == (x, y)
            assert point_in_trackpad_bounds(x, y, side, "full", full)
            assert trackpad_zone_at(x, y, {**full, "enabled": False}) is None
        for x, y in ((-0.01, 0.5), (1.01, 0.5), (0.5, -0.01), (0.5, 1.01)):
            assert trackpad_zone_at(x, y, full) is None
            assert not point_in_trackpad_bounds(x, y, side, "full", full)
    split = sanitize_config({**full, "mode": "halves"})
    assert split["leftEnabled"] and split["rightEnabled"]
    assert trackpad_zone_at(0.25, 0.5, split) == ("left", "half", 0.5, 0.5)
    assert trackpad_zone_at(0.75, 0.5, split) == ("right", "half", 0.5, 0.5)

# Floating input still matches the rendered square at different resolutions.
for pixel_width, pixel_height in ((1920, 1080), (1280, 960)):
    for side, anchor_x in (("left", 0.25), ("right", 0.75)):
        aspect = pixel_width / pixel_height
        x, y, width, height = trackpad_rect(side, "floating", floating, anchor_x, 0.5, aspect, pixel_height)
        assert abs(width - height) < 1e-8
        center = (x + width / 2) / pixel_width, (y + height / 2) / pixel_height
        assert trackpad_zone_at(*center, floating, aspect, pixel_height) == (side, "floating", 0.5, 0.5)
        local = trackpad_coordinates(*center, side, "floating", floating, anchor_x, 0.5, aspect, pixel_height)
        assert all(abs(value - 0.5) < 1e-8 for value in local)

print("Virtual trackpad geometry and configuration tests passed")
PYEOF

# Rendering lives in the native GTK overlay; the runtime overlay tests cover
# repainting, background modes, fading, invisible screen modes, and shortcut notices.
grep -Fq 'radius = min(width, height) / 2.0 * clamp(float(self.config.get("borderRadius", 28)) / 100.0)' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads-overlay"
grep -Fq 'context.arc(x + base_x, y + base_y, dot_size / 2.0, 0, math.tau)' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads-overlay"
grep -Fq 'hold_seconds = float(self.config.get("hideDelay", 1))' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads-overlay"
grep -Fq 'if background == "dots":' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads-overlay"
grep -Fq 'game_mode_active' "$ROOT/system_files/usr/lib/armada/armada_virtual_trackpads.py"
grep -Fq 'if not overlay_enabled(self.config) or self.config.get("mode") in SCREEN_MODES:' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads-overlay"
grep -Fq '{ id: "Trackpads", title: tabIcons.Trackpads' "$ROOT/decky/armada-control/src/Content.tsx"
! grep -Fq '<Trackpads config={config} setConfig={setConfig} />' "$ROOT/decky/armada-control/src/tabs/Settings.tsx"
grep -Fq 'fcntl.ioctl(fd, EVIOCGRAB, 1)' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads"
grep -Fq 'Touchpad:{side.title()}Pad:Motion' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads"
grep -Fq 'Touchpad:{side.title()}Pad:Button:Press' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads"
! grep -Fq 'Touchpad:{side.title()}Pad:Touch:' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads"
grep -Fq '.write_send_event(NativeEvent::new(cap, value))' "$ROOT/packages/inputplumber/patches/0005-add-dbus-touch-events.patch"
! grep -Fq 'blocking_write_send_event(NativeEvent::new(cap, value))' "$ROOT/packages/inputplumber/patches/0005-add-dbus-touch-events.patch"
! grep -Fq '.blocking_write_send_event(event)' "$ROOT/packages/inputplumber/patches/0005-add-dbus-touch-events.patch"
grep -Fq 'className="armada-trackpads-tab"' "$ROOT/decky/armada-control/src/tabs/Trackpads.tsx"
grep -Fq 'ARMADA_VIRTUAL_TRACKPADS_OVERLAY' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads-overlay"
grep -Fq 'XFixesSetWindowShapeRegion' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads-overlay"
! grep -Fq 'b"STEAM_OVERLAY"' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads-overlay"
grep -Fq 'preview_until' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads-overlay"
grep -Fq 'GAMESCOPE_WAYLAND_DISPLAY' "$ROOT/system_files/usr/lib/armada/armada_overlay_session.py"
grep -Fq 'def xwayland_authorities(' "$ROOT/system_files/usr/lib/armada/armada_overlay_session.py"
grep -Fq 'if not can_open_x11(display, authority)' "$ROOT/system_files/usr/lib/armada/armada_overlay_session.py"
grep -Fq 'gi.require_version("Gdk", "4.0")' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads-overlay"
grep -Fq 'class MouseClickSink' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads"
grep -Fq 'ecodes.BTN_LEFT' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads"
grep -Fq 'self.mouse_click.click()' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads"
grep -Fq 'get_virtual_trackpads' "$ROOT/decky/armada-control/main.py"
grep -Fq 'reset_virtual_trackpads' "$ROOT/decky/armada-control/main.py"
grep -Fq '"reset_virtual_trackpads": action_reset_virtual_trackpads' "$ROOT/system_files/usr/libexec/armada/armada-control"
grep -Fq 'trackpads.resetDefaults' "$ROOT/decky/armada-control/src/tabs/Trackpads.tsx"
grep -Fq 'python3-evdev' "$ROOT/build_files/10-base-packages.sh"
grep -Fq 'self.ip.press(side, True)' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads"
grep -Fq 'self.press_releases[side] = {' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads"
grep -Fq 'pending["index"]' "$ROOT/system_files/usr/libexec/armada/virtual-trackpads"
! grep -Fq 'fixedBottom' "$ROOT/decky/armada-control/src/tabs/Trackpads.tsx"
grep -Fq 'ARMADA_OVERLAY_PROP' "$ROOT/packages/gamescope/patches/0028-steamcompmgr-armada-virtual-trackpad-overlay.patch"
grep -Fq 'w->isExternalOverlay || w->isArmadaOverlay' "$ROOT/packages/gamescope/patches/0028-steamcompmgr-armada-virtual-trackpad-overlay.patch"
grep -Fq 'pPaintFocus->armadaOverlayWindow && pPaintFocus->armadaOverlayWindow->opacity' "$ROOT/packages/gamescope/patches/0028-steamcompmgr-armada-virtual-trackpad-overlay.patch"
python3 "$ROOT/tests/virtual-trackpads-haptics-test.py"
python3 "$ROOT/tests/virtual-trackpads-lifecycle-test.py"
