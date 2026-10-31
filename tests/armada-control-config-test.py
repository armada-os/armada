#!/usr/bin/env python3
import asyncio
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "system_files/usr/lib/armada"
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(ROOT / "decky/armada-control/py_modules"))
os.environ["ARMADA_GAME_TWEAKS_LIB"] = str(LIB)

from armada_control import config, power, system, tweaks

INITIAL_KEYS = {
    "tweaks", "tweaksDefaults", "installedGames", "fexProfiles", "turnipDrivers",
    "envPresets", "perf", "cpuDeviceClass", "rgbSupported", "protonDefaults",
}
PROFILES_KEYS = {"power", "powerDefaults", "freqLimits"}
CONTROLLER_KEYS = {"controllerType", "controllerTypes", "calibratedAt", "hasCalibration", "gyro"}
DEVICE_KEYS = {"panelCalibrationSupported", "chargingFanPwm", "chargingFanSupported"}
EXPERIMENTAL_KEYS = {
    "bottomScreenSupported", "bottomScreenEnabled", "bottomScreenBrightnessSupported",
    "bottomScreenActive", "bottomScreenBrightness",
    "swipeGesturesEnabled", "mtpEnabled", "desktopMode", "desktopModes", "sleepMode", "sleepModes",
}
ABOUT_KEYS = {"osVersion", "ablVersion", "sshEnabled"}


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class ConfigLoadingTest(unittest.TestCase):
    def setUp(self):
        self.env = {
            "ARMADA_SOC_CLASS": "SM8650", "ARMADA_PROTON_DEFAULTS": "stable: preview ",
            "ARMADA_SECONDARY_CONNECTOR": "DSI-1", "ARMADA_SECONDARY_TOUCHSCREEN": "touch",
            "ARMADA_SUSPEND_MODE": "fake",
        }
        self.factory = power.parse_power(ROOT / "system_files/usr/share/armada/power-profiles.conf")
        self.power = copy.deepcopy(self.factory)
        self.power["fan"]["charging_pwm"] = "50"
        self.limits = {
            "gpuHz": [600_000_000, 800_000_000, 1_000_000_000], "gpuStockHz": 800_000_000,
            "gpuMhz": [600, 800, 1000], "gpuStockMaxMhz": 800,
            "cpuPolicies": [{"id": 0, "cpus": "0-1", "khz": [1_000_000, 1_500_000, 2_000_000],
                             "mhz": [1000, 1500, 2000]}],
            "cpuTopology": {"little": "0-1", "big": "2-6", "prime": "7"},
        }
        values = {
            "device_env": self.env,
            "freq_limits": self.limits,
            "load_fex_contract": {"profiles": {"default": {"label": "Default", "config": {}}}},
            "load_tweaks": {"global": {"nice": -1}, "games": {"620": {"enabled": False, "nice": -5}}},
            "load_tweak_defaults": {"global": {"nice": 0}, "games": {}},
            "turnip_drivers": [{"id": "stable", "label": "Stable"}], "load_env_presets": [],
            "perf_info": {"cpuCount": 8}, "rgb_supported": False,
            "installed_games": [{"appid": "1", "name": "Game"}],
            "parse_power": self.power, "charging_fan_supported": True, "panel_calibration": {"supported": True},
            "factory_power_defaults": self.factory,
            "bottom_screen_status": {"supported": True, "brightness": 25, "active": False},
            "bottom_screen_enabled": True, "ssh_enabled": False, "mtp_enabled": False,
            "swipe_gestures_enabled": True, "desktop_mode": "desktop",
            "desktop_modes": [{"data": "desktop", "label": "Plasma Desktop"}],
            "sleep_modes": [{"data": "fake", "label": "Fake"}],
            "gyro_state": {"supported": True, "enabled": True},
            "controller_type": "deck-uhid", "calibration_metadata": {"hasCalibration": False, "calibratedAt": None},
            "inputplumber_targets": ["deck-uhid"], "os_version": "OS 1", "abl_version": "ABL 1",
        }
        self.probes = {name: Mock(return_value=value) for name, value in values.items()}
        self.enterContext(patch.multiple(config, **self.probes))

    def test_initial_settings_skip_unrelated_sections_and_game_discovery(self):
        initial = config.build_initial_config()
        self.assertEqual(set(initial), INITIAL_KEYS)
        self.assertEqual(initial["installedGames"], [])
        self.assertEqual(initial["protonDefaults"], ["stable", "preview"])
        self.probes["device_env"].assert_called_once_with()
        self.probes["perf_info"].assert_called_once_with(self.env)
        for name in (
            "parse_power", "factory_power_defaults", "freq_limits", "installed_games", "os_version", "abl_version", "charging_fan_supported", "panel_calibration",
            "controller_type", "calibration_metadata", "inputplumber_targets", "gyro_state", "bottom_screen_status",
            "bottom_screen_enabled", "ssh_enabled", "mtp_enabled", "swipe_gestures_enabled",
            "desktop_mode", "desktop_modes", "sleep_modes",
        ):
            self.probes[name].assert_not_called()

    def test_section_builders_only_read_their_own_settings(self):
        cases = (
            (config.build_profiles_config, PROFILES_KEYS, {"device_env", "freq_limits", "parse_power", "factory_power_defaults"}),
            (config.build_controller_config, CONTROLLER_KEYS, {"device_env", "controller_type", "calibration_metadata", "inputplumber_targets", "gyro_state"}),
            (config.build_device_config, DEVICE_KEYS, {"parse_power", "charging_fan_supported", "panel_calibration"}),
            (config.build_experimental_config, EXPERIMENTAL_KEYS, {
                "device_env", "bottom_screen_status", "bottom_screen_enabled",
                "swipe_gestures_enabled", "mtp_enabled", "desktop_mode", "desktop_modes", "sleep_modes",
            }),
            (config.build_about_config, ABOUT_KEYS, {"os_version", "abl_version", "ssh_enabled"}),
        )
        for builder, keys, expected in cases:
            with self.subTest(builder=builder.__name__):
                for probe in self.probes.values():
                    probe.reset_mock()
                self.assertEqual(set(builder()), keys)
                for name, probe in self.probes.items():
                    if name in expected:
                        self.assertEqual(probe.call_count, 1, name)
                    else:
                        probe.assert_not_called()

    def test_full_config_keeps_legacy_shape_and_reuses_env_power_and_brightness(self):
        full = config.build_config(include_games=False)
        self.assertEqual(set(full), INITIAL_KEYS | PROFILES_KEYS | CONTROLLER_KEYS | DEVICE_KEYS | EXPERIMENTAL_KEYS | ABOUT_KEYS)
        self.assertEqual(full["power"]["fan"]["charging_pwm"], "50")
        self.assertEqual(full["chargingFanPwm"], 50)
        self.assertTrue(full["chargingFanSupported"])
        self.assertEqual(full["bottomScreenBrightness"], 25)
        self.assertEqual(full["tweaks"]["global"]["nice"], -1)
        self.assertEqual(full["tweaksDefaults"]["global"]["nice"], 0)
        self.assertEqual(full["tweaks"]["games"]["620"], {"enabled": False, "nice": -5})
        self.assertEqual(full["tweaksDefaults"]["games"], {})
        self.assertEqual(full["gyro"], {"supported": True, "enabled": True})
        self.assertEqual(full["controllerTypes"], [{"data": "deck-uhid", "label": "Steam Deck"}])
        self.probes["device_env"].assert_called_once_with()
        self.probes["perf_info"].assert_called_once_with(self.env)
        self.probes["freq_limits"].assert_called_once_with(self.env)
        self.probes["inputplumber_targets"].assert_called_once_with(self.env)
        self.probes["parse_power"].assert_called_once_with()
        self.probes["bottom_screen_status"].assert_called_once_with()
        self.probes["installed_games"].assert_not_called()
        self.assertEqual(config.build_config()["installedGames"], [{"appid": "1", "name": "Game"}])

    def test_section_reloads_observe_external_settings_changes(self):
        self.assertEqual(config.build_initial_config()["tweaks"]["global"]["nice"], -1)
        self.probes["load_tweaks"].return_value = {"global": {"nice": -8}, "games": {}}
        self.assertEqual(config.build_initial_config()["tweaks"]["global"]["nice"], -8)
        self.assertEqual(config.build_profiles_config()["power"]["fan"]["charging_pwm"], "50")
        self.probes["parse_power"].return_value = {**copy.deepcopy(self.power), "fan": {"charging_pwm": "75"}}
        self.assertEqual(config.build_profiles_config()["power"]["fan"]["charging_pwm"], "75")
        self.assertFalse(config.build_about_config()["sshEnabled"])
        self.probes["ssh_enabled"].return_value = True
        self.probes["bottom_screen_status"].return_value = {"supported": True, "brightness": 90, "active": True}
        changed = config.build_experimental_config()
        self.assertEqual(changed["bottomScreenBrightness"], 90)
        device = config.build_device_config()
        self.assertTrue(config.build_about_config()["sshEnabled"])
        self.assertEqual(device["chargingFanPwm"], 75)
        self.probes["charging_fan_supported"].return_value = False
        self.assertFalse(config.build_device_config()["chargingFanSupported"])
        self.assertTrue(config.build_device_config()["panelCalibrationSupported"])
        self.probes["panel_calibration"].side_effect = RuntimeError("unsupported panel")
        device = config.build_device_config()
        self.assertFalse(device["panelCalibrationSupported"])
        self.assertEqual(device["chargingFanPwm"], 75)
        self.assertIsNone(config.build_controller_config()["calibratedAt"])
        self.probes["calibration_metadata"].return_value = {"hasCalibration": True, "calibratedAt": "2026-10-24T12:00:00Z"}
        self.assertEqual(config.build_controller_config()["calibratedAt"], "2026-10-24T12:00:00Z")
        self.assertEqual(config.build_about_config()["ablVersion"], "ABL 1")
        self.probes["abl_version"].return_value = "ABL 2"
        self.assertEqual(config.build_about_config()["ablVersion"], "ABL 2")

    def test_profile_scope_preserves_effective_live_and_factory_frequency_limits(self):
        self.power["profiles"]["balanced"].update({
            "gpu_max_mhz": 600, "gpu_min_mhz": 1000, "cpu_max_policy0": 1_000_000,
        })
        section = config.build_profiles_config()
        live = section["power"]["profiles"]["balanced"]
        factory = section["powerDefaults"]["profiles"]["balanced"]
        self.assertEqual((live["gpu_max_mhz"], live["gpu_min_mhz"], live["cpu_max_policy0"]), (600, 600, 1_000_000))
        self.assertEqual((factory["gpu_max_mhz"], factory["gpu_min_mhz"], factory["cpu_max_policy0"]), (800, 600, 1_500_000))
        self.assertEqual(section["freqLimits"], {key: self.limits[key] for key in (
            "gpuMhz", "gpuStockMaxMhz", "cpuPolicies", "cpuTopology",
        )})
        self.probes["freq_limits"].assert_called_once_with(self.env)
        self.assertEqual(section["power"]["fan_curves"], section["powerDefaults"]["fan_curves"])

    def test_rpc_endpoints_dispatch_to_scoped_builders_and_keep_legacy_save_responses(self):
        plugin = load_module("armada_control_plugin", ROOT / "decky/armada-control/main.py")
        instance = plugin.Plugin()
        for name in ("initial", "profiles", "controller", "device", "experimental", "about"):
            with self.subTest(section=name):
                response = {"section": name}
                with patch.object(plugin, f"build_{name}_config", return_value=response) as builder:
                    self.assertEqual(asyncio.run(getattr(instance, f"get_{name}_config")()), response)
                builder.assert_called_once_with()
        with patch.object(plugin, "build_config", return_value={"full": True}) as builder:
            with patch.object(plugin, "save_tweaks") as save:
                self.assertEqual(asyncio.run(instance.save_tweaks({"global": {}, "games": {}})), {"full": True})
                save.assert_called_once_with({"global": {}, "games": {}})
            builder.assert_called_once_with(False)
        with patch.object(plugin, "build_config", return_value={"full": True}) as builder:
            with patch.object(plugin, "save_power_profile") as save:
                self.assertEqual(asyncio.run(instance.save_power_profile("eco", {"cpu_max": "0.5"})), {"full": True})
                save.assert_called_once_with("eco", {"cpu_max": "0.5"})
            builder.assert_called_once_with(False)
        with patch.object(plugin, "patch_tweaks", return_value={"global": {"nice": -2}, "games": {}}) as save:
            with patch.object(plugin, "build_config", side_effect=AssertionError("unrelated probes")):
                changes = [{"path": ["global", "nice"], "value": -2}]
                self.assertEqual(asyncio.run(instance.patch_tweaks(changes)), {
                    "tweaks": {"global": {"nice": -2}, "games": {}},
                })
            save.assert_called_once_with(changes)


