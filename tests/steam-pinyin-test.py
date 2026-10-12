#!/usr/bin/env python3
"""Contract tests for the upstream steam-pinyin launcher.

EXECUTE ONLY INSIDE THE DEDICATED NATIVE x86_64 LINUX CONTAINER.
Set ARMADA_PINYIN_TEST_CONTAINER=1 in the container; this module refuses to run
anywhere else so that a real device profile can never be touched by mistake.

The profile at /usr/share/armada/ibus/profile is a PRECONDITION: the validation
step must deploy the real source profile into the container before this test
runs. This test never creates the profile; it fails loudly when the profile is
missing rather than masking that gap with a skip or a pass.

These tests drive the real bash launcher at
system_files/usr/libexec/armada/steam-pinyin against real native same-UID
`sleep` binaries renamed to `steam` (real /proc, real readlink; nothing fakes
/proc or pgrep). A fixture `ibus-daemon` placed first on PATH records the real
argv and a limited environment the launcher hands to the external daemon
boundary. The launcher script itself is never rewritten.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "system_files/usr/libexec/armada/steam-pinyin"
PROFILE = Path("/usr/share/armada/ibus/profile")

CONTAINER_ENV = "ARMADA_PINYIN_TEST_CONTAINER"
CAPTURE_ENV = "ARMADA_PINYIN_TEST_CAPTURE"

FOREGROUND_ARGS = ["--panel", "disable", "--config", "default", "--emoji-extension", "disable"]

# Only these keys are expected to cross into the daemon environment; the secret
# marker proves that unrelated Steam environment entries are not copied.
CAPTURED_KEYS = (
    "DISPLAY",
    "XAUTHORITY",
    "WAYLAND_DISPLAY",
    "DBUS_SESSION_BUS_ADDRESS",
    "XDG_RUNTIME_DIR",
    "DCONF_PROFILE",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "GSETTINGS_SCHEMA_DIR",
    "ARMADA_STEAM_SECRET_MARKER",
)

DAEMON_SOURCE = """#!{python}
import json
import os
import sys

KEYS = {keys!r}


