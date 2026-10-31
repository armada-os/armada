import copy
import importlib.machinery
import importlib.util
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
sys.path.insert(0, str(ROOT / "decky/armada-control/py_modules"))

from armada_control import fan_curves, power
import armada_fan
from armada_fan import FAN_DEFAULTS


loader = importlib.machinery.SourceFileLoader(
    "armada_powerd", str(ROOT / "system_files/usr/libexec/armada/armada-powerd")
)
spec = importlib.util.spec_from_loader(loader.name, loader)
powerd = importlib.util.module_from_spec(spec)
loader.exec_module(powerd)


class FanProfilesTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.user = Path(self.work.name) / "power.conf"
        self.factory = Path(self.work.name) / "factory.conf"
        self.factory.write_text((ROOT / "system_files/usr/share/armada/power-profiles.conf").read_text())
        self.writes = []
        for module in (fan_curves, power):
            self.enterContext(patch.object(module, "POWER_CONFIG", self.user))
            self.enterContext(patch.object(module, "FACTORY_POWER_CONFIG", self.factory))
            self.enterContext(patch.object(module, "call", self.write_config))
        self.enterContext(patch.object(fan_curves, "STATE_FILE", Path(self.work.name) / "state"))
        self.enterContext(patch.object(fan_curves, "get_current_temp", lambda: 60))
        self.enterContext(patch.object(powerd, "CONFIG_FILE", self.user))
        self.enterContext(patch.object(powerd, "FACTORY_CONFIG_FILE", self.factory))

    def write_config(self, action, **payload):
        self.assertEqual((action, payload["name"]), ("write_config", "power"))
        self.user.write_text(payload["text"])
        self.writes.append(payload["text"])

    def curve(self, name="moderate", **changes):
        return {**fan_curves.get_state()["fanCurves"][name], **changes}

    def daemon(self):
        daemon = powerd.ArmadaPower.__new__(powerd.ArmadaPower)
        (daemon.default_profile, daemon.underclock_config, daemon.fan_curves,
         daemon.profile_config, daemon.fan_config, daemon.suspend_config,
         daemon.system_config) = daemon.parse_config()
        daemon.profile = "balanced"
        daemon.last_pwm = 100
        daemon.smoothed_temp = 80.0
        daemon.fan_control_signature = None
        daemon.fan_pwm = Path(self.work.name) / "pwm1"
        daemon.fan_enable = None
        daemon.fan_hwmon = None
        daemon.connection = None
        daemon.suspended = False
        daemon.perf_tick = lambda: None
        return daemon

    def test_plugin_capability_and_daemon_discovery_share_the_same_pwm_control(self):
        root = Path(self.work.name) / "hwmon"
        root.mkdir()
        daemon = powerd.ArmadaPower.__new__(powerd.ArmadaPower)
        with patch.object(armada_fan, "HWMON_ROOT", root):
            self.assertFalse(fan_curves.charging_fan_supported())
            self.assertIsNone(daemon.discover_fan_hwmon())
            generic = root / "hwmon0"
            generic.mkdir()
            (generic / "pwm1").touch()
            (generic / "name").write_text("generic")
            self.assertTrue(fan_curves.charging_fan_supported())
            self.assertEqual(daemon.discover_fan_hwmon(), generic)
            preferred = root / "hwmon1"
            preferred.mkdir()
            (preferred / "name").write_text("pwmfan")
            self.assertEqual(daemon.discover_fan_hwmon(), generic)
            (preferred / "pwm1").touch()
            self.assertEqual(daemon.discover_fan_hwmon(), preferred)
            self.assertEqual(armada_fan.discover_fan_hwmon(), preferred)

    def test_legacy_inheritance_and_parser_agreement(self):
        self.user.write_text("[fan]\nramp_up=18\nramp_down=3\nsmoothing=0.75\nmin_pwm=40\n")
        snapshot = self.user.read_text()
        state = fan_curves.get_state()
        self.assertEqual(state["fanCurves"]["moderate"]["ramp_up"], 18)
        self.assertEqual(state["factoryFanCurves"]["moderate"]["ramp_up"], 36)
        parsed = power.parse_power()
        daemon = self.daemon()
        for name, curve in state["fanCurves"].items():
            self.assertEqual(parsed["fan_curves"][name], curve)
            for key in FAN_DEFAULTS:
                self.assertEqual(daemon.fan_curves[name][key], curve[key])
        self.assertEqual(self.user.read_text(), snapshot)

    def test_legacy_clamping_preserves_overrides_without_recovery(self):
        for values, expected in (
            ("smoothing=1.0\nmin_pwm=-1", {"smoothing": 0.99, "min_pwm": 0}),
            ("smoothing=-0.5\nmin_pwm=300", {"smoothing": 0.0, "min_pwm": 255}),
            ("ramp_up=0\nramp_down=300", {"ramp_up": 1, "ramp_down": 255}),
        ):
            with self.subTest(values=values):
                self.user.write_text(f"[fan]\n{values}\n[profile.eco]\ncpu_max=0.42\n"
                                     "[fan_curve.custom]\ncurve=0:70,80:255\n")
                snapshot = self.user.read_text()
                parsed = power.parse_power()
                daemon = powerd.ArmadaPower.__new__(powerd.ArmadaPower)
                daemon.load_config()
                state = fan_curves.get_state()
                self.assertEqual(parsed["profiles"]["eco"]["cpu_max"], "0.42")
                self.assertEqual(daemon.profile_config["eco"]["cpu_max"], 0.42)
                self.assertIn("custom", parsed["fan_curves"])
                self.assertIn("custom", daemon.fan_curves)
                for key, value in expected.items():
                    self.assertEqual(parsed["fan_curves"]["custom"][key], value)
                    self.assertEqual(state["fanCurves"]["custom"][key], value)
                    self.assertEqual(daemon.fan_config[key], value)
                self.assertEqual(self.user.read_text(), snapshot)
                self.assertEqual(list(self.user.parent.glob("power.conf.invalid-*")), [])
                self.assertEqual(self.writes, [])

    def test_targeted_upsert_preserves_other_settings_and_curves(self):
        self.user.write_text("[fan]\ncharging_pwm=80\n[profile.eco]\ncpu_max=0.75\n"
                             "[fan_curve.custom]\nlabel=Other\ncurve=0:70,80:255\n"
                             "ramp_up=12\n[system]\nirq_cores=all\n")
        before = fan_curves.get_state()["fanCurves"]["custom"]
        state = fan_curves.save_all({"moderate": self.curve(smoothing=0.85, min_pwm=65)})
        self.assertEqual(state["fanCurves"]["custom"], before)
        self.assertEqual(state["fanCurves"]["relaxed"]["min_pwm"], 51)
        parser = fan_curves._read(self.user)
        self.assertEqual(parser.getint("fan", "charging_pwm"), 80)
        self.assertEqual(parser.get("system", "irq_cores"), "all")
        self.assertEqual(parser.get("profile.eco", "cpu_max"), "0.75")
        self.assertEqual(set(parser.options("fan_curve.moderate")), {"smoothing", "min_pwm"})

    def test_reset_removes_only_unneeded_overrides(self):
        fan_curves.save_all({"moderate": self.curve(ramp_down=20, curve="0:60,80:255")})
        factory = fan_curves.get_state()["factoryFanCurves"]["moderate"]
        fan_curves.save_all({"moderate": factory})
        self.assertFalse(fan_curves._read(self.user).has_section("fan_curve.moderate"))

    def test_factory_reset_overrides_different_legacy_global_values(self):
        self.user.write_text("[fan]\nmin_pwm=0\nramp_up=19\n")
        factory = fan_curves.get_state()["factoryFanCurves"]["moderate"]
        state = fan_curves.save_all({"moderate": factory})
        parser = fan_curves._read(self.user)
        self.assertEqual(parser.getint("fan_curve.moderate", "min_pwm"), 51)
        self.assertEqual(parser.getint("fan_curve.moderate", "ramp_up"), 36)
        self.assertEqual(parser.getint("fan", "min_pwm"), 0)
        self.assertEqual(state["fanCurves"]["moderate"], factory)

    def test_explicit_factory_curve_setting_is_reset_baseline(self):
        self.factory.write_text(self.factory.read_text().replace(
            "[fan_curve.moderate]\n", "[fan_curve.moderate]\nramp_up=50\n"
        ))
        self.user.write_text("[fan]\nramp_up=19\n[fan_curve.moderate]\nramp_up=60\n")
        state = fan_curves.save_all({"moderate": fan_curves.get_state()["factoryFanCurves"]["moderate"]})
        self.assertEqual(state["fanCurves"]["moderate"]["ramp_up"], 50)
        self.assertFalse(fan_curves._read(self.user).has_section("fan_curve.moderate"))

    def test_fan_stop_preserves_configured_minimum_and_other_curves(self):
        state = fan_curves.save_all({"moderate": self.curve(curve="0:0,60:70,90:255", min_pwm=63)})
        self.assertEqual(state["fanCurves"]["moderate"]["min_pwm"], 63)
        self.assertFalse(fan_curves._read(self.user).has_section("fan"))
        daemon = self.daemon()
        self.assertEqual(daemon.active_fan_settings()["min_pwm"], 0)
        self.assertEqual(daemon.target_pwm(0), 0)
        daemon.profile = "eco"
        self.assertEqual(daemon.active_fan_settings()["min_pwm"], 51)
        self.assertGreaterEqual(daemon.target_pwm(0), 51)

    def test_delete_requires_explicit_unassigned_custom_id(self):
        fan_curves.save_all({"custom": self.curve(label="Custom")})
        fan_curves.save_all({"moderate": self.curve(smoothing=0.8)})
        self.assertIn("custom", fan_curves.get_state()["fanCurves"])
        state = fan_curves.save_all({}, ["custom"])
        self.assertNotIn("custom", state["fanCurves"])
        for deleted in (["moderate"], ["missing"], ["bad\nname"], "custom", [None]):
            with self.subTest(deleted=deleted), self.assertRaises(ValueError):
                fan_curves.save_all({}, deleted)
        fan_curves.save_all({"custom": self.curve()})
        self.user.write_text(self.user.read_text() + "\n[profile.eco]\nfan_curve=custom\n")
        with self.assertRaisesRegex(ValueError, "still assigned"):
            fan_curves.save_all({}, ["custom"])
        with self.assertRaisesRegex(ValueError, "save and delete"):
            fan_curves.save_all({"custom": self.curve()}, ["custom"])

    def test_normalized_curve_assignments_still_block_deletion(self):
        fan_curves.save_all({"custom": self.curve(label="Custom")})
        self.user.write_text(self.user.read_text() + "\n[profile.eco]\nfan_curve= CuStOm \n")
        snapshot = self.user.read_text()
        self.assertEqual(fan_curves.get_state()["profiles"]["eco"]["fan_curve"], "custom")
        self.assertEqual(self.daemon().profile_config["eco"]["fan_curve"], "custom")
        with self.assertRaisesRegex(ValueError, "still assigned"):
            fan_curves.save_all({}, ["custom"])
        self.assertEqual(self.user.read_text(), snapshot)
        self.assertEqual(len(self.writes), 1)

    def test_invalid_values_never_write(self):
        invalid = {"ramp_up": (0, 256, 1.5, True, None),
                   "ramp_down": (-1, "oops"), "min_pwm": (-1, 256, 2.5),
                   "smoothing": (-0.01, 1, float("nan"), float("inf"), True),
                   "label": ("bad\nlabel", "a" * 81),
                   "curve": ("", "200:255", "0:300", "garbage")}
        for key, values in invalid.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    fan_curves.save_all({"moderate": self.curve(**{key: value})})
        for name in ("Bad", "bad-name", "bad\n", "a" * 33, 1):
            with self.subTest(name=name), self.assertRaises(ValueError):
                fan_curves.save_all({name: self.curve()})
        incomplete = self.curve()
        del incomplete["ramp_up"]
        with self.assertRaises(ValueError):
            fan_curves.save_all({"moderate": incomplete})
        self.assertEqual(self.writes, [])

    def test_equal_temperature_steps_save_and_reload_like_main(self):
        for value in ("40:100,40:0,90:255", "40:0,40:100,90:255", "40:100,40:100"):
            with self.subTest(curve=value):
                fan_curves.save_all({"moderate": self.curve(curve=value, ramp_up=12)})
                saved = fan_curves.get_state()["fanCurves"]["moderate"]
                self.assertEqual(saved["curve"], value)
                self.assertEqual(saved["ramp_up"], 12)

    def test_legacy_duplicate_temperatures_keep_runtime_order(self):
        self.user.write_text("[fan_curve.moderate]\ncurve=40:100,40:0,90:255\n")
        snapshot = self.user.read_text()
        state = fan_curves.get_state()
        self.assertEqual(state["fanCurves"]["moderate"]["curve"], "40:100,40:0,90:255")
        daemon = self.daemon()
        self.assertEqual(daemon.active_fan_settings()["min_pwm"], 0)
        self.assertEqual(daemon.target_pwm(30), 0)
        self.assertEqual(self.user.read_text(), snapshot)

    def test_parsers_reject_invalid_curve_settings(self):
        for setting in ("ramp_up=1.5", "ramp_down=oops", "min_pwm=inf", "smoothing=NaN"):
            self.user.write_text(f"[fan_curve.moderate]\n{setting}\n")
            with self.subTest(setting=setting):
                with self.assertRaises(ValueError):
                    power.parse_power(repair=False)
                with self.assertRaises(ValueError):
                    fan_curves.get_state()
                with self.assertRaises(ValueError):
                    self.daemon()

    def test_read_clamping_agrees_for_named_curve_overrides(self):
        self.user.write_text("[fan_curve.moderate]\nramp_up=0\nramp_down=256\n"
                             "min_pwm=-1\nsmoothing=1.0\n")
        state = fan_curves.get_state()["fanCurves"]["moderate"]
        parsed = power.parse_power()["fan_curves"]["moderate"]
        daemon = self.daemon().fan_curves["moderate"]
        for key, value in {"ramp_up": 1, "ramp_down": 255, "min_pwm": 0, "smoothing": 0.99}.items():
            self.assertEqual(state[key], value)
            self.assertEqual(parsed[key], value)
            self.assertEqual(daemon[key], value)

    def test_individual_settings_ramp_and_reset_on_effective_change(self):
        fan_curves.save_all({"moderate": self.curve(
            curve="0:80,100:160", ramp_up=10, ramp_down=4, smoothing=0.8, min_pwm=60
        )})
        daemon = self.daemon()
        daemon.read_temp = lambda: 100
        daemon.sync_fan_settings()
        daemon.smoothed_temp = 20.0
        daemon.fan_tick()
        self.assertAlmostEqual(daemon.smoothed_temp, 36.0)
        self.assertEqual(daemon.last_pwm, 110)
        daemon.fan_curves["moderate"]["smoothing"] = 0.5
        daemon.fan_tick()
        self.assertEqual(daemon.smoothed_temp, 100)
        self.assertEqual(daemon.last_pwm, 120)
        daemon.read_temp = lambda: 1
        daemon.smoothed_temp = 0
        daemon.fan_tick()
        self.assertEqual(daemon.last_pwm, 116)
        daemon.profile = "eco"
        daemon.sync_fan_settings()
        self.assertEqual(daemon.smoothed_temp, 0)
        self.assertEqual(daemon.last_pwm, 116)
        daemon.smoothed_temp = 70
        daemon.sync_fan_settings()
        self.assertEqual(daemon.smoothed_temp, 70)

    def test_quantization_hardware_limits_and_legacy_inline_curve(self):
        fan_curves.save_all({"moderate": self.curve(min_pwm=70)})
        daemon = self.daemon()
        self.assertEqual(daemon.quantize_pwm(0), 70)
        self.assertEqual(daemon.quantize_pwm(77), 80)
        self.assertEqual(daemon.quantize_pwm(999), 255)
        daemon.profile_config["balanced"]["fan_curve"] = [(0, 0), (100, 255)]
        self.assertEqual(daemon.active_fan_settings()["min_pwm"], 51)
        self.assertEqual(daemon.target_pwm(0), 51)
        self.user.write_text(self.user.read_text() + "\n[profile.balanced]\nfan_curve=0:0,100:255\n")
        self.assertIsInstance(self.daemon().profile_settings()["fan_curve"], list)

    def test_suspend_charging_and_missing_sensor_safety(self):
        fan_curves.save_all({"moderate": self.curve(curve="0:0,90:255", min_pwm=60)})
        daemon = self.daemon()
        daemon.suspended = True
        daemon.read_temp_max = lambda: 0
        daemon.fan_tick()
        self.assertEqual(daemon.last_pwm, 128)
        daemon.read_temp_max = lambda: 30
        daemon.fan_config["charging_pwm"] = 90
        with patch.object(powerd, "external_power_online", lambda: True):
            daemon.fan_tick()
        self.assertEqual(daemon.last_pwm, 90)
        daemon.suspended = False
        daemon.read_temp = lambda: 0
        daemon.fan_tick()
        self.assertEqual(daemon.last_pwm, 126)
        daemon.fan_tick()
        self.assertEqual(daemon.last_pwm, 128)
        daemon.read_temp = lambda: 1
        daemon.smoothed_temp = 0
        daemon.last_pwm = 128
        with patch.object(powerd, "external_power_online", lambda: True):
            for _ in range(12):
                daemon.fan_tick()
        self.assertEqual(daemon.last_pwm, 90)

    def test_fan_power_and_charging_saves_share_one_lock(self):
        entered = threading.Event()
        release = threading.Event()
        first = True

        def delayed_write(action, **payload):
            nonlocal first
            if first:
                first = False
                entered.set()
                self.assertTrue(release.wait(5))
            self.write_config(action, **payload)

        data = copy.deepcopy(power.parse_power())
        data["profiles"]["eco"]["cpu_max"] = "0.7"
        custom = self.curve(ramp_up=12)
        with patch.object(fan_curves, "call", delayed_write), patch.object(power, "call", delayed_write):
            with ThreadPoolExecutor(max_workers=3) as pool:
                fans = pool.submit(fan_curves.save_all, {"custom": custom})
                self.assertTrue(entered.wait(5))
                charging = pool.submit(fan_curves.save_charging_pwm, 80)
                profiles = pool.submit(power.save_power_profile, "eco", data["profiles"]["eco"])
                self.assertFalse(charging.done())
                self.assertFalse(profiles.done())
                release.set()
                for future in (fans, charging, profiles):
                    future.result(timeout=5)
        state = fan_curves.get_state()
        self.assertEqual(state["fanCurves"]["custom"]["ramp_up"], 12)
        parser = fan_curves._read(self.user)
        self.assertEqual(parser.getint("fan", "charging_pwm"), 80)
        self.assertEqual(parser.getfloat("profile.eco", "cpu_max"), 0.7)

    def test_targeted_profile_saves_preserve_newer_unrelated_profiles_and_unknown_options(self):
        self.user.write_text("[profile.eco]\nfuture_option=kept\n")
        before = power.parse_power()
        eco = {**before["profiles"]["eco"], "cpu_max": "0.42"}
        balanced = {**before["profiles"]["balanced"], "cpu_max": "0.93"}
        power.save_power_profile("eco", eco)
        power.save_power_profile("balanced", balanced)
        saved = power.parse_power()
        self.assertEqual(saved["profiles"]["eco"]["cpu_max"], "0.42")
        self.assertEqual(saved["profiles"]["balanced"]["cpu_max"], "0.93")
        self.assertEqual(fan_curves._read(self.user).get("profile.eco", "future_option"), "kept")
        writes = len(self.writes)
        for profile_id, profile in (("missing", eco), (None, eco), ("eco", None)):
            with self.subTest(profile=profile_id), self.assertRaisesRegex(ValueError, "invalid power profile"):
                power.save_power_profile(profile_id, profile)
        self.assertEqual(len(self.writes), writes)

    def test_frequency_save_and_reset_preserve_fan_and_charging_settings(self):
        self.user.write_text("[fan]\ncharging_pwm=80\n[fan_curve.moderate]\nramp_up=12\n")
        limits = {
            "gpuHz": [400_000_000, 600_000_000, 800_000_000], "gpuStockHz": 800_000_000,
            "cpuPolicies": [{"id": 0, "khz": [800_000, 1_200_000, 1_600_000]}],
        }
        with patch.object(power, "device_env", return_value={}), patch.object(power, "freq_limits", return_value=limits):
            data = power.resolve_limits(power.parse_power(), limits, "")
            data["profiles"]["eco"].update({"gpu_max_mhz": 400, "gpu_min_mhz": 400, "cpu_max_policy0": 1_200_000})
            power.save_power_config(data)
            parser = fan_curves._read(self.user)
            self.assertEqual(parser.getint("profile.eco", "gpu_max_mhz"), 400)
            self.assertEqual(parser.getint("profile.eco", "cpu_max_policy0"), 1_200_000)
            reloaded = power.resolve_limits(power.parse_power(), limits, "")
            self.assertEqual(reloaded["profiles"]["eco"]["gpu_min_mhz"], 400)
            self.assertEqual(reloaded["profiles"]["eco"]["cpu_max_policy0"], 1_200_000)
            reloaded["profiles"]["eco"] = {
                **power.factory_power_defaults()["profiles"]["eco"], "cpu_max_policy0": None,
            }
            power.save_power_config(reloaded)
        parser = fan_curves._read(self.user)
        self.assertFalse(parser.has_section("profile.eco"))
        self.assertEqual(parser.getint("fan", "charging_pwm"), 80)
        self.assertEqual(parser.getint("fan_curve.moderate", "ramp_up"), 12)

    def test_power_save_rejects_deleted_curve_assignment(self):
        data = power.parse_power()
        data["profiles"]["eco"]["fan_curve"] = "removed"
        with self.assertRaisesRegex(ValueError, "malformed power config"):
            power.save_power_config(data)
        self.assertEqual(self.writes, [])

    def test_power_save_normalizes_names_during_unrelated_profile_edit(self):
        self.user.write_text("[profile.eco]\nfan_curve= ReLaXeD \ncpu_max=0.42\n")
        data = power.parse_power()
        self.assertEqual(data["profiles"]["eco"]["fan_curve"], "relaxed")
        data["profiles"]["balanced"]["cpu_max"] = "0.93"
        data["profiles"]["balanced"]["fan_curve"] = " MODERATE "
        power.save_power_config(data)
        parser = fan_curves._read(self.user)
        self.assertEqual(parser.get("profile.eco", "fan_curve"), "relaxed")
        self.assertEqual(parser.getfloat("profile.eco", "cpu_max"), 0.42)
        self.assertEqual(parser.get("profile.balanced", "fan_curve"), "moderate")
        self.assertEqual(parser.getfloat("profile.balanced", "cpu_max"), 0.93)
        daemon = self.daemon()
        self.assertEqual(daemon.profile_config["eco"]["fan_curve"], "relaxed")
        self.assertEqual(daemon.profile_config["balanced"]["fan_curve"], "moderate")


if __name__ == "__main__":
    unittest.main()
