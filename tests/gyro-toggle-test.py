#!/usr/bin/env python3
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
loader = importlib.machinery.SourceFileLoader(
    "gyro_control", str(ROOT / "system_files/usr/libexec/armada/armada-control"),
)
spec = importlib.util.spec_from_loader(loader.name, loader)
control = importlib.util.module_from_spec(spec)
loader.exec_module(control)
SSC_SCRIPT = ROOT / "system_files/usr/libexec/armada/armada-ssc"


class GyroToggleTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.dir = Path(directory.name)
        self.config = self.dir / "gyro.conf"
        self.data = self.dir / "ssc"
        (self.data / "ayn-odin3").mkdir(parents=True)
        self.device = "ayn-odin3"
        self.commands = []
        self.fail_restarts = 0
        for target, replacement in (
            ("GYRO_CONFIG", self.config),
            ("SSC_DATA", self.data),
            ("device_env", lambda: {"ARMADA_DEVICE_ID": self.device}),
            ("run", self.fake_run),
        ):
            mock = patch.object(control, target, replacement)
            mock.start()
            self.addCleanup(mock.stop)

    def fake_run(self, command, timeout=20):
        self.commands.append(command)
        if self.fail_restarts:
            self.fail_restarts -= 1
            raise subprocess.CalledProcessError(1, command)

    def test_default_on_and_persisted(self):
        self.assertEqual(control.action_get_gyro({}), self.state(True))
        for enabled in (False, True):
            state = control.action_set_gyro_enabled({"enabled": enabled})
            self.assertEqual(state, self.state(enabled))
            self.assertEqual(self.config.read_text(), f"ARMADA_GYRO={int(enabled)}\n")
        self.assertEqual(self.commands, [["/usr/bin/systemctl", "restart", "inputplumber"]] * 2)

    def state(self, enabled, orientation="default"):
        return {"supported": True, "enabled": enabled, "orientation": orientation}

    def test_orientation_keeps_the_enable_setting(self):
        self.config.write_text("ARMADA_GYRO=0\n")
        self.assertEqual(control.action_set_gyro_orientation({"orientation": "pitch-roll"}),
                         self.state(False, "pitch-roll"))
        self.assertEqual(control.action_set_gyro_enabled({"enabled": True}), self.state(True, "pitch-roll"))
        self.assertEqual(self.config.read_text(), "ARMADA_GYRO=1\nARMADA_GYRO_CORRECTION=1,0,0;0,-1,0;0,0,-1\n")
        self.assertEqual(control.action_set_gyro_orientation({"orientation": "default"}), self.state(True))
        self.assertEqual(self.config.read_text(), "ARMADA_GYRO=1\n")
        for bad in ("custom", "", None, 1):
            with self.assertRaises(ValueError):
                control.action_set_gyro_orientation({"orientation": bad})

    def test_custom_correction(self):
        self.config.write_text("ARMADA_GYRO_CORRECTION=0,1,0;-1,0,0;0,0,1\n")
        self.assertEqual(control.action_get_gyro({})["orientation"], "custom")
        self.assertEqual(control.action_set_gyro_orientation({"orientation": "roll-yaw"})["orientation"], "roll-yaw")

    def test_orientation_names_match_the_axes_they_reverse(self):
        # Board mount matrix; Deck x/y/z map to pitch/roll/yaw.
        mount = [[0, -1, 0], [0, 0, 1], [-1, 0, 0]]
        axes = ("pitch", "roll", "yaw")
        for name, value in control.GYRO_ORIENTATIONS.items():
            if value is None:
                continue
            c = [[int(v) for v in row.split(",")] for row in value.split(";")]
            final = [[sum(mount[i][k] * c[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
            flips = []
            for i in range(3):
                j = next(j for j in range(3) if mount[i][j])
                self.assertEqual(abs(final[i][j]), 1, name)
                if final[i][j] != mount[i][j]:
                    flips.append(axes[i])
            self.assertEqual("-".join(flips), name)

    def test_failed_restart_keeps_the_old_setting(self):
        for previous in (None, "ARMADA_GYRO=1\n"):
            if previous is None:
                self.config.unlink(missing_ok=True)
            else:
                self.config.write_text(previous)
            self.commands = []
            self.fail_restarts = 1
            with self.assertRaises(subprocess.CalledProcessError):
                control.action_set_gyro_enabled({"enabled": False})
            self.assertEqual(self.config.read_text() if self.config.exists() else None, previous)
            self.assertEqual(control.action_get_gyro({})["enabled"], True)
            self.assertEqual(len(self.commands), 1)

    def test_daemon_and_script_agree(self):
        for text in ("", "ARMADA_GYRO=0\n", "ARMADA_GYRO=1\n", "ARMADA_GYRO=\n", " ARMADA_GYRO = 0 \n",
                     "ARMADA_GYRO=0\nARMADA_GYRO=1\n", "ARMADA_GYRO=1 \n", "ARMADA_GYRO=1\r\n", "# comment\n"):
            env = self.ssc(None, True, ["env"], text)[2]
            self.assertEqual(env.startswith("INPUTPLUMBER_FASTRPC=1\n"), control.action_get_gyro({})["enabled"], repr(text))
        self.config.write_bytes(b"# \xff\nARMADA_GYRO=0\n")
        self.assertFalse(control.action_get_gyro({})["enabled"])

    def test_unsupported_device(self):
        self.device = "ayn-odin2"
        self.assertEqual(control.action_get_gyro({}), {"supported": False, "enabled": False, "orientation": "default"})
        with self.assertRaises(RuntimeError):
            control.action_set_gyro_enabled({"enabled": True})
        self.assertFalse(self.config.exists())
        self.assertEqual(self.commands, [])

    def test_rejects_non_bool(self):
        with self.assertRaises(ValueError):
            control.action_set_gyro_enabled({"enabled": "0"})

    def test_correction_passes_through(self):
        for text, matrix in (("", None), ("ARMADA_GYRO_CORRECTION=1, 0, 0; 0, -1, 0; 0, 0, -1\n", "1, 0, 0; 0, -1, 0; 0, 0, -1"),
                             ("ARMADA_GYRO_CORRECTION=\n", None), ('ARMADA_GYRO_CORRECTION=1,0,0"\n', None),
                             ("ARMADA_GYRO_CORRECTION=$(id)\n", None), ('ARMADA_GYRO_CORRECTION=1,0,0\\\n', None),
                             ("ARMADA_GYRO_CORRECTION=1,0,0;0,1,0;0,0,1\nARMADA_GYRO_CORRECTION=0,0,0\n", "1,0,0;0,1,0;0,0,1")):
            line = f'INPUTPLUMBER_SSC_MOUNT_CORRECTION="{matrix}"\n' if matrix else ""
            self.assertEqual(self.ssc(None, True, ["env"], text)[2], "INPUTPLUMBER_FASTRPC=1\n" + line, repr(text))

    def ssc(self, gyro, supported, arg, text=None):
        script = SSC_SCRIPT.read_text()
        bindir = self.dir / "bin"
        bindir.mkdir(exist_ok=True)
        (bindir / "device-env").write_text("#!/bin/sh\necho ARMADA_DEVICE_ID=ayn-odin3\n")
        (bindir / "device-env").chmod(0o755)
        (bindir / "hexagonrpcd").write_text("#!/bin/sh\necho listener \"$@\"\n")
        (bindir / "hexagonrpcd").chmod(0o755)
        node = self.dir / "fastrpc-adsp"
        node.touch()
        data = self.data if supported else self.dir / "none"
        script = (script.replace("/usr/libexec/armada/device-env", str(bindir / "device-env"))
                  .replace("/etc/armada/gyro.conf", str(self.config))
                  .replace("/usr/share/armada/ssc", str(data))
                  .replace("/run/armada", str(self.dir / "run"))
                  .replace("/dev/fastrpc-adsp ", f"{node} "))
        self.config.write_text(text if text is not None else f"ARMADA_GYRO={gyro}\n")
        result = subprocess.run(["bash", "-c", script, "armada-ssc", *arg], text=True, capture_output=True,
                                env={"PATH": f"{bindir}:/usr/bin:/bin"})
        env = self.dir / "run/gyro.env"
        return result.returncode, result.stdout, env.read_text() if env.exists() else None

    def test_listener_ignores_the_setting(self):
        for gyro in (0, 1):
            code, out, _ = self.ssc(gyro, True, [])
            self.assertEqual(code, 0)
            self.assertIn("listener", out)
        code, out, _ = self.ssc(1, False, [])
        self.assertEqual((code, out), (0, ""))

    def test_env_follows_the_setting(self):
        self.assertEqual(self.ssc(1, True, ["env"])[2], "INPUTPLUMBER_FASTRPC=1\n")
        self.assertEqual(self.ssc(0, True, ["env"])[2], "INPUTPLUMBER_FASTRPC=0\n")
        self.assertEqual(self.ssc(1, False, ["env"])[2], "INPUTPLUMBER_FASTRPC=0\n")


if __name__ == "__main__":
    unittest.main()
