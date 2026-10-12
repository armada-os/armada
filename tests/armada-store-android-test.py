#!/usr/bin/env python3
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "decky/armada-store/py_modules"))
from armada_store import android, catalog, installers, jobs, paths, store


class AndroidTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.root = Path(self.work.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.environment = patch.dict(os.environ, {
            "ARMADA_STORE_STATE_DIR": str(self.root / "state"),
            "DECKY_USER_HOME": str(self.home), "DECKY_USER": "missing-test-user",
            "ARMADA_STORE_ALLOW_INSECURE_URLS": "1",
        })
        self.environment.start()
        self.info = {"package": "org.example.test", "name": "Example", "free": True, "version": "1"}
        self.app = android.app_entry(self.info)
        self.files = []
        for name in ("base.apk", "config.arm64_v8a.apk"):
            apk = self.root / name
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("AndroidManifest.xml", "fixture")
                archive.writestr("classes.dex", b"x" * 10000)
            self.files.append({"name": name, "type": "BASE" if name == "base.apk" else "SPLIT",
                               "size": apk.stat().st_size, "url": apk.as_uri(),
                               "sha256": hashlib.sha256(apk.read_bytes()).hexdigest()})
        self.resolve = patch.object(android, "request", return_value={"app": self.info, "files": self.files})
        self.resolve.start()
        android._results = []
        android._retry_at = 0

    def tearDown(self):
        android.stop()
        android._results = []
        android._retry_at = 0
        self.resolve.stop()
        self.environment.stop()
        self.work.cleanup()

    def install(self, cancel=None, progress=lambda done, total: None):
        android.install(self.app, cancel or threading.Event(), progress)

    def test_complete_set_is_published_and_survives_search_change(self):
        progress = []
        job = jobs.Job(self.app["id"], "install", self.app)
        jobs._execute(job)
        self.assertEqual(job.phase, "done", job.error)
        folder = android.apk_path(self.app).parent
        self.assertEqual((folder / ".armada-apks").read_text().splitlines(),
                         ["base.apk", "config.arm64_v8a.apk"])
        self.assertTrue(catalog.installed_map()[self.app["id"]]["installed"])
        launch = catalog.launch_spec(self.app)
        self.assertEqual(launch["compatTool"], "lepton_armada")
        self.assertEqual(store.pending_shortcuts(), [self.app["id"]])
        self.install(progress=lambda done, total: progress.append((done, total)))
        self.assertEqual(progress[-1][0], progress[-1][1])
        self.assertEqual(store.pending_shortcuts(), [self.app["id"]])
        store.record_shortcut(self.app["id"], 123)
        self.install()
        self.assertEqual(store.pending_shortcuts(), [])
        self.assertEqual(store.shortcuts()[self.app["id"]], 123)

    def test_search_ranks_exact_matches_and_retains_cached_metadata(self):
        self.resolve.stop()
        names = [("org.example.z", "Related Z"), ("org.example.a", "Related A"),
                 ("com.termux.styling", "Termux:Style"), ("com.termux", "Termux")]
        with patch.object(android, "request", return_value={"apps": [
            {"package": package, "name": name, "free": True} for package, name in names
        ], "pages": []}):
            reply = android.search("termux")
        self.assertEqual(reply["ids"], ["android:com.termux", "android:com.termux.styling",
                                        "android:org.example.z", "android:org.example.a"])
        with patch.object(android, "request", return_value={"apps": [self.info], "pages": []}) as request:
            android.search("", category="TOOLS")
            request.assert_called_once_with("browse", query="", category="TOOLS")
        self.assertIn("android:com.termux", [app["id"] for app in android.apps()])

    def test_rate_limit_backs_off_without_repeating_requests(self):
        self.resolve.stop()
        process = SimpleNamespace(stdin=io.StringIO(), stdout=io.StringIO(json.dumps({
            "error": "rate_limit", "status": 429, "message": "Google Play is rate limited"
        }) + "\n"), poll=lambda: None, kill=lambda: None, communicate=lambda **kwargs: None)
        android._process = process
        with patch.object(android, "_read_reply", return_value={
            "error": "rate_limit", "status": 429, "message": "Google Play is rate limited"
        }):
            with self.assertLogs(level="WARNING") as logs:
                with self.assertRaisesRegex(RuntimeError, "rate limited"):
                    android.request("resolve", package="com.termux")
            self.assertIn("HTTP 429", logs.output[0])
            self.assertGreater(android._retry_at, time.monotonic())
            before = process.stdin.getvalue()
            with self.assertRaisesRegex(RuntimeError, "rate limited"):
                android.request("resolve", package="com.termux")
            self.assertEqual(process.stdin.getvalue(), before)
            with self.assertRaisesRegex(RuntimeError, "rate limited"):
                android.request("browse", category="TOOLS")
            self.assertEqual(process.stdin.getvalue(), before)

    def test_expired_session_restarts_helper_after_backoff(self):
        self.resolve.stop()

        def process():
            return SimpleNamespace(stdin=io.StringIO(), stdout=io.StringIO(), poll=lambda: None,
                                   kill=lambda: None, communicate=lambda **kwargs: None)

        expired = android._process = process()
        with patch.object(android, "_read_reply", return_value={
            "error": "authentication", "status": 401, "message": "Google Play authentication failed"
        }), self.assertLogs(level="WARNING"):
            with self.assertRaisesRegex(RuntimeError, "authentication failed"):
                android.request("search", query="termux")
        self.assertIsNone(android._process)
        self.assertTrue(expired.stdin.closed)
        self.assertGreater(android._retry_at, time.monotonic())
        fresh = process()
        with patch.object(android.subprocess, "Popen", return_value=fresh) as start:
            with self.assertRaisesRegex(RuntimeError, "authentication failed"):
                android.request("search", query="termux")
            start.assert_not_called()
            android._retry_at = 0
            with patch.object(android, "_read_reply", return_value={"apps": []}):
                self.assertEqual(android.request("search", query="termux"), {"apps": []})
            start.assert_called_once()
        self.assertIs(android._process, fresh)

    def test_helper_startup_failure_is_logged_and_can_retry(self):
        self.resolve.stop()
        with patch.object(android.subprocess, "Popen", side_effect=FileNotFoundError(2, "missing helper")):
            with self.assertLogs(level="ERROR") as logs:
                with self.assertRaisesRegex(RuntimeError, "helper could not start"):
                    android.request("info")
        self.assertIn("errno 2", logs.output[0])
        self.assertIsNone(android._process)
        self.assertEqual(android._retry_at, 0)

    def test_valid_helper_replies_reuse_a_process(self):
        self.resolve.stop()
        process = android._process = subprocess.Popen(
            [sys.executable, "-u", "-c",
             "import sys,json\nfor line in sys.stdin: print(json.dumps({'op':json.loads(line)['op']}))"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
        )
        self.assertEqual(android.request("info"), {"op": "info"})
        self.assertEqual(android.request("details", package="com.termux"), {"op": "details"})
        self.assertIs(android._process, process)
        android.stop()
        self.assertIsNotNone(process.returncode)
        self.assertTrue(process.stdout.closed)

    def test_partial_or_invalid_helper_reply_is_stopped_without_leaking_payload(self):
        self.resolve.stop()
        for payload in (b'{"secret":"private-token"', b'["private-token"]\n'):
            read_fd, write_fd = os.pipe()
            os.write(write_fd, payload)
            os.close(write_fd)
            process = SimpleNamespace(stdin=io.StringIO(), stdout=os.fdopen(read_fd),
                                      poll=lambda: None, kill=lambda: None, communicate=lambda **kwargs: None)
            android._process = process
            with self.assertLogs(level="WARNING") as logs:
                with self.assertRaisesRegex(RuntimeError, "did not respond"):
                    android.request("info")
            self.assertIsNone(android._process)
            self.assertTrue(process.stdout.closed)
            self.assertNotIn("private-token", " ".join(logs.output))

    def test_partial_line_timeout_does_not_wait_for_a_newline(self):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b'{"apps":')
        android._process = SimpleNamespace(stdout=os.fdopen(read_fd), stdin=io.StringIO(),
                                          poll=lambda: None, kill=lambda: None, communicate=lambda **kwargs: None)
        try:
            with patch.object(android.select, "select", side_effect=[([1], [], []), ([], [], [])]):
                with self.assertRaises(TimeoutError):
                    android._read_reply()
        finally:
            os.close(write_fd)

    def test_superseded_idle_timer_does_not_stop_active_helper(self):
        process = android._process = SimpleNamespace(stdin=io.StringIO(), stdout=io.StringIO(),
                                                     kill=lambda: None, communicate=lambda **kwargs: None)
        android._timer = threading.Timer(300, android.stop)
        android.stop(threading.Timer(300, android.stop))
        self.assertIs(android._process, process)

    def test_helper_cleanup_timeout_still_waits_and_closes_pipes(self):
        waits = []
        def communicate(**kwargs):
            raise subprocess.TimeoutExpired("private-token", 5)
        process = android._process = SimpleNamespace(stdin=io.StringIO(), stdout=io.StringIO(),
                                                     kill=lambda: None, communicate=communicate,
                                                     wait=lambda **kwargs: waits.append(kwargs))
        with self.assertLogs(level="WARNING") as logs:
            android.stop()
        self.assertEqual(waits, [{"timeout": 1}])
        self.assertTrue(process.stdin.closed and process.stdout.closed)
        self.assertNotIn("private-token", " ".join(logs.output))

    def test_restricted_search_result_cannot_start_a_download(self):
        app = android.app_entry({**self.info, "restriction": "DEVICE_RESTRICTED"})
        self.assertFalse(app["canInstall"])
        self.assertIn("Unavailable", app["note"])
        android._results = [app]
        with self.assertRaisesRegex(ValueError, "cannot be downloaded"):
            jobs.start(app["id"], "install")

    def test_failure_does_not_replace_existing_download(self):
        self.install()
        previous = android.apk_path(self.app).read_bytes()
        self.files[1]["sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            self.install()
        self.assertEqual(android.apk_path(self.app).read_bytes(), previous)
        self.assertEqual(list(self.home.glob(".armada-store-*")), [])

    def test_wrong_package_or_base_type_does_not_replace_existing_download(self):
        self.install()
        previous = android.apk_path(self.app).read_bytes()
        self.info["package"] = "org.example.wrong"
        with self.assertRaisesRegex(RuntimeError, "Unexpected Android package"):
            self.install()
        self.info["package"] = "org.example.test"
        self.files[0]["type"] = "SPLIT"
        with self.assertRaisesRegex(RuntimeError, "Unsupported APK"):
            self.install()
        self.assertEqual(android.apk_path(self.app).read_bytes(), previous)

    def test_corrupt_apk_with_matching_checksum_is_rejected(self):
        apk = self.root / "base.apk"
        apk.write_bytes(b"not an APK")
        self.files[0].update(size=apk.stat().st_size, sha256=hashlib.sha256(apk.read_bytes()).hexdigest())
        with self.assertLogs(level="ERROR") as logs:
            with self.assertRaisesRegex(RuntimeError, "Invalid APK"):
                self.install()
        self.assertIn("checking APK contents of base.apk", logs.output[0])
        self.assertFalse(android.apk_path(self.app).exists())
        self.assertEqual(list(self.home.glob(".armada-store-*")), [])

    def test_download_failure_logs_context_without_credentials(self):
        with patch.object(installers, "download_to", side_effect=OSError("https://secret-token@example.com")):
            with self.assertLogs(level="WARNING") as logs:
                with self.assertRaisesRegex(RuntimeError, "download failed"):
                    self.install()
        self.assertIn("org.example.test/base.apk", " ".join(logs.output))
        self.assertNotIn("secret-token", " ".join(logs.output))
        self.assertFalse(android.apk_path(self.app).exists())
        self.assertEqual(list(self.home.glob(".armada-store-*")), [])

    def test_state_failure_can_retry_without_duplicate_shortcuts(self):
        with patch.object(store, "record_android", side_effect=OSError("state unavailable")):
            with self.assertLogs(level="ERROR") as logs:
                with self.assertRaises(OSError):
                    self.install()
        self.assertIn("recording installation", logs.output[0])
        self.assertTrue(android.apk_path(self.app).exists())
        self.assertEqual(store.pending_shortcuts(), [])
        self.install()
        self.assertEqual(store.pending_shortcuts(), [self.app["id"]])

    def test_cancelled_download_never_becomes_installed(self):
        cancel = threading.Event()
        with self.assertRaises(installers.Cancelled):
            self.install(cancel, lambda done, total: cancel.set())
        self.assertFalse(android.apk_path(self.app).exists())
        self.assertEqual(store.pending_shortcuts(), [])
        self.assertEqual(list(self.home.glob(".armada-store-*")), [])

    def test_truncated_and_unsafe_downloads_are_rejected(self):
        self.files[0]["size"] += 1
        with self.assertRaisesRegex(RuntimeError, "Incomplete"):
            self.install()
        self.files[0]["name"] = "../base.apk"
        with self.assertRaisesRegex(RuntimeError, "Unsupported"):
            self.install()
        self.assertFalse(android.apk_path(self.app).exists())

    def test_symlink_destination_cannot_redirect_publish(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.home / "Applications").mkdir()
        (self.home / "Applications/Android").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            self.install()
        self.assertEqual(list(outside.iterdir()), [])

    def test_local_import_is_repeatable_and_removal_keeps_source(self):
        apk = self.root / "base.apk"
        with patch.object(catalog, "ANDROID_COMPAT_TOOL_DIR", str(self.root)):
            app_id = android.import_local(str(apk))
            self.assertEqual(android.import_local(str(apk)), app_id)
        self.assertEqual(store.pending_shortcuts(), [app_id])
        store.record_shortcut(app_id, 123)
        with patch.object(catalog, "ANDROID_COMPAT_TOOL_DIR", str(self.root)):
            android.import_local(str(apk))
        self.assertEqual(store.pending_shortcuts(), [])
        app = catalog.find_app(app_id)
        android.uninstall(app)
        self.assertTrue(apk.exists())
        self.assertIsNone(catalog.find_app(app_id))
        with self.assertRaises(ValueError):
            android.import_local(str(self.root / "missing.apk"))


if __name__ == "__main__":
    unittest.main()
