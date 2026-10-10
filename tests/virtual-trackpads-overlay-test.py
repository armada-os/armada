#!/usr/bin/python3
"""Run the real GTK overlay against an authenticated disposable X11 display.

Linux dependencies: Xvfb, xauth, GTK 4, PyGObject with Cairo integration, and
Pycairo. Run directly with python3; the parent process deliberately never
imports GTK, so each worker exercises initialization from a clean process.
"""

import ctypes
import json
import os
from pathlib import Path
import runpy
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "system_files/usr/lib/armada"
OVERLAY = ROOT / "system_files/usr/libexec/armada/virtual-trackpads-overlay"
TITLE = b"Armada Virtual Trackpads Overlay"


class X11Probe:
    """Inspect actual mapped windows without importing GTK in the test driver."""

    def __init__(self, display):
        self.lib = ctypes.CDLL("libX11.so.6")
        pointer = ctypes.c_void_p
        ulong = ctypes.c_ulong
        self.lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.lib.XOpenDisplay.restype = pointer
        self.lib.XCloseDisplay.argtypes = [pointer]
        self.lib.XDefaultRootWindow.argtypes = [pointer]
        self.lib.XDefaultRootWindow.restype = ulong
        self.lib.XQueryTree.argtypes = [
            pointer, ulong, ctypes.POINTER(ulong), ctypes.POINTER(ulong),
            ctypes.POINTER(ctypes.POINTER(ulong)), ctypes.POINTER(ctypes.c_uint),
        ]
        self.lib.XFetchName.argtypes = [pointer, ulong, ctypes.POINTER(ctypes.c_char_p)]
        self.lib.XFree.argtypes = [pointer]
        self.lib.XInternAtom.argtypes = [pointer, ctypes.c_char_p, ctypes.c_int]
        self.lib.XInternAtom.restype = ulong
        self.lib.XGetWindowProperty.argtypes = [
            pointer, ulong, ulong, ctypes.c_long, ctypes.c_long, ctypes.c_int,
            ulong, ctypes.POINTER(ulong), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ulong), ctypes.POINTER(ulong),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
        ]
        self.lib.XChangeProperty.argtypes = [
            pointer, ulong, ulong, ulong, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int,
        ]
        self.lib.XDeleteProperty.argtypes = [pointer, ulong, ulong]
        self.lib.XSync.argtypes = [pointer, ctypes.c_int]
        self.display = self.lib.XOpenDisplay(display.encode())
        if not self.display:
            raise RuntimeError(f"Cannot connect to test X server {display}")

    def close(self):
        if self.display:
            self.lib.XCloseDisplay(self.display)
            self.display = None

    def named_window(self):
        root, parent = ctypes.c_ulong(), ctypes.c_ulong()
        children = ctypes.POINTER(ctypes.c_ulong)()
        count = ctypes.c_uint()
        self.lib.XQueryTree(
            self.display, self.lib.XDefaultRootWindow(self.display),
            ctypes.byref(root), ctypes.byref(parent), ctypes.byref(children),
            ctypes.byref(count),
        )
        try:
            for index in range(count.value):
                name = ctypes.c_char_p()
                self.lib.XFetchName(self.display, children[index], ctypes.byref(name))
                try:
                    if name.value == TITLE:
                        return children[index]
                finally:
                    if name:
                        self.lib.XFree(name)
        finally:
            if children:
                self.lib.XFree(children)
        return None

    def cardinal(self, window, property_name):
        atom = self.lib.XInternAtom(self.display, property_name.encode(), False)
        kind, count, remaining = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
        bits = ctypes.c_int()
        data = ctypes.POINTER(ctypes.c_ubyte)()
        result = self.lib.XGetWindowProperty(
            self.display, window, atom, 0, 1, False, 6, ctypes.byref(kind),
            ctypes.byref(bits), ctypes.byref(count), ctypes.byref(remaining),
            ctypes.byref(data),
        )
        try:
            if result != 0 or kind.value != 6 or bits.value != 32 or count.value != 1:
                return None
            return ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))[0]
        finally:
            if data:
                self.lib.XFree(data)

    def set_server_id(self, server_id):
        atom = self.lib.XInternAtom(self.display, b"GAMESCOPE_XWAYLAND_SERVER_ID", False)
        root = self.lib.XDefaultRootWindow(self.display)
        if server_id is None:
            self.lib.XDeleteProperty(self.display, root, atom)
        else:
            value = ctypes.c_ulong(server_id)
            self.lib.XChangeProperty(
                self.display, root, atom, 6, 32, 0,
                ctypes.cast(ctypes.byref(value), ctypes.POINTER(ctypes.c_ubyte)), 1,
            )
        self.lib.XSync(self.display, False)


