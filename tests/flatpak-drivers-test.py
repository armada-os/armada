#!/usr/bin/env python3
# armada-flatpak-drivers: which apps it reports, whether they get our drivers, and the
# global override check.
import contextlib
import importlib.machinery
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
loader = importlib.machinery.SourceFileLoader(
    "flatpak_drivers", str(ROOT / "system_files/usr/bin/armada-flatpak-drivers"),
)
spec = importlib.util.spec_from_loader(loader.name, loader)
drivers = importlib.util.module_from_spec(spec)
loader.exec_module(drivers)


class FlatpakDriversTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.dir = Path(directory.name)
        self.override = self.dir / "flatpak-override"
        self.override.write_text("[Environment]\n")
        self.global_override = self.dir / "overrides/global"
        self.global_override.parent.mkdir()
        self.global_override.symlink_to(self.override)
        self.problems = {}
        self.unoffered = set()  # apps whose runtime gets no GL.host
        self.probed = []
        for target, value in (
            ("GLOBAL_OVERRIDE", self.global_override),
            ("OVERRIDE", self.override),
            ("installed_apps", lambda: ["org.New", "org.Old"]),
        ):
            mock = patch.object(drivers, target, value)
            mock.start()
            self.addCleanup(mock.stop)
        for target, name, value in (
            (drivers.armada_turnip, "flatpak_problem", self.fake_problem),
            (drivers, "offered", lambda app: app not in self.unoffered),
            (drivers, "runtime", lambda app: "org.freedesktop.Platform/aarch64/24.08"),
        ):
            mock = patch.object(target, name, value)
            mock.start()
            self.addCleanup(mock.stop)

    def fake_problem(self, run, app, libraries, exposed):
        self.probed.append(app)
        return self.problems.get(app)

    def run_main(self, apps=()):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), patch.object(drivers.os, "geteuid", lambda: 1000):
            code = drivers.main(list(apps))
        return code, out.getvalue().splitlines()

    def test_reports_each_app(self):
        self.problems["org.Old"] = "undefined symbol: wl_fixes_interface"
        code, lines = self.run_main()
        self.assertEqual(lines, ["org.New: ok", "org.Old: undefined symbol: wl_fixes_interface"])
        self.assertEqual(code, 1)

    def test_an_app_without_gl_host_keeps_its_runtimes_mesa(self):
        self.unoffered.add("org.Old")
        code, lines = self.run_main()
        self.assertEqual(lines[1], "org.Old: its runtime's Mesa "
                                   "(org.freedesktop.Platform/aarch64/24.08 isn't offered Armada's)")
        self.assertEqual(code, 0)
        self.assertEqual(self.probed, ["org.New"])

    def test_all_ok(self):
        self.assertEqual(self.run_main(), (0, ["org.New: ok", "org.Old: ok"]))

    def test_checks_only_the_named_apps(self):
        self.run_main(["org.Named"])
        self.assertEqual(self.probed, ["org.Named"])

    def test_flags_a_global_override_that_is_no_longer_the_link(self):
        self.global_override.unlink()
        self.global_override.write_text("[Environment]\nVK_DRIVER_FILES=/x\n")
        code, lines = self.run_main()
        self.assertIn("is not a link", lines[0])
        self.assertEqual(code, 1)

    def test_flags_a_missing_global_override(self):
        self.global_override.unlink()
        self.assertIn("is missing", self.run_main()[1][0])

    def test_refuses_root(self):
        with patch.object(drivers.os, "geteuid", lambda: 0), self.assertRaises(SystemExit):
            drivers.main([])


class OfferedTest(unittest.TestCase):
    def offered(self, code, stderr=""):
        result = subprocess.CompletedProcess([], code, "", stderr)
        with patch.object(drivers.subprocess, "run", lambda *a, **k: result):
            return drivers.offered("org.App")

    def test_results(self):
        self.assertIs(self.offered(0), True)
        self.assertIs(self.offered(1), False)
        self.assertIs(self.offered(1, "Gtk-WARNING: something\n"), False)
        self.assertEqual(self.offered(1, "error: app/org.App/aarch64/master not installed\n"),
                         "couldn't check: error: app/org.App/aarch64/master not installed")
        self.assertEqual(self.offered(139), "couldn't check: exited 139")


if __name__ == "__main__":
    unittest.main()
