"""Exercise the real startup wrapper without Steam, a display, or root."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "packages/armada-splash/system/usr/libexec/armada/armada-splash-run"
SESSION = ROOT / "system_files/usr/share/gamescope-session-plus/sessions.d/steam"
LOW_SPACE = "Fatal Error: Steam needs 250MB"


class SteamLaunchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="steam-launch-test.")
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.logs = self.work / ".local/share/armada/logs"
        self.logs.mkdir(parents=True)
        self.events = self.work / "events"
        self.events.touch()
        self.status = self.work / "status"

        # Reserve a port for each case. Normally it stays closed; the fake
        # Steam opens it only after the wrapper has made its initial probe.
        self.listener = socket.socket()
        self.addCleanup(self.listener.close)
        self.listener.bind(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.env = {
            **os.environ,
            "HOME": str(self.work),
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "ARMADA_SPLASH_MODE": "off",
            "ARMADA_SPLASH_CEF_PORT": str(self.port),
            "ARMADA_SPLASH_STATUS": str(self.status),
            "ARMADA_SPLASH_PROGRESS": str(self.bin / "progress"),
            "ARMADA_SPLASH_BIN": str(self.bin / "splash"),
            "ARMADA_SPLASH_ARGS": "--test",
            "DISPLAY": ":test",
            "TEST_EVENTS": str(self.events),
            "TEST_SWITCH_CODE": "0",
            "TEST_ERROR_STATUS": str(self.work / "error-status"),
            "TEST_ERROR_DURATION": str(self.work / "error-duration"),
            "TEST_ERROR_SPLASH_EXIT": "0",
            "TEST_STEAM_STARTED": str(self.work / "steam-started"),
            "TEST_FREE_KIB": "1000000",
        }
        self.env.pop("ARMADA_SPLASH_ERROR_HOLD", None)
        self.script("sudo", '#!/bin/sh\nprintf "sudo %s\\n" "$*" >> "$TEST_EVENTS"\nexit "$TEST_SWITCH_CODE"\n')
        self.script("df", '#!/bin/sh\n[ -e "$2" ] || exit 1\nprintf "Filesystem 1024-blocks Used Available Capacity Mounted on\\n"\nprintf "testfs 10000000 0 %s 0%% /\\n" "$TEST_FREE_KIB"\n')
        self.script("progress", '#!/bin/sh\nprintf "%s\\n" "$*" > "$ARMADA_SPLASH_STATUS"\n')
        self.script("splash", f"#!{sys.executable}\n" + '''
import os, signal, time
from pathlib import Path
events = Path(os.environ["TEST_EVENTS"])
status = Path(os.environ["ARMADA_SPLASH_STATUS"]).read_text()
is_error = status.startswith("!")
started = time.monotonic()
def record(text):
    with events.open("a") as stream:
        stream.write(text + "\\n")
def stop(*args):
    if is_error:
        Path(os.environ["TEST_ERROR_DURATION"]).write_text(str(time.monotonic() - started))
    record("splash stopped")
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
if is_error:
    Path(os.environ["TEST_ERROR_STATUS"]).write_text(status)
    record("error splash started")
    if os.environ["TEST_ERROR_SPLASH_EXIT"] == "1":
        raise SystemExit(1)
else:
    record("splash started")
while True:
    time.sleep(0.05)
''')
        self.steam = self.script("steam", f"#!{sys.executable}\n" + '''
import os, socket, sys, time
from pathlib import Path
mode = sys.argv[1]
Path(os.environ["TEST_STEAM_STARTED"]).touch()
if mode == "ready":
    listener = socket.socket()
    listener.bind(("127.0.0.1", int(os.environ["ARMADA_SPLASH_CEF_PORT"])))
    listener.listen()
    listener.settimeout(5)
    # Two successful probes are the wrapper's readiness contract.
    for _ in range(2):
        connection, _ = listener.accept()
        connection.close()
    time.sleep(0.1)
elif mode == "splash":
    deadline = time.monotonic() + 5
    while "splash started" not in Path(os.environ["TEST_EVENTS"]).read_text():
        if time.monotonic() > deadline:
            raise SystemExit("splash did not start")
        time.sleep(0.01)
if mode in ("fail", "splash"):
    print("Fatal Error: Steam needs 250MB", flush=True)
sys.exit(int(sys.argv[2]))
''')

    def script(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)
        return path

    def run_steam(self, mode="fail", code=1, *, stale=False, command=None):
        if stale:
            self.listener.listen()
        else:
            self.listener.close()
        with (self.work / "output").open("w") as output:
            process = subprocess.Popen(
                ["bash", str(WRAPPER), *(command or [str(self.steam), mode, str(code)])],
                env=self.env, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                process.wait(timeout=20)
            finally:
                # Also clean up renderers on the normal/update paths, where
                # gamescope would ordinarily own session teardown.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
        self.assertEqual(process.returncode, code, (self.work / "output").read_text())
        return self.events.read_text().splitlines()

    def assert_recovery(self, events):
        self.assertEqual(events.count("sudo -n /usr/libexec/armada/session-control recover-desktop"), 1)
        self.assertEqual(self.status.read_text().strip(), "Steam could not start. Restarting in Desktop Mode")

    def test_low_space_opens_desktop_with_splash_off(self):
        started = time.monotonic()
        self.assert_recovery(self.run_steam())
        self.assertLess(time.monotonic() - started, 5, "no renderer: must skip the error hold")
        failure = (self.logs / "last-steam-failure.log").read_text()
        self.assertIn(LOW_SPACE, failure)
        self.assertIn("exit code: 1", failure)

    def test_low_space_is_detected_before_steam_can_fill_the_disk(self):
        self.env["ARMADA_STEAM_MIN_FREE_KIB"] = "999999999999"
        self.assert_recovery(self.run_steam(code=254))
        self.assertFalse((self.work / "steam-started").exists())
        failure = (self.logs / "last-steam-failure.log").read_text()
        self.assertIn(LOW_SPACE, failure)
        self.assertIn("exit code: 254", failure)

    def test_error_is_shown_for_ten_seconds_before_switching(self):
        self.env["ARMADA_SPLASH_MODE"] = "x11"
        self.assertEqual(self.run_steam("splash"), [
            "splash started", "splash stopped",
            "error splash started", "splash stopped",
            "sudo -n /usr/libexec/armada/session-control recover-desktop",
        ])
        self.assertEqual((self.work / "error-status").read_text().splitlines(), [
            "!Steam launch failed (exit 1)", f"!{LOW_SPACE}",
            "Rebooting to Desktop Mode in 10 seconds",
        ])
        # Allow for the renderer process starting just after the hold timer.
        self.assertGreaterEqual(float((self.work / "error-duration").read_text()), 9.5)

    def test_failed_error_renderer_does_not_delay_recovery(self):
        self.env["ARMADA_SPLASH_MODE"] = "x11"
        self.env["TEST_ERROR_SPLASH_EXIT"] = "1"
        started = time.monotonic()
        self.assert_recovery(self.run_steam("splash"))
        self.assertLess(time.monotonic() - started, 5)

    def test_missing_steam_opens_desktop(self):
        self.assert_recovery(self.run_steam(code=127, command=[str(self.work / "missing-steam")]))

    def test_failed_diagnostic_writes_do_not_block_recovery(self):
        # Make both the log directory and status unwritable without relying
        # on permissions (these tests also run as root in build containers).
        self.logs.rmdir()
        self.logs.write_text("not a directory")
        self.status.mkdir()
        self.assertEqual(self.run_steam(), ["sudo -n /usr/libexec/armada/session-control recover-desktop"])

    def test_failed_switch_returns_original_steam_error(self):
        self.env["TEST_SWITCH_CODE"] = "1"
        self.assert_recovery(self.run_steam())
        self.assertIn("failed to restart in Desktop Mode", (self.work / "output").read_text())

    def test_clean_exit_does_not_switch(self):
        self.assertEqual(self.run_steam("clean", 0), [])

    def test_invalid_space_threshold_uses_default(self):
        self.env["ARMADA_STEAM_MIN_FREE_KIB"] = "invalid"
        self.assertEqual(self.run_steam("clean", 0), [])

    def test_leading_zero_space_values_are_decimal(self):
        self.env["ARMADA_STEAM_MIN_FREE_KIB"] = "010"
        self.env["TEST_FREE_KIB"] = "009"
        self.assert_recovery(self.run_steam(code=254))
        self.assertFalse((self.work / "steam-started").exists())

    def test_update_restart_does_not_switch(self):
        self.assertEqual(self.run_steam("update", 42), [])
        self.assertEqual(self.status.read_text().strip(), "Restarting Steam")

    def test_exit_after_ui_ready_does_not_switch(self):
        self.assertEqual(self.run_steam("ready"), [])

    def test_stale_cef_listener_does_not_hide_launch_failure(self):
        self.assert_recovery(self.run_steam(stale=True))

    def test_session_always_installs_recovery_wrapper(self):
        # Disabling the splash must not bypass failure handling altogether.
        wrapper_lines = [line for line in SESSION.read_text().splitlines() if "armada-splash-run" in line]
        self.assertEqual(wrapper_lines, ['CLIENTCMD="/usr/libexec/armada/armada-splash-run ${CLIENTCMD}"'])


if __name__ == "__main__":
    unittest.main()