class TweaksPersistenceTest(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.defaults = Path(directory) / "defaults.json"
        self.overrides = Path(directory) / "overrides.json"
        self.defaults.write_text(json.dumps({"global": {"nice": 0, "env": {"GLOBAL": "1"}}, "games": {}}))
        self.writes = []
        self.enterContext(patch.object(tweaks.armada_game_tweaks, "DEFAULTS_CONFIG", self.defaults))
        self.enterContext(patch.object(tweaks.armada_game_tweaks, "OVERRIDES_CONFIG", self.overrides))
        self.enterContext(patch.object(tweaks, "call", self.write_config))

    def write_config(self, action, **payload):
        self.assertEqual((action, payload["name"]), ("write_config", "tweaks"))
        self.overrides.write_text(payload["text"])
        self.writes.append(payload["text"])

    def test_factory_defaults_stay_separate_fresh_and_normalized(self):
        tweaks.save_tweaks({"global": {"nice": -10}, "games": {"620": {"enabled": False}}})
        defaults = tweaks.load_tweak_defaults()
        self.assertEqual(defaults, {"global": {"nice": 0, "env": {"GLOBAL": "1"}}, "games": {}})
        self.assertEqual(tweaks.load_tweaks()["global"]["nice"], -10)
        defaults["global"]["env"]["GLOBAL"] = "changed"
        self.assertEqual(tweaks.load_tweak_defaults()["global"]["env"], {"GLOBAL": "1"})
        self.defaults.write_text(json.dumps({"global": {"nice": -4}}))
        self.assertEqual(tweaks.load_tweak_defaults(), {"global": {"nice": -4}, "games": {}})
        self.defaults.unlink()
        self.assertEqual(tweaks.load_tweak_defaults(), {"global": {}, "games": {}})

    def test_changed_paths_keep_unrelated_updates_and_null_environment_overrides(self):
        tweaks.patch_tweaks([
            {"path": ["games", "1", "env", "GLOBAL"], "value": None},
            {"path": ["games", "1", "nice"], "value": 0},
            {"path": ["global", "futureOption"], "value": "kept"},
        ])
        tweaks.patch_tweaks([{"path": ["global", "nice"], "value": -5}])
        saved = tweaks.patch_tweaks([{"path": ["games", "2", "steamCompatTool"], "value": "proton"}])
        self.assertEqual(saved["global"]["nice"], -5)
        self.assertEqual(saved["global"]["futureOption"], "kept")
        self.assertEqual(saved["games"]["1"], {"nice": 0, "env": {"GLOBAL": None}})
        self.assertEqual(saved["games"]["2"]["steamCompatTool"], "proton")
        self.assertNotIn("GLOBAL", tweaks.armada_game_tweaks.merged_settings(saved, "1")["env"])

    def test_explicit_removals_restore_defaults_and_delete_game_profiles(self):
        tweaks.patch_tweaks([
            {"path": ["global", "nice"], "value": -5},
            {"path": ["games", "1"], "value": {"nice": -2, "env": {"OVERRIDE": "1"}}},
        ])
        saved = tweaks.patch_tweaks([
            {"path": ["global", "nice"], "remove": True},
            {"path": ["games", "1", "env", "OVERRIDE"], "remove": True},
        ])
        self.assertEqual(saved["global"]["nice"], 0)
        self.assertEqual(saved["games"]["1"], {"nice": -2, "env": {}})
        self.assertEqual(tweaks.patch_tweaks([{"path": ["games", "1"], "remove": True}])["games"], {})
        count = len(self.writes)
        self.assertEqual(tweaks.patch_tweaks([]), tweaks.load_tweaks())
        self.assertEqual(len(self.writes), count)

    def test_invalid_changes_never_write_partial_updates(self):
        for invalid in (
            None, {}, [None], [{"path": [], "value": 1}], [{"path": ["other"], "value": {}}],
            [{"path": ["games", "invalid"], "value": {}}],
            [{"path": ["global", 1], "value": 1}], [{"path": ["games"], "value": []}],
            [{"path": ["games", "1"], "value": None}],
            [{"path": ["global", "nice"], "remove": False}],
            [{"path": ["global", "nice"], "remove": True, "value": -1}],
            [{"path": ["global", "nice"]}],
        ):
            with self.subTest(changes=invalid), self.assertRaises(ValueError):
                changes = ([{"path": ["global", "nice"], "value": -1}] + invalid
                           if isinstance(invalid, list) else invalid)
                tweaks.patch_tweaks(changes)
        self.assertEqual(self.writes, [])

    def test_concurrent_patches_wait_for_legacy_writes_and_preserve_each_target(self):
        entered, release = threading.Event(), threading.Event()
        original = self.write_config

        def blocking_write(action, **payload):
            if not entered.is_set():
                entered.set()
                if not release.wait(5):
                    raise AssertionError("timed out waiting to release the write")
            original(action, **payload)

        disabled = {"enabled": False, "name": "Game", "nice": -5, "fexProfile": "fast",
                    "env": {"GLOBAL": None}, "thunks": {"Vulkan": False}, "turnipDriver": "user:driver",
                    "steamCompatTool": "preview", "steamResolution": "960x540"}
        with patch.object(tweaks, "call", blocking_write), ThreadPoolExecutor(max_workers=3) as pool:
            legacy = pool.submit(tweaks.save_tweaks, {"global": {"nice": -4}, "games": {"620": disabled}})
            self.assertTrue(entered.wait(5))
            one = pool.submit(tweaks.patch_tweaks, [{"path": ["games", "1", "nice"], "value": -1}])
            two = pool.submit(tweaks.patch_tweaks, [{"path": ["games", "2", "nice"], "value": -2}])
            self.assertFalse(one.done())
            self.assertFalse(two.done())
            release.set()
            legacy.result()
            one.result()
            two.result()
        self.assertEqual(tweaks.load_tweaks(), {
            "global": {"nice": -4, "env": {"GLOBAL": "1"}},
            "games": {"1": {"nice": -1}, "2": {"nice": -2}, "620": disabled},
        })


class SharedProbeTest(unittest.TestCase):
    def test_perf_metadata_accepts_the_current_request_environment(self):
        with patch.object(system, "device_env", side_effect=AssertionError("duplicate device environment read")):
            with patch.object(system, "read_text", return_value="userspace schedutil"):
                result = system.perf_info({"ARMADA_BIG_CORES": "2-7"})
        self.assertEqual(result["governors"], ["schedutil"])
        self.assertIn({"data": "big", "label": "Big Cores (2-7)"}, result["corePresets"])

    def test_brightness_payload_is_read_once_and_failures_remain_safe(self):
        with patch.object(system, "call", return_value={"supported": True, "brightness": 40, "active": True}) as call:
            self.assertEqual(system.bottom_screen_status(), {"supported": True, "brightness": 40, "active": True})
        call.assert_called_once_with("get_bottom_screen_brightness")
        with patch.object(system, "call", side_effect=RuntimeError("offline")):
            self.assertEqual(system.bottom_screen_status(), {"supported": False, "brightness": 0, "active": False})
            self.assertIsNone(system.bottom_screen_brightness())
            self.assertFalse(system.bottom_screen_active())


class DaemonProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.control = load_module("armada_control_service", ROOT / "system_files/usr/libexec/armada/armada-control")

    def test_brightness_and_connector_state_share_one_fresh_environment(self):
        control = self.control
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backlight = root / "backlight" / "secondary"
            backlight.mkdir(parents=True)
            (backlight / "brightness").write_text("20\n")
            (backlight / "max_brightness").write_text("100\n")
            connector = root / "drm" / "card0-DSI-1"
            connector.mkdir(parents=True)
            (connector / "enabled").write_text("enabled\n")
            env = {"ARMADA_SECONDARY_BACKLIGHT": "secondary", "ARMADA_SECONDARY_CONNECTOR": "DSI-1"}
            with patch.object(control, "BACKLIGHT_ROOT", root / "backlight"), patch.object(control, "DRM_ROOT", root / "drm"):
                with patch.object(control, "device_env", return_value=env) as probe:
                    self.assertEqual(control.action_get_bottom_screen_brightness({}), {"supported": True, "brightness": 20, "active": True})
                    probe.assert_called_once_with()
                with patch.object(control, "device_env", return_value={}) as probe:
                    self.assertEqual(control.action_get_bottom_screen_brightness({}), {"supported": False, "brightness": 0, "active": False})
                    probe.assert_called_once_with()
            self.assertEqual((backlight / "brightness").read_text(), "20\n")

    def test_missing_brightness_preference_skips_backlight_discovery_and_writes(self):
        control = self.control
        with patch.object(control, "saved_bottom_screen_brightness", return_value=None):
            with patch.object(control, "secondary_backlight") as discover, patch.object(control, "apply_bottom_screen_brightness") as apply:
                control.restore_bottom_screen_brightness()
        discover.assert_not_called()
        apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
