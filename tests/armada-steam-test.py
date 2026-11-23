#!/usr/bin/env python3
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
import armada_steam as health


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.home = self.base / "home"
        self.h = health.SteamMaintenance(self.home, self.base / "run")
        self.h.root.mkdir(parents=True)
        (self.h.root / "steamrtarm64").mkdir()
        (self.h.root / "steamrtarm64/steam").write_bytes(b"old client")
        # Stands in for steam-install: records how it was run and lays down the factory client.
        self.installer = self.base / "steam-install"
        self.installer.write_text(
            "#!/usr/bin/bash\n"
            "set -e\n"
            'echo "$1 $HOME $STEAM_ROOT" > "$RECORD"\n'
            '[[ -z "${FAIL:-}" ]] || { echo "tarball missing" >&2; exit 1; }\n'
            'mkdir -p "$STEAM_ROOT/steamrtarm64"\n'
            'printf "factory client" > "$STEAM_ROOT/steamrtarm64/steam"\n')
        self.installer.chmod(0o755)
        self.record = self.base / "record"
        self.addCleanup(patch.stopall)
        patch.object(health, "progress").start()
        patch.object(health, "INSTALLER", str(self.installer)).start()
        patch.dict(os.environ, {"RECORD": str(self.record)}, clear=False).start()
        os.environ.pop("STEAM_ROOT", None)

    def test_restore_runs_the_packaged_installer_and_keeps_user_data(self):
        preserved = ["steamapps/common/game/save", "userdata/123/save", "config/loginusers.vdf",
                     "compatibilitytools.d/custom/tool", "ssfn123", "logs/bootstrap_log.txt", "custom-file"]
        caches = ["config/htmlcache", "config/widevine", "appcache/httpcache", "appcache/cefdata"]
        for relative in preserved + [cache + "/cache" for cache in caches]:
            path = self.h.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(relative)
        dot = self.home / ".steam"
        dot.mkdir()
        (dot / "steam.pid").write_text("stale PID")
        self.h.restore()
        self.assertEqual(self.record.read_text(), f"--repair {self.home} {self.h.root}\n")
        for relative in preserved:
            self.assertEqual((self.h.root / relative).read_text(), relative)
        self.assertEqual((self.h.root / "steamrtarm64/steam").read_bytes(), b"factory client")
        self.assertFalse((dot / "steam.pid").exists())
        for cache in caches:
            self.assertFalse((self.h.root / cache).exists())

    def test_reset_runs_the_installer_in_reset_mode(self):
        self.h.restore(reset=True)
        self.assertEqual(self.record.read_text(), f"--reset {self.home} {self.h.root}\n")

    def test_installer_failure_is_reported(self):
        with patch.dict(os.environ, {"FAIL": "1"}):
            with self.assertRaisesRegex(RuntimeError, "tarball missing"):
                self.h.restore()

    def test_custom_root_and_symlink_are_not_repaired(self):
        with patch.dict(os.environ, {"STEAM_ROOT": str(self.base / "custom")}):
            with self.assertRaisesRegex(RuntimeError, "custom"):
                self.h.restore()
        elsewhere = self.base / "elsewhere"
        self.h.root.rename(elsewhere)
        self.h.root.symlink_to(elsewhere)
        with self.assertRaisesRegex(RuntimeError, "symlinked"):
            self.h.restore()
        self.assertFalse(self.record.exists())

    def test_busy_repair_does_not_stop_clients(self):
        with self.h.lock(), patch.object(health, "stop_clients") as stop:
            with self.assertRaisesRegex(RuntimeError, "already running"):
                self.h.restore()
        stop.assert_not_called()

    def test_running_client_stops_before_the_installer_runs(self):
        executable = self.h.root / "steamrtarm64/steam"
        shutil.copyfile(shutil.which("sleep"), executable)
        executable.chmod(0o755)
        client = subprocess.Popen([str(executable), "60"])
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if Path(f"/proc/{client.pid}/exe").resolve() == executable:
                    break
                time.sleep(0.01)
            else:
                self.fail("Client did not launch")
            self.h.restore()
            client.wait(timeout=5)
            self.assertEqual(executable.read_bytes(), b"factory client")
        finally:
            health.stop_clients(self.h.root.resolve())
            if client.poll() is None:
                client.kill()
            client.wait()


if __name__ == "__main__":
    unittest.main()