def render_worker(directory):
    """Verify real draw callbacks, alpha output, hide/fade, and split-screen."""
    assert "DISPLAY" not in os.environ
    assert "XAUTHORITY" not in os.environ
    sys.path.insert(0, str(LIBRARY))
    from armada_overlay_session import discover_gamescope_environment

    display = discover_gamescope_environment()
    assert display == os.environ["ARMADA_TEST_DISPLAY"], display
    assert os.environ.get("XAUTHORITY") == os.environ["ARMADA_TEST_AUTHORITY"]
    namespace = runpy.run_path(str(OVERLAY), run_name="overlay_under_test")
    import cairo
    import gi

    gi.require_version("Gsk", "4.0")
    from gi.repository import Gtk, GLib

    assert Gtk.init_check()
    directory = Path(directory)
    config_path, state_path = directory / "config.json", directory / "state.json"
    notice_path = directory / "notice.json"
    runtime = namespace["TrackpadOverlay"].tick.__globals__
    runtime["CONFIG_PATH"], runtime["STATE_PATH"] = config_path, state_path
    runtime["NOTICE_PATH"] = notice_path
    app = namespace["TrackpadOverlay"]()
    app.set_application_id(None)
    config = {
        "enabled": True, "leftEnabled": True, "rightEnabled": True,
        "mode": "simple",
        "leftSize": 35, "rightSize": 35, "borderOpacity": 100,
        "backgroundOpacity": 100, "dotSize": 3,
        "centerDotEnabled": False,
    }
    state = {"leftActive": True, "rightActive": True,
             "leftZone": "bottom", "rightZone": "bottom"}
    config_path.write_text(json.dumps(config))
    state_path.write_text(json.dumps(state))
    drawn = []
    original_draw = app.draw

    def record_draw(*args):
        drawn.append(time.monotonic())
        return original_draw(*args)

    app.draw = record_draw
    errors = []
    started = time.monotonic()
    phase = 0
    phase_started = started
    last_frames = 0
    pixels = {}
    paintable = None
    last_surface = None
    # Saved manual corrections from older builds must no longer move pads.
    legacy_layouts = [("right", False), ("upside_down", False),
                      ("left", False), ("normal", False), ("normal", True)]
    legacy_index = 0

    def alpha_pixels(label):
        nonlocal last_surface
        # Render the widget's real GTK render node, rather than calling the
        # Python draw function directly (which would miss callback failures).
        snapshot = Gtk.Snapshot()
        paintable.snapshot(snapshot, app.width, app.height)
        node = snapshot.to_node()
        image_path = directory / f"{label}.png"
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, app.width, app.height)
        if node is not None:
            # Replay GTK's existing render node into an independent target.
            # Keep capture independent of the live GdkSurface and its frame
            # production; never unrealize a renderer attached to that surface.
            node.draw(cairo.Context(surface))
        surface.flush()
        last_surface = surface
        surface.write_to_png(str(image_path))
        data = surface.get_data()
        alpha_offset = 3 if sys.byteorder == "little" else 0
        visible = sum(
            data[y * surface.get_stride() + x * 4 + alpha_offset] != 0
            for y in range(surface.get_height())
            for x in range(surface.get_width())
        )
        print(json.dumps({"phase": label, "alphaPixels": visible,
                          "draws": len(drawn), "fade": app.fade,
                          "mode": app.config.get("mode"),
                          "enabled": app.config.get("enabled")}), flush=True)
        return visible

    def alpha_at(x, y):
        data = last_surface.get_data()
        offset = int(y) * last_surface.get_stride() + int(x) * 4
        return data[offset + (3 if sys.byteorder == "little" else 0)]

    def corner_alpha():
        inset = 8 + app.height * 0.35 / 2
        return {"top-left": alpha_at(inset, inset),
                "top-right": alpha_at(app.width - inset, inset),
                "bottom-left": alpha_at(inset, app.height - inset),
                "bottom-right": alpha_at(app.width - inset, app.height - inset)}

    def publish_notice(enabled):
        now = time.time()
        notice_path.write_text(json.dumps({"enabled": enabled, "created": now,
                                          "expires": now + 2, "screen": "primary"}))

    def assert_chip(label):
        # Text must sit on an opaque-enough rounded background, including the
        # empty padding surrounding it (not merely appear as floating glyphs).
        pixels[label] = alpha_pixels(label)
        y = max(16, app.height * 0.045) + 5
        assert alpha_at(app.width / 2, y) > 150, f"Missing chip background: {label}"

    def check():
        nonlocal phase, phase_started, last_frames, paintable, legacy_index
        now = time.monotonic()
        try:
            assert now - started < 16, "Overlay did not complete rendering phases"
            if app.window is None or not app.window.get_mapped():
                return GLib.SOURCE_CONTINUE
            if paintable is None:
                # Keep this observer alive across GTK frames. Constructing a
                # fresh paintable during queue_draw can capture a temporarily
                # invalidated (NULL) widget render node instead of the last
                # completed frame. Its asynchronous image updates remove that
                # race while still exercising the real GTK render pipeline.
                paintable = Gtk.WidgetPaintable.new(app.window)
                phase_started = now
                return GLib.SOURCE_CONTINUE
            if phase == 0 and now - phase_started >= 0.65:
                assert len(drawn) >= 2, "GTK never invoked the Cairo draw callback"
                probe = X11Probe(display)
                try:
                    window = probe.named_window()
                    assert window, "Overlay has no X11 window"
                    assert probe.cardinal(window, "ARMADA_VIRTUAL_TRACKPADS_OVERLAY") == 1
                finally:
                    probe.close()
                pixels["active"] = alpha_pixels("active")
                assert pixels["active"] > 100, pixels
                # No center marker: after release + hold + fade, all alpha
                # must disappear while the mapped overlay remains running.
                state.update(leftActive=False, rightActive=False)
                state_path.write_text(json.dumps(state))
                last_frames = len(drawn)
                phase, phase_started = 1, now
            elif phase == 1 and now - phase_started >= 1.6:
                assert len(drawn) > last_frames, "Fade did not repaint"
                pixels["faded"] = alpha_pixels("faded")
                assert pixels["faded"] == 0, pixels
                state.update(leftActive=True, rightActive=True)
                state_path.write_text(json.dumps(state))
                phase, phase_started = 3, now
            elif phase == 3 and now - phase_started >= 0.5:
                pixels["reactivated"] = alpha_pixels("reactivated")
                assert pixels["reactivated"] > 100, pixels
                config.update(enabled=True, autoHide=False, backgroundStyle="solid",
                              borderWidth=10, borderOpacity=0, backgroundOpacity=50)
                state.update(leftActive=False, rightActive=False)
                config_path.write_text(json.dumps(config))
                state_path.write_text(json.dumps(state))
                phase, phase_started = 4, now
            elif phase == 4 and now - phase_started >= 0.5:
                pixels["solid"] = alpha_pixels("solid")
                assert pixels["solid"] > 1000, pixels
                config.update(backgroundStyle="none", backgroundOpacity=0)
                config_path.write_text(json.dumps(config))
                phase, phase_started = 5, now
            elif phase == 5 and now - phase_started >= 0.4:
                pixels["none"] = alpha_pixels("none")
                assert pixels["none"] == 0, pixels
                config.update(backgroundStyle="solid", backgroundOpacity=50,
                              rightEnabled=False, touchRotation=legacy_layouts[0][0])
                config_path.write_text(json.dumps(config))
                phase, phase_started = 6, now
            elif phase == 6 and now - phase_started >= 0.35:
                rotation, mirror = legacy_layouts[legacy_index]
                corner = "bottom-left"
                alpha_pixels(f"legacy-rotation-{rotation}-mirror-{mirror}")
                corners = corner_alpha()
                assert corners[corner] > 0, (rotation, mirror, corners)
                assert all(value == 0 for key, value in corners.items() if key != corner), corners
                legacy_index += 1
                if legacy_index < len(legacy_layouts):
                    config.update(touchRotation=legacy_layouts[legacy_index][0],
                                  touchMirror=legacy_layouts[legacy_index][1])
                    config_path.write_text(json.dumps(config))
                    phase_started = now
                else:
                    publish_notice(True)
                    phase, phase_started = 7, now
            elif phase == 7 and now - phase_started >= 0.35:
                assert_chip("shortcut-enabled")
                publish_notice(False)
                config["enabled"] = False
                config_path.write_text(json.dumps(config))
                phase, phase_started = 8, now
            elif phase == 8 and now - phase_started >= 0.35:
                assert_chip("shortcut-disabled")
                assert not any(corner_alpha().values()), "Disabled notice kept pads visible"
                phase, phase_started = 9, now
            elif phase == 9:
                assert now - phase_started < 2.5, "Notice-only overlay did not stop at expiry"
        except BaseException as error:
            errors.append(error)
            app.quit()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    GLib.timeout_add(50, check)
    app.run(None)
    if errors:
        raise errors[0]
    assert phase == 9, f"Overlay exited prematurely at phase {phase}"


