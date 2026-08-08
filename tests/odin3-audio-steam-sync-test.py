#!/usr/bin/env python3
"""Focused tests for Odin 3 PipeWire-to-Steam output synchronization."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "system_files/usr/libexec/armada/odin3-audio-steam-restore"
if "websocket" not in sys.modules:
    try:
        __import__("websocket")
    except ModuleNotFoundError:
        websocket_stub = types.ModuleType("websocket")
        websocket_stub.WebSocketException = Exception
        sys.modules["websocket"] = websocket_stub
loader = importlib.machinery.SourceFileLoader(
    "odin3_audio_steam_sync", str(HELPER)
)
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
steam_sync = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = steam_sync
loader.exec_module(steam_sync)


def result(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")


class SelectionTests(unittest.TestCase):
    def test_stable_pipewire_selection_carries_calibration_indexes(self):
        sinks = json.dumps(
            [
                {"index": 39, "name": "Virtual Surround Sound"},
                {"index": 41, "name": "Stereo"},
                {
                    "index": 172,
                    "name": "alsa_output.platform-sound.HiFi__Headphones__sink",
                },
            ]
        )
        with mock.patch.object(
            steam_sync,
            "run_pactl",
            side_effect=[
                result(
                    "alsa_output.platform-sound.HiFi__Headphones__sink\n"
                ),
                result(sinks),
                result(
                    "alsa_output.platform-sound.HiFi__Headphones__sink\n"
                ),
            ],
        ):
            selection = steam_sync.selected_sink()
        self.assertEqual(
            selection,
            steam_sync.SinkSelection(
                name="alsa_output.platform-sound.HiFi__Headphones__sink",
                pulse_index=172,
                virtual_pulse_index=39,
                stereo_pulse_index=41,
            ),
        )

    def test_duplicate_default_sink_fails_closed(self):
        sinks = json.dumps(
            [
                {"index": 7, "name": "duplicate"},
                {"index": 8, "name": "duplicate"},
            ]
        )
        with mock.patch.object(
            steam_sync,
            "run_pactl",
            side_effect=[
                result("duplicate\n"),
                result(sinks),
                result("duplicate\n"),
            ],
        ):
            self.assertIsNone(steam_sync.selected_sink())

    def test_selection_payload_is_json_escaped_not_javascript_source(self):
        name = 'sink"; throw new Error("unsafe")\n\u2028'
        expression = steam_sync.selection_expression(
            steam_sync.SinkSelection(name, 7, 8, 9)
        )
        prefix = "const requested = "
        encoded = expression.split(prefix, 1)[1].split(";\n", 1)[0]
        payload = json.loads(encoded)
        self.assertEqual(payload["name"], name)
        self.assertIn(r"\"", encoded)
        self.assertIn(r"\n", encoded)
        self.assertIn(r"\u2028", encoded)
        self.assertNotIn("\u2028", encoded)

    def test_unsettled_pipewire_inventory_requests_service_retry(self):
        with (
            mock.patch.object(steam_sync, "is_odin3", return_value=True),
            mock.patch.object(
                steam_sync,
                "find_shared_context",
                return_value="ws://127.0.0.1/context",
            ),
            mock.patch.object(steam_sync, "selected_sink", return_value=None),
            mock.patch.object(steam_sync, "update_steam_override") as update,
        ):
            self.assertEqual(steam_sync.main(), 1)
        update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
