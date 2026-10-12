#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HELPER_HOME = Path(os.environ.get("ARMADA_AURORA_HOME", "/usr/lib/armada-aurora"))
HELPER = HELPER_HOME / "bin/armada-aurora"


class Dispenser(BaseHTTPRequestHandler):
    requests = []
    response = b"<html>blocked secret-token@example.com</html>"
    status = 403

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        type(self).requests.append((self.headers["User-Agent"], json.loads(body)))
        self.send_response(type(self).status)
        self.end_headers()
        self.wfile.write(type(self).response)

    def log_message(self, *args):
        pass


class HelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not HELPER.exists():
            raise RuntimeError("Install armada-aurora or set ARMADA_AURORA_HOME to its extracted files")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Dispenser)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        Dispenser.requests = []
        Dispenser.status = 403
        Dispenser.response = b"<html>blocked secret-token@example.com</html>"

    def run_helper(self, lines):
        environment = dict(os.environ, JAVA_HOME=str(HELPER_HOME / "runtime"), ARMADA_AURORA_DISPENSER=
                           "http://127.0.0.1:{}/auth".format(self.server.server_port))
        result = subprocess.run([str(HELPER)], input="\n".join(lines) + "\n",
                                text=True, capture_output=True, env=environment, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertNotIn("secret-token", result.stdout)
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_offline_info_and_bad_requests_do_not_authenticate(self):
        result = self.run_helper([
            '{"op":"info"}', "not json", '{"op":"login","password":"secret-token"}',
            '{"op":"details","package":"../etc/passwd"}',
            '{"op":"search","query":""}',
            '{"op":"browse","category":"../invalid"}',
            '{"op":"search","query":"VLC","page":{"kind":"bundle","url":"https://example.com"}}',
            '{"op":"info"}',
        ])
        self.assertEqual(result[0], {"library": "3.6.4", "androidApi": 30,
                                     "abis": "arm64-v8a", "density": 320, "anonymous": True})
        self.assertEqual(result[-1], result[0])
        self.assertTrue(all(row["error"] == "request" for row in result[1:-1]))
        self.assertEqual(Dispenser.requests, [])

    def test_blocked_auth_is_safe_and_does_not_hammer_dispenser(self):
        result = self.run_helper(['{"op":"search","query":"VLC"}',
                                  '{"op":"details","package":"org.videolan.vlc"}'])
        self.assertEqual(result, [{"error": "authentication",
                                   "message": "Anonymous authentication HTTP 403"}] * 2)
        self.assertEqual(len(Dispenser.requests), 1)
        agent, profile = Dispenser.requests[0]
        self.assertEqual(agent, "com.aurora.store-4.8.4-76")
        self.assertEqual(profile["Build.VERSION.SDK_INT"], "30")
        self.assertEqual(profile["Platforms"], "arm64-v8a")
        self.assertEqual(profile["GL.Version"], "196609")
        features = set(profile["Features"].split(","))
        self.assertTrue({"android.hardware.microphone", "android.hardware.wifi",
                         "android.hardware.vulkan.level=1", "android.hardware.vulkan.version=4198400",
                         "android.software.webview"} <= features)
        self.assertFalse(any(feature.startswith(("android.hardware.camera", "android.hardware.location",
                                                "android.hardware.sensor", "android.hardware.telephony",
                                                "android.hardware.bluetooth")) for feature in features))
        self.assertNotIn("com.google.android.gms", profile["SharedLibraries"])

    def test_malformed_session_does_not_expose_response(self):
        Dispenser.status = 200
        Dispenser.response = b'{"email":"secret-token@example.com"}'
        result = self.run_helper(['{"op":"search","query":"VLC"}'])
        self.assertEqual(result, [{"error": "authentication",
                                   "message": "Invalid anonymous session response"}])


if __name__ == "__main__":
    unittest.main()