class OverlayHeadlessTests(unittest.TestCase):
    def test_screen_modes_and_disabled_pads_exit_without_graphics(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            environment = dict(os.environ,
                               PYTHONPATH=str(LIBRARY),
                               ARMADA_DEVICE_ENV=str(Path(directory) / "no-device-env"),
                               ARMADA_VIRTUAL_TRACKPADS_CONFIG_PATH=str(config_path),
                               ARMADA_VIRTUAL_TRACKPADS_NOTICE_PATH=str(Path(directory) / "no-notice"))
            for key in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY"):
                environment.pop(key, None)
            for config in ({"enabled": False}, *(
                {"enabled": True, "mode": mode, "centerDotEnabled": True, "autoHide": False}
                for mode in ("halves", "fullLeft", "fullRight")
            )):
                with self.subTest(config=config):
                    config_path.write_text(json.dumps(config))
                    result = subprocess.run([sys.executable, str(OVERLAY)], env=environment,
                                            capture_output=True, text=True, timeout=3)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertNotIn("using", result.stdout)


class OverlaySessionSelectionTests(unittest.TestCase):
    def test_copied_secondary_config_normalizes_only_without_hardware(self):
        sys.path.insert(0, str(LIBRARY))
        from armada_overlay_session import screen_for_device

        self.assertEqual(screen_for_device("secondary", {}), "primary")
        self.assertEqual(screen_for_device("secondary", {"ARMADA_SECONDARY_CONNECTOR": "DSI-1"}), "primary")
        self.assertEqual(screen_for_device("secondary", {"ARMADA_SECONDARY_TOUCHSCREEN": "bottom_touchscreen"}), "primary")
        dual = {"ARMADA_SECONDARY_CONNECTOR": "DSI-1", "ARMADA_SECONDARY_TOUCHSCREEN": "bottom_touchscreen"}
        # Hardware selection stays secondary without any session/socket data.
        self.assertEqual(screen_for_device("secondary", dual), "secondary")
        self.assertEqual(screen_for_device("primary", dual), "primary")

    def test_screen_selection_never_falls_back_to_other_compositor(self):
        sys.path.insert(0, str(LIBRARY))
        import armada_overlay_session as session

        primary = {"DISPLAY": ":20", "GAMESCOPE_WAYLAND_DISPLAY": "gamescope-primary"}
        secondary = {"DISPLAY": ":40", "GAMESCOPE_WAYLAND_DISPLAY": "gamescope-secondary"}
        with mock.patch.object(session, "steam_environments", return_value=[primary]) as steam, \
                mock.patch.object(session, "secondary_environments", return_value=[secondary]) as bottom, \
                mock.patch.object(session, "xwayland_authorities", return_value={}), \
                mock.patch.object(session, "can_open_x11", return_value=True):
            self.assertEqual(session.discover_gamescope_environment(screen="secondary"), ":40")
            steam.assert_not_called()
            bottom.assert_called_once()
            steam.reset_mock()
            bottom.reset_mock()
            self.assertEqual(session.discover_gamescope_environment(screen="primary"), ":20")
            steam.assert_called_once()
            bottom.assert_not_called()

        with mock.patch.object(session, "steam_environments", return_value=[primary]) as steam, \
                mock.patch.object(session, "secondary_environments", return_value=[]), \
                mock.patch.object(session, "xwayland_authorities", return_value={}):
            with self.assertRaisesRegex(RuntimeError, "Secondary"):
                session.discover_gamescope_environment(timeout=0.01, screen="secondary")
            steam.assert_not_called()

    def test_secondary_requires_live_ready_socket(self):
        sys.path.insert(0, str(LIBRARY))
        import armada_overlay_session as session

        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(session.subprocess, "check_output") as runner:
            (Path(directory) / "armada-bottom-env").write_text("DISPLAY=:40\n")
            self.assertEqual(session.secondary_environments(directory), [])
            runner.assert_not_called()


class OverlayRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for executable in ("Xvfb", "xauth", "bash"):
            if not shutil.which(executable):
                raise RuntimeError(f"Required runtime test dependency is missing: {executable}")
        cls.directory = tempfile.TemporaryDirectory(prefix="armada-overlay-test-")
        cls.addClassCleanup(cls.directory.cleanup)
        cls.authority = Path(cls.directory.name) / "Xauthority"
        cls.config_path = Path(cls.directory.name) / "service-config.json"
        cls.notice_path = Path(cls.directory.name) / "service-notice.json"
        cls.dual_device_env = Path(cls.directory.name) / "dual-device-env"
        cls.dual_device_env.write_text(
            "#!/bin/sh\nprintf '%s\\n' ARMADA_SECONDARY_CONNECTOR=DSI-1 "
            "ARMADA_SECONDARY_TOUCHSCREEN=bottom_touchscreen\n"
        )
        cls.dual_device_env.chmod(0o700)
        number = 200 + os.getpid() % 10000
        while Path(f"/tmp/.X11-unix/X{number}").exists() or Path(f"/tmp/.X{number}-lock").exists():
            number += 1
        cls.display = f":{number}"
        subprocess.run(
            ["xauth", "-f", str(cls.authority), "add", cls.display,
             "MIT-MAGIC-COOKIE-1", secrets.token_hex(16)],
            check=True, capture_output=True, text=True,
        )
        # A pipe can fill with repeated X11 diagnostics and freeze the server,
        # which would make otherwise bounded tests hang inside XOpenDisplay.
        cls.xvfb_log = (Path(cls.directory.name) / "xvfb.log").open("w+b")
        cls.addClassCleanup(cls.xvfb_log.close)
        cls.xvfb = subprocess.Popen(
            ["Xvfb", cls.display, "-noreset", "-screen", "0", "800x450x24", "-nolisten", "tcp",
             "-auth", str(cls.authority)], stdout=cls.xvfb_log, stderr=subprocess.STDOUT,
        )
        cls.addClassCleanup(cls.stop_process, cls.xvfb)
        deadline = time.monotonic() + 5
        while not Path(f"/tmp/.X11-unix/X{number}").exists():
            if cls.xvfb.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("Disposable X server failed to start")
            time.sleep(0.02)
        steam_environment = dict(os.environ, DISPLAY=cls.display,
                                 XAUTHORITY=str(cls.authority),
                                 GAMESCOPE_WAYLAND_DISPLAY="armada-test-gamescope-0")
        cls.steam = subprocess.Popen(
            ["bash", "-c", "exec -a steam sleep 60"], env=steam_environment,
        )
        cls.addClassCleanup(cls.stop_process, cls.steam)
        # The driver uses Xlib only. Workers below explicitly remove these
        # variables and must obtain them from the running Steam fixture.
        cls.previous_authority = os.environ.get("XAUTHORITY")
        os.environ["XAUTHORITY"] = str(cls.authority)
        cls.addClassCleanup(cls.restore_authority)
        probe = X11Probe(cls.display)
        try:
            probe.set_server_id(0)
        finally:
            probe.close()

    @classmethod
    def restore_authority(cls):
        if cls.previous_authority is None:
            os.environ.pop("XAUTHORITY", None)
        else:
            os.environ["XAUTHORITY"] = cls.previous_authority

    @staticmethod
    def stop_process(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    def environment(self):
        environment = dict(os.environ)
        for name in ("DISPLAY", "XAUTHORITY", "GAMESCOPE_WAYLAND_DISPLAY", "WAYLAND_DISPLAY"):
            environment.pop(name, None)
        environment.update(
            PYTHONPATH=str(LIBRARY), GDK_BACKEND="x11", GSK_RENDERER="cairo",
            GTK_A11Y="none", NO_AT_BRIDGE="1", GSETTINGS_BACKEND="memory",
            ARMADA_TEST_DISPLAY=self.display,
            ARMADA_TEST_AUTHORITY=str(self.authority),
            ARMADA_DEVICE_ENV="/nonexistent-armada-test-device-env",
            ARMADA_VIRTUAL_TRACKPADS_CONFIG_PATH=str(self.config_path),
            ARMADA_VIRTUAL_TRACKPADS_NOTICE_PATH=str(self.notice_path),
        )
        return environment

    def setUp(self):
        self.config_path.write_text(json.dumps({"enabled": True, "screen": "primary"}))
        self.notice_path.unlink(missing_ok=True)

    def assert_no_render_errors(self, output):
        for failure in ("Traceback", "Gtk couldn't be initialized", "GDK_IS_DISPLAY",
                        "Couldn't find foreign struct converter", "TypeError"):
            self.assertNotIn(failure, output)

    def test_bootstrap_from_service_without_display(self):
        process = subprocess.Popen(
            [sys.executable, str(OVERLAY)], env=self.environment(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        probe = X11Probe(self.display)
        window = None
        try:
            deadline = time.monotonic() + 8
            while process.poll() is None and time.monotonic() < deadline:
                window = probe.named_window()
                if window and probe.cardinal(window, "ARMADA_VIRTUAL_TRACKPADS_OVERLAY") == 1:
                    break
                time.sleep(0.05)
            alive = process.poll() is None
            marked = bool(window and probe.cardinal(window, "ARMADA_VIRTUAL_TRACKPADS_OVERLAY") == 1)
        finally:
            probe.close()
            if process.poll() is None:
                process.terminate()
            output, errors = process.communicate(timeout=3)
        self.assertTrue(alive and marked, output + errors)
        self.assert_no_render_errors(output + errors)

    def test_disabled_service_exits_without_graphics(self):
        for config in ({"enabled": False}, *(
            {"enabled": True, "mode": mode, "centerDotEnabled": True}
            for mode in ("halves", "fullLeft", "fullRight")
        )):
            with self.subTest(config=config):
                self.config_path.write_text(json.dumps(config))
                result = subprocess.run(
                    [sys.executable, str(OVERLAY)], env=self.environment(),
                    capture_output=True, text=True, timeout=3,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("using", result.stdout)
                self.assert_no_render_errors(result.stdout + result.stderr)

    def test_disabled_shortcut_notice_bootstraps_and_exits(self):
        for config in ({"enabled": False}, *(
            {"enabled": True, "mode": mode} for mode in ("halves", "fullLeft", "fullRight")
        )):
            with self.subTest(config=config):
                self.config_path.write_text(json.dumps(config))
                now = time.time()
                self.notice_path.write_text(json.dumps({"enabled": config["enabled"], "created": now,
                                                       "expires": now + 2, "screen": "primary"}))
                result = subprocess.run(
                    [sys.executable, str(OVERLAY)], env=self.environment(),
                    capture_output=True, text=True, timeout=5,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("first GTK/Cairo frame rendered", result.stdout)
                self.assert_no_render_errors(result.stdout + result.stderr)

    def test_screen_change_stops_old_overlay(self):
        process = subprocess.Popen(
            [sys.executable, str(OVERLAY)],
            env=dict(self.environment(), ARMADA_DEVICE_ENV=str(self.dual_device_env)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        probe = X11Probe(self.display)
        try:
            deadline = time.monotonic() + 8
            while not probe.named_window() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertIsNotNone(probe.named_window())
            self.config_path.write_text(json.dumps({"enabled": True, "screen": "secondary"}))
            output, errors = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, output + errors)
            self.assertIsNone(probe.named_window(), "Old screen kept its overlay after selection changed")
        finally:
            probe.close()
            self.stop_process(process)

    def test_secondary_uses_its_own_gamescope_display(self):
        number = int(self.display[1:]) + 1
        while Path(f"/tmp/.X11-unix/X{number}").exists() or Path(f"/tmp/.X{number}-lock").exists():
            number += 1
        secondary_display = f":{number}"
        subprocess.run(
            ["xauth", "-f", str(self.authority), "add", secondary_display,
             "MIT-MAGIC-COOKIE-1", secrets.token_hex(16)],
            check=True, capture_output=True, text=True,
        )
        server = subprocess.Popen(
            ["Xvfb", secondary_display, "-noreset", "-screen", "0", "640x480x24", "-nolisten", "tcp",
             "-auth", str(self.authority)], stdout=self.xvfb_log, stderr=subprocess.STDOUT,
        )
        self.addCleanup(self.stop_process, server)
        deadline = time.monotonic() + 5
        while not Path(f"/tmp/.X11-unix/X{number}").exists():
            if server.poll() is not None or time.monotonic() >= deadline:
                self.fail("Secondary X server failed to start")
            time.sleep(0.02)
        secondary_probe, primary_probe = X11Probe(secondary_display), X11Probe(self.display)
        self.addCleanup(secondary_probe.close)
        self.addCleanup(primary_probe.close)
        secondary_probe.set_server_id(0)

        runtime = Path(self.directory.name) / "secondary-runtime"
        runtime.mkdir()
        endpoint = socket.socket(socket.AF_UNIX)
        self.addCleanup(endpoint.close)
        endpoint.bind(str(runtime / "gamescope-secondary"))
        (runtime / "armada-bottom-env").write_text(
            f"DISPLAY={shlex.quote(secondary_display)}\n"
            f"XAUTHORITY={shlex.quote(str(self.authority))}\n"
            "GAMESCOPE_WAYLAND_DISPLAY=gamescope-secondary\n"
        )
        # Copy through text mode so this fixture also works from Windows checkouts.
        runner = runtime / "armada-run-bottom"
        runner.write_text((ROOT / "system_files/usr/bin/armada-run-bottom").read_text())
        runner.chmod(0o700)
        self.config_path.write_text(json.dumps({"enabled": True, "screen": "secondary"}))
        environment = dict(self.environment(), ARMADA_TEST_RUNTIME=str(runtime),
                           ARMADA_TEST_BOTTOM_RUNNER=str(runner),
                           ARMADA_DEVICE_ENV=str(self.dual_device_env))
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--secondary-worker"], env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            deadline = time.monotonic() + 8
            while not secondary_probe.named_window() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            secondary_window = secondary_probe.named_window()
            primary_window = primary_probe.named_window()
        finally:
            process.terminate()
            output, errors = process.communicate(timeout=3)
        self.assertIsNotNone(secondary_window, output + errors)
        self.assertIsNone(primary_window, "Secondary overlay appeared on the primary screen")
        self.assertIn(f"using secondary display {secondary_display}", output)
        self.assert_no_render_errors(output + errors)

    def test_real_gtk_drawing_and_transparency(self):
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--render-worker", self.directory.name],
                env=self.environment(), capture_output=True, text=True, timeout=22,
            )
        finally:
            output_directory = os.environ.get("ARMADA_OVERLAY_TEST_OUTPUT")
            if output_directory:
                destination = Path(output_directory)
                destination.mkdir(parents=True, exist_ok=True)
                for screenshot in Path(self.directory.name).glob("*.png"):
                    shutil.copyfile(screenshot, destination / screenshot.name)
        print(result.stdout, end="", flush=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_no_render_errors(result.stdout + result.stderr)
        self.assertIn('"alphaPixels"', result.stdout)

    def test_reject_isolated_game_and_non_gamescope_displays(self):
        sys.path.insert(0, str(LIBRARY))
        from armada_overlay_session import can_open_x11

        probe = X11Probe(self.display)
        try:
            probe.set_server_id(None)
            self.assertFalse(can_open_x11(self.display, str(self.authority)))
            probe.set_server_id(1)
            self.assertFalse(can_open_x11(self.display, str(self.authority)))
            probe.set_server_id(0)
            self.assertTrue(can_open_x11(self.display, str(self.authority)))
        finally:
            probe.set_server_id(0)
            probe.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--render-worker":
        render_worker(sys.argv[2])
    elif len(sys.argv) > 1 and sys.argv[1] == "--secondary-worker":
        sys.path.insert(0, str(LIBRARY))
        import armada_overlay_session as session

        secondary_environments = session.secondary_environments
        session.secondary_environments = lambda: secondary_environments(
            runtime_root=os.environ["ARMADA_TEST_RUNTIME"],
            runner=os.environ["ARMADA_TEST_BOTTOM_RUNNER"],
        )
        runpy.run_path(str(OVERLAY), run_name="__main__")
    else:
        unittest.main(verbosity=2)
