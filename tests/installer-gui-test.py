#!/usr/bin/python3
"""Exercise the touch size picker with GTK under a disposable X server."""
import os
from pathlib import Path
import runpy
import select
import shutil
import tempfile
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
i = runpy.run_path(str(ROOT / "system_files/usr/libexec/armada/armada-installer"))


class PickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.framebuffer = tempfile.TemporaryDirectory()
        cls.display = subprocess.Popen(["Xvfb", ":99", "-screen", "0", "800x600x24", "-nolisten", "tcp", "-fbdir", cls.framebuffer.name])
        deadline = time.monotonic() + 5
        while not Path("/tmp/.X11-unix/X99").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        os.environ["DISPLAY"] = ":99"
        os.environ["GSK_RENDERER"] = "cairo"
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gio, GLib, Gtk
        cls.Adw = Adw
        cls.Gio, cls.GLib, cls.Gtk = Gio, GLib, Gtk

    @classmethod
    def tearDownClass(cls):
        cls.display.terminate()
        cls.display.wait()
        cls.framebuffer.cleanup()

    def widgets(self, root):
        yield root
        child = root.get_first_child()
        while child is not None:
            yield from self.widgets(child)
            child = child.get_next_sibling()

    def drive(self, action):
        app = self.Gio.Application.get_default()
        window = app.get_active_window()
        widgets = list(self.widgets(window))
        slider = next(w for w in widgets if isinstance(w, self.Gtk.Scale))
        buttons = {(w.get_child().get_icon_name() if isinstance(w.get_child(), self.Gtk.Image) else w.get_label()): w
                   for w in widgets if isinstance(w, self.Gtk.Button)}
        try:
            self.assertIsInstance(window, self.Adw.MessageDialog)
            action(window, slider, buttons, widgets)
        except BaseException as error:
            self.failure = error
            window.close()
        return False

    def test_drag_and_fine_adjustments(self):
        self.failure = None
        def action(window, slider, buttons, widgets):
            slider.set_value(48)
            buttons["list-add-symbolic"].emit("clicked")
            self.assertEqual(slider.get_value(), 49)
            buttons["list-remove-symbolic"].emit("clicked")
            self.assertEqual(slider.get_value(), 48)
            slider.set_value(8)
            self.assertFalse(buttons["list-remove-symbolic"].get_sensitive())
            slider.set_value(92)
            self.assertFalse(buttons["list-add-symbolic"].get_sensitive())
            slider.set_value(32)
            labels = [w.get_text() for w in widgets if isinstance(w, self.Gtk.Label)]
            self.assertIn("Android: 32 GiB     Armada: 95 GiB", labels)
            if os.environ.get("ARMADA_TEST_SCREENSHOT"):
                shutil.copyfile(Path(self.framebuffer.name) / "Xvfb_screen0", os.environ["ARMADA_TEST_SCREENSHOT"])
            buttons["list-add-symbolic"].emit("clicked")
            buttons["Continue"].emit("clicked")
        self.GLib.timeout_add(400, self.drive, action)
        self.assertEqual(i["choose_android_size"](8, 92, 127), 33)
        if self.failure:
            raise self.failure

    def test_cancel_with_only_one_size(self):
        self.failure = None
        def action(window, slider, buttons, widgets):
            self.assertFalse(slider.get_sensitive())
            self.assertFalse(buttons["list-remove-symbolic"].get_sensitive())
            self.assertFalse(buttons["list-add-symbolic"].get_sensitive())
            buttons["Cancel"].emit("clicked")
        self.GLib.timeout_add(400, self.drive, action)
        with self.assertRaises(i["Cancelled"]):
            i["choose_android_size"](8, 8, 43)
        if self.failure:
            raise self.failure


    @unittest.skipUnless(os.environ.get("DBUS_SESSION_BUS_ADDRESS"), "requires dbus-run-session")
    def test_picker_opens_while_another_instance_owns_the_application_id(self):
        peer = subprocess.Popen([sys.executable, "-c", """
from gi.repository import Gio, GLib
app = Gio.Application(application_id="org.armada.Installer.Size")
app.register(None)
assert not app.get_is_remote()
print("ready", flush=True)
GLib.MainLoop().run()
"""], stdout=subprocess.PIPE)
        self.failure = None
        timer = None
        def action(window, slider, buttons, widgets):
            nonlocal timer
            timer = None
            buttons["Continue"].emit("clicked")
        try:
            self.assertTrue(select.select([peer.stdout], [], [], 5)[0])
            self.assertEqual(peer.stdout.readline(), b"ready\n")
            timer = self.GLib.timeout_add(400, self.drive, action)
            self.assertEqual(i["choose_android_size"](8, 8, 43), 8)
            if self.failure:
                raise self.failure
        finally:
            if timer is not None:
                self.GLib.source_remove(timer)
            peer.terminate()
            peer.wait(timeout=5)
            peer.stdout.close()


if __name__ == "__main__":
    unittest.main()