def first_line(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.readline().rstrip("\\n")
    except OSError:
        return None


capture = os.environ.get({capture!r})
profile = os.environ.get("DCONF_PROFILE")
record = {{
    "argv": sys.argv,
    "env": {{key: os.environ.get(key) for key in KEYS}},
    "profile_first_line": first_line(profile) if profile else None,
}}
with open(capture, "w", encoding="utf-8") as handle:
    json.dump(record, handle)
sys.exit(0)
"""


def setUpModule():
    if os.environ.get(CONTAINER_ENV) != "1":
        raise RuntimeError(
            f"{CONTAINER_ENV}=1 is required; these tests must run only in the "
            "dedicated container so no real device configuration is modified"
        )


def write_fake_daemon(directory):
    """Write the PATH-first fixture daemon; return (bindir, capture_path)."""
    directory.mkdir(parents=True, exist_ok=True)
    daemon = directory / "ibus-daemon"
    daemon.write_text(
        DAEMON_SOURCE.format(python=sys.executable, keys=CAPTURED_KEYS, capture=CAPTURE_ENV)
    )
    daemon.chmod(0o755)
    return directory, directory / "daemon-capture.json"


def start_native_steam(directory, environment, seconds=30):
    """Run a real same-UID native process whose comm name is `steam`."""
    directory.mkdir(parents=True, exist_ok=True)
    executable = directory / "steam"
    shutil.copy2(shutil.which("sleep"), executable)
    process = subprocess.Popen([str(executable), str(seconds)], env=environment)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            if os.readlink(f"/proc/{process.pid}/exe") == str(executable):
                return process
        except OSError:
            pass
        time.sleep(0.02)
    stop_process(process)
    raise AssertionError(f"native steam fixture in {directory} did not start")


def stop_process(process):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def launcher_environment(bindir, capture):
    environment = dict(os.environ)
    environment["PATH"] = f"{bindir}{os.pathsep}{environment.get('PATH', '')}"
    environment[CAPTURE_ENV] = str(capture)
    return environment


class SteamPinyinLauncherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)

    def require_launcher(self):
        if not LAUNCHER.is_file():
            self.fail(f"production launcher is missing: {LAUNCHER} (expected RED before implementation)")

    def require_profile(self):
        if not PROFILE.is_file():
            self.fail(
                f"profile precondition missing: {PROFILE}; the validation step must deploy the "
                "source profile first (this test must not create it)"
            )

    def read_capture(self, capture):
        self.assertTrue(capture.is_file(), "launcher never started the daemon")
        return json.loads(capture.read_text(encoding="utf-8"))

    def test_gamescope_session_forwards_env_profile_and_clears_loader(self):
        self.require_launcher()
        self.require_profile()
        bindir, capture = write_fake_daemon(self.work / "fixture-bin")

        runtime = self.work / "runtime"
        runtime.mkdir()
        xauthority = self.work / "auth with space" / "Xauthority"

        steam_env = {
            "XDG_CURRENT_DESKTOP": "gamescope",
            "DISPLAY": ":23",
            "XAUTHORITY": str(xauthority),
            "WAYLAND_DISPLAY": "wayland-test",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/task/example",
            "XDG_RUNTIME_DIR": str(runtime),
            "ARMADA_STEAM_SECRET_MARKER": "do-not-copy",
        }
        self.addCleanup(stop_process, start_native_steam(self.work / "steam-proc", steam_env))

        environment = launcher_environment(bindir, capture)
        environment["LD_LIBRARY_PATH"] = "/nonexistent/ld-library-path"
        environment["GSETTINGS_SCHEMA_DIR"] = "/nonexistent/gsettings-schema-dir"
        before = dict(os.environ)

        result = subprocess.run(
            ["bash", str(LAUNCHER)], env=environment, capture_output=True, text=True, timeout=8
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        record = self.read_capture(capture)
        self.assertEqual(record["argv"][1:], FOREGROUND_ARGS)

        captured = record["env"]
        self.assertEqual(captured["DISPLAY"], ":23")
        self.assertEqual(captured["XAUTHORITY"], str(xauthority))
        self.assertEqual(captured["WAYLAND_DISPLAY"], "wayland-test")
        self.assertEqual(captured["DBUS_SESSION_BUS_ADDRESS"], "unix:path=/task/example")
        self.assertEqual(captured["XDG_RUNTIME_DIR"], str(runtime))

        self.assertEqual(captured["DCONF_PROFILE"], str(PROFILE))
        self.assertEqual(record["profile_first_line"], "user-db:user")

        self.assertIsNone(captured["LD_LIBRARY_PATH"], "inherited LD_LIBRARY_PATH reached the daemon")
        self.assertIsNone(captured["GSETTINGS_SCHEMA_DIR"], "inherited GSETTINGS_SCHEMA_DIR reached the daemon")
        self.assertIsNone(captured["ARMADA_STEAM_SECRET_MARKER"], "unrelated Steam env was copied")

        self.assertEqual(dict(os.environ), before, "launcher mutated the parent environment")

    def test_desktop_session_is_ignored_until_gamescope_steam_appears(self):
        self.require_launcher()
        self.require_profile()
        bindir, capture = write_fake_daemon(self.work / "fixture-bin")

        runtime = self.work / "runtime"
        runtime.mkdir()

        desktop = start_native_steam(
            self.work / "desktop-steam",
            {"XDG_CURRENT_DESKTOP": "KDE", "DISPLAY": ":77", "XDG_RUNTIME_DIR": str(runtime)},
        )
        self.addCleanup(stop_process, desktop)

        environment = launcher_environment(bindir, capture)
        launcher = subprocess.Popen(
            ["bash", str(LAUNCHER)], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        self.addCleanup(stop_process, launcher)

        time.sleep(0.7)
        gaming = start_native_steam(
            self.work / "gaming-steam",
            {"XDG_CURRENT_DESKTOP": "gamescope", "DISPLAY": ":24", "XDG_RUNTIME_DIR": str(runtime)},
        )
        self.addCleanup(stop_process, gaming)

        _, stderr = launcher.communicate(timeout=8)
        self.assertEqual(launcher.returncode, 0, stderr)

        record = self.read_capture(capture)
        self.assertNotEqual(record["env"]["DISPLAY"], ":77", "launcher attached to the desktop session")
        self.assertEqual(record["env"]["DISPLAY"], ":24")

    def test_missing_profile_fails_fast_and_never_starts_daemon(self):
        self.require_launcher()
        if not PROFILE.exists():
            self.fail(f"profile precondition missing: {PROFILE}; the validation step must deploy it first")

        backup = PROFILE.with_name(PROFILE.name + ".armada-test-backup")
        os.rename(PROFILE, backup)
        self.addCleanup(self.restore_profile, backup)

        bindir, capture = write_fake_daemon(self.work / "fixture-bin")
        environment = launcher_environment(bindir, capture)

        start = time.monotonic()
        result = subprocess.run(
            ["bash", str(LAUNCHER)], env=environment, capture_output=True, text=True, timeout=8
        )
        elapsed = time.monotonic() - start

        self.assertNotEqual(result.returncode, 0, "launcher must fail when the profile is missing")
        self.assertLess(elapsed, 5, "launcher must reject a missing profile before waiting for Steam")
        self.assertFalse(capture.exists(), "daemon must not start without a readable profile")

    def restore_profile(self, backup):
        if backup.exists() and not PROFILE.exists():
            os.rename(backup, PROFILE)


if __name__ == "__main__":
    unittest.main()
