import json
import subprocess
import sys
import tempfile
import threading
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
                    "displayIsExternal": None,
                    "supportsHdr": True,
                    "enabled": False,
                    "outputFeedback": False,
                    "sdrContentBrightnessNits": None,
                    "autoHdrSupported": False,
                    "autoHdrEnabled": False,
                    "autoHdrSdrNits": None,
                    "autoHdrTargetNits": None,
                    "autoHdrSupportedModes": 0,
                    "autoHdrModeProtocolPresent": False,
                    "autoHdrModeProtocol": False,
                    "autoHdrMode": None,
                    "autoHdrEffectiveMode": None,
                    "reason": "ok",
                },
            )

    def test_selects_primary_root_and_decodes_float_cardinal(self):
        secondary = "GAMESCOPE_XWAYLAND_SERVER_ID(CARDINAL) = 1"
        primary = "\n".join(
            [
                "GAMESCOPE_XWAYLAND_SERVER_ID(CARDINAL) = 0",
                "GAMESCOPE_DISPLAY_IS_EXTERNAL(CARDINAL) = 0",
                "GAMESCOPE_DISPLAY_SUPPORTS_HDR(CARDINAL) = 1",
                "GAMESCOPE_DISPLAY_HDR_ENABLED(CARDINAL) = 1",
                "GAMESCOPE_HDR_OUTPUT_FEEDBACK(CARDINAL) = 1",
                "GAMESCOPE_SDR_ON_HDR_CONTENT_BRIGHTNESS(CARDINAL) = 1140457472",
                "GAMESCOPE_HDR_ITM_SUPPORTED(CARDINAL) = 1",
                "GAMESCOPE_HDR_ITM_ENABLE(CARDINAL) = 1",
                "GAMESCOPE_HDR_ITM_SDR_NITS(CARDINAL) = 203",
                "GAMESCOPE_HDR_ITM_TARGET_NITS(CARDINAL) = 650",
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
        self.assertFalse(state["displayIsExternal"])
        self.assertTrue(state["enabled"])
        self.assertTrue(state["outputFeedback"])
        self.assertEqual(state["sdrContentBrightnessNits"], 500.0)
        self.assertTrue(state["autoHdrSupported"])
        self.assertTrue(state["autoHdrEnabled"])
        self.assertEqual(state["autoHdrSdrNits"], 203)
        self.assertEqual(state["autoHdrTargetNits"], 650)
        self.assertEqual(
            state["autoHdrSupportedModes"],
            system.AUTO_HDR_SUPPORTED_MODE_EFFICIENT,
        )
        self.assertFalse(state["autoHdrModeProtocol"])
        self.assertEqual(state["autoHdrMode"], system.AUTO_HDR_MODE_EFFICIENT)
        self.assertEqual(
            state["autoHdrEffectiveMode"],
            system.AUTO_HDR_MODE_EFFICIENT,
        )

    def test_parses_adaptive_mode_protocol_and_effective_fallback(self):
        output = "\n".join(
            [
                "GAMESCOPE_XWAYLAND_SERVER_ID(CARDINAL) = 0",
                "GAMESCOPE_DISPLAY_IS_EXTERNAL(CARDINAL) = 0",
                "GAMESCOPE_DISPLAY_SUPPORTS_HDR(CARDINAL) = 1",
                "GAMESCOPE_DISPLAY_HDR_ENABLED(CARDINAL) = 1",
                "GAMESCOPE_HDR_OUTPUT_FEEDBACK(CARDINAL) = 1",
                "GAMESCOPE_HDR_ITM_SUPPORTED(CARDINAL) = 1",
                "GAMESCOPE_HDR_ITM_ENABLE(CARDINAL) = 1",
                "GAMESCOPE_HDR_ITM_SUPPORTED_MODES(CARDINAL) = 2",
                "GAMESCOPE_HDR_ITM_MODE(CARDINAL) = 2",
                "GAMESCOPE_HDR_ITM_EFFECTIVE_MODE(CARDINAL) = 1",
            ]
        )
        with mock.patch.object(system, "_x_display_numbers", return_value=[0]), mock.patch.object(
            system, "run_cmd", return_value=completed(output)
        ):
            state = system.get_hdr_runtime_state()
        self.assertTrue(state["autoHdrModeProtocol"])
        self.assertEqual(
            state["autoHdrSupportedModes"],
            system.AUTO_HDR_SUPPORTED_MODE_HIGH_QUALITY,
        )
        self.assertTrue(state["autoHdrModeProtocolPresent"])
        self.assertEqual(state["autoHdrMode"], system.AUTO_HDR_MODE_HIGH_QUALITY)
        self.assertEqual(
            state["autoHdrEffectiveMode"],
            system.AUTO_HDR_MODE_EFFICIENT,
        )

    def test_runtime_query_never_requests_removed_profile_atoms(self):
        command = system._xprop_command(":0")
        self.assertNotIn("GAMESCOPE_HDR_ITM_SUPPORTED_PROFILES", command)
        self.assertNotIn("GAMESCOPE_HDR_ITM_PROFILE", command)
        self.assertNotIn("GAMESCOPE_HDR_ITM_EFFECTIVE_PROFILE", command)

    def test_partial_or_malformed_adaptive_mode_protocol_fails_closed(self):
        base = [
            "GAMESCOPE_XWAYLAND_SERVER_ID(CARDINAL) = 0",
            "GAMESCOPE_DISPLAY_IS_EXTERNAL(CARDINAL) = 0",
            "GAMESCOPE_DISPLAY_SUPPORTS_HDR(CARDINAL) = 1",
            "GAMESCOPE_DISPLAY_HDR_ENABLED(CARDINAL) = 1",
            "GAMESCOPE_HDR_OUTPUT_FEEDBACK(CARDINAL) = 1",
            "GAMESCOPE_HDR_ITM_SUPPORTED(CARDINAL) = 1",
            "GAMESCOPE_HDR_ITM_ENABLE(CARDINAL) = 1",
            "GAMESCOPE_HDR_ITM_SUPPORTED_MODES(CARDINAL) = 3",
        ]
        cases = (
            (["GAMESCOPE_HDR_ITM_EFFECTIVE_MODE(CARDINAL) = 1"], "missing-mode"),
            (["GAMESCOPE_HDR_ITM_MODE(CARDINAL) = 2"], "missing-effective"),
            ([
                "GAMESCOPE_HDR_ITM_MODE(CARDINAL) = 3",
                "GAMESCOPE_HDR_ITM_EFFECTIVE_MODE(CARDINAL) = 1",
            ], "malformed-mode"),
            ([
                "GAMESCOPE_HDR_ITM_MODE(CARDINAL) = 2",
                "GAMESCOPE_HDR_ITM_EFFECTIVE_MODE(CARDINAL) = 3",
            ], "malformed-effective"),
        )
        for extra, label in cases:
            with self.subTest(label=label), mock.patch.object(
                system, "_x_display_numbers", return_value=[0]
            ), mock.patch.object(
                system, "run_cmd", return_value=completed("\n".join(base + extra))
            ):
                state = system.get_hdr_runtime_state()
            self.assertTrue(state["autoHdrModeProtocolPresent"])
            self.assertFalse(state["autoHdrModeProtocol"])
            self.assertEqual(state["autoHdrSupportedModes"], 0)
            self.assertIsNone(state["autoHdrMode"])
            self.assertIsNone(state["autoHdrEffectiveMode"])

    def test_present_non_cardinal_duplicate_or_unparsable_supported_modes_is_malformed(self):
        base = [
            "GAMESCOPE_XWAYLAND_SERVER_ID(CARDINAL) = 0",
            "GAMESCOPE_DISPLAY_IS_EXTERNAL(CARDINAL) = 0",
            "GAMESCOPE_DISPLAY_SUPPORTS_HDR(CARDINAL) = 1",
            "GAMESCOPE_DISPLAY_HDR_ENABLED(CARDINAL) = 1",
            "GAMESCOPE_HDR_OUTPUT_FEEDBACK(CARDINAL) = 1",
            "GAMESCOPE_HDR_ITM_SUPPORTED(CARDINAL) = 1",
            "GAMESCOPE_HDR_ITM_ENABLE(CARDINAL) = 1",
            "GAMESCOPE_HDR_ITM_MODE(CARDINAL) = 2",
            "GAMESCOPE_HDR_ITM_EFFECTIVE_MODE(CARDINAL) = 1",
        ]
        cases = (
            (["GAMESCOPE_HDR_ITM_SUPPORTED_MODES(STRING) = 3"], "wrong-type"),
            ([
                "GAMESCOPE_HDR_ITM_SUPPORTED_MODES(CARDINAL) = 3",
                "GAMESCOPE_HDR_ITM_SUPPORTED_MODES(CARDINAL) = 3",
            ], "duplicate"),
            (["GAMESCOPE_HDR_ITM_SUPPORTED_MODES(CARDINAL) = invalid"], "unparsable"),
            (["GAMESCOPE_HDR_ITM_SUPPORTED_MODES(CARDINAL) ="], "empty"),
        )
        for supported, label in cases:
            with self.subTest(label=label), mock.patch.object(
                system, "_x_display_numbers", return_value=[0]
            ), mock.patch.object(
                system,
                "run_cmd",
                return_value=completed("\n".join(base + supported)),
            ):
                state = system.get_hdr_runtime_state()
            self.assertTrue(state["autoHdrModeProtocolPresent"])
            self.assertFalse(state["autoHdrModeProtocol"])
            self.assertEqual(state["autoHdrSupportedModes"], 0)
            self.assertIsNone(state["autoHdrMode"])
            self.assertIsNone(state["autoHdrEffectiveMode"])

    def test_external_output_identity_is_parsed_explicitly(self):
        output = "\n".join(
            [
                "GAMESCOPE_XWAYLAND_SERVER_ID(CARDINAL) = 0",
                "GAMESCOPE_DISPLAY_IS_EXTERNAL(CARDINAL) = 1",
            ]
        )
        with mock.patch.object(system, "_x_display_numbers", return_value=[0]), mock.patch.object(
            system, "run_cmd", return_value=completed(output)
        ):
            self.assertTrue(system.get_hdr_runtime_state()["displayIsExternal"])

    def test_invalid_output_identity_is_unknown(self):
        output = "\n".join(
            [
                "GAMESCOPE_XWAYLAND_SERVER_ID(CARDINAL) = 0",
                "GAMESCOPE_DISPLAY_IS_EXTERNAL(CARDINAL) = 2",
            ]
        )
        with mock.patch.object(system, "_x_display_numbers", return_value=[0]), mock.patch.object(
            system, "run_cmd", return_value=completed(output)
        ):
            self.assertIsNone(system.get_hdr_runtime_state()["displayIsExternal"])

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

    def test_auto_hdr_set_command_drops_root_and_never_uses_a_shell(self):
        with mock.patch.object(system.os, "geteuid", return_value=0, create=True):
            command = system._xprop_set_command(":4", "GAMESCOPE_HDR_ITM_ENABLE", 1)
        self.assertEqual(command[:7], [
            system.RUNUSER, "-u", system.SESSION_USER, "--", "/usr/bin/env", "-i",
            f"PATH={system.TRUSTED_PATH}",
        ])
        self.assertEqual(command[7:], [
            system.XPROP, "-display", ":4", "-root", "-f",
            "GAMESCOPE_HDR_ITM_ENABLE", "32c", "-set", "GAMESCOPE_HDR_ITM_ENABLE", "1",
        ])

class AutoHdrPreferenceTests(unittest.TestCase):
    def preferences(self, enabled=True, apps=None):
        return {
            "version": 2,
            "global": {"enabled": enabled},
            "apps": apps or {},
        }

    def runtime(self, enabled=False, mode=2, effective=0):
        return {
            "available": True,
            "display": ":0",
            "displayIsExternal": False,
            "supportsHdr": True,
            "enabled": True,
            "outputFeedback": True,
            "autoHdrSupported": True,
            "autoHdrEnabled": enabled,
            "autoHdrSdrNits": 203 if enabled else None,
            "autoHdrTargetNits": 650 if enabled else None,
            "autoHdrSupportedModes": 3,
            "autoHdrModeProtocolPresent": True,
            "autoHdrModeProtocol": True,
            "autoHdrMode": mode,
            "autoHdrEffectiveMode": effective,
            "reason": "ok",
        }

    def test_schema_validation_preserves_explicit_false_inheritance(self):
        preferences = system._validate_auto_hdr_preferences(
            self.preferences(apps={"123": {"enabled": False}})
        )
        self.assertEqual(
            system._resolve_auto_hdr_preference(preferences, "game", "123"),
            {"enabled": False},
        )
        self.assertEqual(
            system._resolve_auto_hdr_preference(preferences, "game", "456"),
            {"enabled": True},
        )

    def test_schema_rejects_unknown_fields_and_invalid_appids(self):
        invalid = (
            {**self.preferences(), "extra": True},
            {
                **self.preferences(),
                "global": {"enabled": True, "profile": "quality"},
            },
            self.preferences(apps={"0": {"enabled": True}}),
            self.preferences(apps={"-1": {"enabled": True}}),
            self.preferences(apps={"4294967296": {"enabled": True}}),
            self.preferences(apps={"769": {"enabled": True}}),
            self.preferences(apps={"abc": {"enabled": True}}),
            self.preferences(apps={"12": {}}),
            {**self.preferences(), "version": True},
        )
        for preferences in invalid:
            with self.subTest(preferences=preferences), self.assertRaises(ValueError):
                system._validate_auto_hdr_preferences(preferences)

    def test_preference_write_requests_privileged_atomic_config_path(self):
        preferences = self.preferences()
        with mock.patch.object(system, "call") as privileged:
            system._write_auto_hdr_preferences(preferences)
        privileged.assert_called_once()
        self.assertEqual(privileged.call_args.args, ("write_config",))
        self.assertEqual(
            privileged.call_args.kwargs["name"], "auto-hdr-profiles"
        )
        self.assertEqual(
            json.loads(privileged.call_args.kwargs["text"]), preferences
        )

    def test_missing_preferences_seed_from_verified_runtime(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            system,
            "AUTO_HDR_PREFERENCES_PATH",
            Path(directory) / "missing.json",
        ), mock.patch.object(
            system,
            "get_hdr_runtime_state",
            return_value=self.runtime(enabled=True, mode=2, effective=1),
        ), mock.patch.object(system, "_write_auto_hdr_preferences") as writer:
            preferences = system._load_auto_hdr_preferences_locked()
        self.assertEqual(
            preferences["global"], {"enabled": True}
        )
        writer.assert_called_once_with(preferences)

    def test_missing_preferences_default_disabled_when_unverified(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            system,
            "AUTO_HDR_PREFERENCES_PATH",
            Path(directory) / "missing.json",
        ), mock.patch.object(
            system,
            "get_hdr_runtime_state",
            return_value={"available": False},
        ), mock.patch.object(system, "_write_auto_hdr_preferences"):
            preferences = system._load_auto_hdr_preferences_locked()
        self.assertEqual(
            preferences["global"], {"enabled": False}
        )

    def test_v1_preferences_migrate_to_enable_only_v2_schema(self):
        legacy = {
            "version": 1,
            "global": {"enabled": True, "profile": "eco"},
            "apps": {
                "123": {"enabled": False, "profile": "eco"},
                "456": {"profile": "quality"},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            path.write_text(json.dumps(legacy), encoding="utf-8")
            with mock.patch.object(
                system, "AUTO_HDR_PREFERENCES_PATH", path
            ), mock.patch.object(
                system, "_write_auto_hdr_preferences"
            ) as writer:
                preferences = system._load_auto_hdr_preferences_locked()
        self.assertEqual(
            preferences,
            {
                "version": 2,
                "global": {"enabled": True},
                "apps": {"123": {"enabled": False}},
            },
        )
        writer.assert_called_once_with(preferences)

    def test_combined_live_apply_writes_mode_two_before_enable(self):
        before = self.runtime(enabled=False, mode=1, effective=0)
        after = self.runtime(enabled=True, mode=2, effective=1)
        with mock.patch.object(
            system, "get_hdr_runtime_state", side_effect=[before, after]
        ), mock.patch.object(
            system, "run_cmd", return_value=completed()
        ) as runner:
            self.assertEqual(
                system._apply_auto_hdr_preference_locked(
                    {"enabled": True}
                ),
                after,
            )
        writes = [
            command[command.index("-set") + 1 :]
            for command in (entry.args[0] for entry in runner.call_args_list)
        ]
        self.assertEqual(
            writes,
            [
                ["GAMESCOPE_HDR_ITM_SDR_NITS", "203"],
                ["GAMESCOPE_HDR_ITM_TARGET_NITS", "650"],
                ["GAMESCOPE_HDR_ITM_MODE", "2"],
                ["GAMESCOPE_HDR_ITM_ENABLE", "1"],
            ],
        )

    def test_combined_live_apply_rolls_back_mode_and_enable(self):
        before = self.runtime(enabled=True, mode=1, effective=1)
        failed = self.runtime(enabled=True, mode=1, effective=1)
        restored = self.runtime(enabled=True, mode=1, effective=1)
        with mock.patch.object(
            system,
            "get_hdr_runtime_state",
            side_effect=[before, failed, restored],
        ), mock.patch.object(
            system, "run_cmd", return_value=completed()
        ) as runner:
            with self.assertRaisesRegex(RuntimeError, "did not converge"):
                system._apply_auto_hdr_preference_locked(
                    {"enabled": True}
                )
        rollback_writes = [
            entry.args[0][entry.args[0].index("-set") + 1 :]
            for entry in runner.call_args_list[-2:]
        ]
        self.assertEqual(
            rollback_writes,
            [
                ["GAMESCOPE_HDR_ITM_MODE", "1"],
                ["GAMESCOPE_HDR_ITM_ENABLE", "1"],
            ],
        )

    def test_mode_two_accepts_internal_efficient_fallback(self):
        before = self.runtime(enabled=True, mode=1, effective=1)
        fallback = self.runtime(enabled=True, mode=2, effective=1)
        with mock.patch.object(
            system,
            "get_hdr_runtime_state",
            side_effect=[before, fallback],
        ), mock.patch.object(system, "run_cmd", return_value=completed()):
            result = system._apply_auto_hdr_preference_locked(
                {"enabled": True}
            )
        self.assertEqual(result["autoHdrMode"], 2)
        self.assertEqual(result["autoHdrEffectiveMode"], 1)

    def test_missing_mode_protocol_fails_closed_without_writing(self):
        before = {
            **self.runtime(enabled=True),
            "autoHdrModeProtocolPresent": False,
            "autoHdrModeProtocol": False,
            "autoHdrSupportedModes": 1,
            "autoHdrMode": 1,
            "autoHdrEffectiveMode": 1,
        }
        for enabled in (False, True):
            with self.subTest(enabled=enabled), mock.patch.object(
                system, "get_hdr_runtime_state", return_value=before
            ), mock.patch.object(system, "run_cmd") as runner:
                with self.assertRaisesRegex(RuntimeError, "protocol"):
                    system._apply_auto_hdr_preference_locked(
                        {"enabled": enabled}
                    )
                runner.assert_not_called()

    def test_update_reconciles_active_override_not_changed_global(self):
        current = self.preferences(
            enabled=True,
            apps={"123": {"enabled": False}},
        )
        runtime = self.runtime(enabled=False, mode=2)
        with mock.patch.object(
            system, "_load_auto_hdr_preferences_locked", return_value=current
        ), mock.patch.object(
            system, "_apply_auto_hdr_preference_locked", return_value=runtime
        ) as apply_runtime, mock.patch.object(
            system, "_write_auto_hdr_preferences"
        ):
            snapshot = system.update_auto_hdr_preferences(
                "global", None, "game", "123", {"enabled": False}
            )
        apply_runtime.assert_called_once_with(
            {"enabled": False}
        )
        self.assertFalse(snapshot["resolved"]["enabled"])
        self.assertEqual(snapshot["override"]["enabled"], False)

    def test_update_rejects_removed_profile_preference(self):
        with self.assertRaisesRegex(ValueError, "Invalid Auto HDR preference patch"):
            system.update_auto_hdr_preferences(
                "global", None, "global", None, {"profile": "eco"}
            )


if __name__ == "__main__":
    unittest.main()
