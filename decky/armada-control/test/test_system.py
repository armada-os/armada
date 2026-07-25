import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "py_modules"))

from armada_control import system  # noqa: E402


def completed(stdout="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


class HdrCapabilityTests(unittest.TestCase):
    def test_production_policy_uses_bash_compatible_option_order(self):
        result = completed(
            "builtin export -- ARMADA_HDR_CAPABLE=1 || exit 1\n"
        )
        with mock.patch.object(system, "run_cmd", return_value=result) as runner:
            self.assertTrue(system.hdr_capable())
        command = runner.call_args.args[0]
        bash_index = command.index("/bin/bash")
        self.assertEqual(
            command[bash_index : bash_index + 5],
            ["/bin/bash", "--noprofile", "--norc", "-p", system.HDR_SESSION_FINALIZER],
        )

    def test_missing_capability_export_is_not_qualified(self):
        with mock.patch.object(system, "run_cmd", return_value=completed("")):
            self.assertFalse(system.hdr_capable())


class HdrRuntimeStateTests(unittest.TestCase):
    def test_root_xprop_query_drops_to_the_session_user(self):
        with mock.patch.object(system.os, "geteuid", return_value=0, create=True):
            command = system._xprop_command(":7")
        self.assertEqual(
            command[:8],
            [
                system.RUNUSER,
                "-u",
                system.SESSION_USER,
                "--",
                "/usr/bin/env",
                "-i",
                f"PATH={system.TRUSTED_PATH}",
                system.XPROP,
            ],
        )
        self.assertEqual(command[8:12], ["-display", ":7", "-root", *system._HDR_XPROPS[:1]])

    def test_unprivileged_xprop_query_stays_in_the_session_user(self):
        with mock.patch.object(system.os, "geteuid", return_value=1000, create=True):
            command = system._xprop_command(":3")
        self.assertEqual(command[:4], [system.XPROP, "-display", ":3", "-root"])

    def test_primary_root_missing_enabled_and_brightness_is_valid_off_state(self):
        output = "\n".join(
            [
                "GAMESCOPE_XWAYLAND_SERVER_ID(CARDINAL) = 0",
                "GAMESCOPE_DISPLAY_SUPPORTS_HDR(CARDINAL) = 1",
                "GAMESCOPE_DISPLAY_HDR_ENABLED:  no such atom on any window.",
                "GAMESCOPE_HDR_OUTPUT_FEEDBACK(CARDINAL) = 0",
                "GAMESCOPE_SDR_ON_HDR_CONTENT_BRIGHTNESS:  no such atom on any window.",
            ]
        )
        with mock.patch.object(system, "_x_display_numbers", return_value=[0]), mock.patch.object(
            system, "run_cmd", return_value=completed(output)
        ):
            self.assertEqual(
                system.get_hdr_runtime_state(),
                {
                    "available": True,
                    "display": ":0",
                    "supportsHdr": True,
                    "enabled": False,
                    "outputFeedback": False,
                    "sdrContentBrightnessNits": None,
                    "reason": "ok",
                },
            )

    def test_selects_primary_root_and_decodes_float_cardinal(self):
        secondary = "GAMESCOPE_XWAYLAND_SERVER_ID(CARDINAL) = 1"
        primary = "\n".join(
            [
                "GAMESCOPE_XWAYLAND_SERVER_ID(CARDINAL) = 0",
                "GAMESCOPE_DISPLAY_SUPPORTS_HDR(CARDINAL) = 1",
                "GAMESCOPE_DISPLAY_HDR_ENABLED(CARDINAL) = 1",
                "GAMESCOPE_HDR_OUTPUT_FEEDBACK(CARDINAL) = 1",
                "GAMESCOPE_SDR_ON_HDR_CONTENT_BRIGHTNESS(CARDINAL) = 1140457472",
            ]
        )

        def query(command, timeout=5, capture=True):
            display = command[command.index("-display") + 1]
            return completed(secondary if display == ":1" else primary)

        with mock.patch.object(system, "_x_display_numbers", return_value=[1, 0]), mock.patch.object(
            system, "run_cmd", side_effect=query
        ):
            state = system.get_hdr_runtime_state()
        self.assertTrue(state["available"])
        self.assertEqual(state["display"], ":0")
        self.assertTrue(state["enabled"])
        self.assertTrue(state["outputFeedback"])
        self.assertEqual(state["sdrContentBrightnessNits"], 500.0)

    def test_query_failure_is_not_reported_as_valid_off_state(self):
        with mock.patch.object(system, "_x_display_numbers", return_value=[0]), mock.patch.object(
            system, "run_cmd", return_value=None
        ):
            state = system.get_hdr_runtime_state()
        self.assertFalse(state["available"])
        self.assertEqual(state["reason"], "xprop-query-failed")

    def test_successful_non_primary_query_is_unavailable(self):
        output = "GAMESCOPE_XWAYLAND_SERVER_ID(CARDINAL) = 2"
        with mock.patch.object(system, "_x_display_numbers", return_value=[2]), mock.patch.object(
            system, "run_cmd", return_value=completed(output)
        ):
            state = system.get_hdr_runtime_state()
        self.assertFalse(state["available"])
        self.assertEqual(state["reason"], "primary-gamescope-root-not-found")

    def test_nonfinite_float_cardinal_is_rejected(self):
        nan_bits = 0x7FC00000
        self.assertIsNone(system._cardinal_float(nan_bits))


if __name__ == "__main__":
    unittest.main()
