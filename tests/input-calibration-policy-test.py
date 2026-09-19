#!/usr/bin/env python3
"""Upgrade isolation and persistent-write failure regression tests (no hardware)."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'system_files/usr/lib/armada'))
sys.path.insert(0, str(ROOT / 'decky/armada-control/py_modules'))
import input_calibration_policy as policy
import rsinput_calibration as mcu
from armada_control import calibration


def script(name):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / 'system_files/usr/libexec/armada' / name))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tree = self.root / 'dt'
        self.node = self.tree / 'soc/serial/gamepad'
        self.node.mkdir(parents=True)
        (self.node / 'compatible').write_bytes(b'gamepad,rsinput\0')
        self.params = self.root / 'params'
        self.params.mkdir()
        self.config = self.root / 'calibration.json'
        self.old = {'backend': 'rsinput', 'axis_leftx_center': 123, 'axis_leftx_max': 900,
                    'axis_leftx_deadzone': 80, 'axis_leftx_antideadzone': 19,
                    'trigger_left_max': 1400, 'trigger_left_deadzone': 42,
                    'trigger_left_antideadzone': 3, 'trigger_right_max': 1490,
                    'trigger_right_deadzone': 45, 'trigger_right_antideadzone': 4}
        self.config.write_text(json.dumps(self.old))
        self.enterContext(patch.object(policy, 'DEVICE_TREE', self.tree))
        policy.mcu_node.cache_clear()
        self.addCleanup(policy.mcu_node.cache_clear)

    def enable(self, span=1024, deadzone=0):
        (self.node / 'mcu-calibration').touch()
        (self.node / 'axis-range').write_bytes(span.to_bytes(4, 'big'))
        (self.node / 'axis-deadzone').write_bytes(deadzone.to_bytes(4, 'big'))
        policy.mcu_node.cache_clear()

    def boot(self):
        app = script('apply-input-calibration')
        app.CONFIG = self.config
        app.CALIBRATION_BACKENDS = {'rsinput': self.params, 'retroid': self.params}
        app.main()

    def test_enabled_boards_drop_axes_and_preserve_all_triggers(self):
        for compatible, span, deadzone in [('retroidpocket,rp6', 1024, 0),
                                         ('retroidpocket,rpnova', 1024, 0),
                                         ('ayn,odin3', 1024, 0), ('ayn,thor', 1408, 0)]:
            with self.subTest(compatible=compatible):
                (self.tree / 'compatible').write_bytes(compatible.encode() + b'\0')
                self.enable(span, deadzone)
                self.config.write_text(json.dumps(self.old))
                self.boot()
                self.assertEqual(json.loads(self.config.read_text()), self.old)
                self.assertFalse(any(p.name.startswith('axis_') for p in self.params.iterdir()))
                for name, value in self.old.items():
                    if name.startswith('trigger_'):
                        self.assertEqual((self.params / name).read_text(), str(value))

    def test_disabled_boards_and_retroid_keep_legacy_settings(self):
        for backend, opted_in, disabled in [('rsinput', False, False), ('retroid', True, False),
                                           ('rsinput', True, True)]:
            with self.subTest(backend=backend, opted_in=opted_in, disabled=disabled):
                if opted_in:
                    self.enable()
                if disabled:
                    (self.node.parent / 'status').write_bytes(b'disabled\0')
                policy.mcu_node.cache_clear()
                saved = {**self.old, 'backend': backend}
                self.config.write_text(json.dumps(saved))
                before = self.config.read_bytes()
                self.boot()
                self.assertEqual(self.config.read_bytes(), before)
                for key, value in saved.items():
                    if key != 'backend':
                        self.assertEqual((self.params / key).read_text(), str(value))

    def test_live_cleanup_uses_dt_defaults_without_touching_triggers(self):
        self.enable(1300, 17)
        for name, value in self.old.items():
            if name != 'backend':
                (self.params / name).write_text(str(value))
        policy.prepare_sticks(self.params)
        self.assertEqual((self.params / 'axis_leftx_max').read_text(), '1300')
        self.assertEqual((self.params / 'axis_leftx_deadzone').read_text(), '17')
        self.assertEqual((self.params / 'trigger_left_antideadzone').read_text(), '3')
        self.assertTrue(policy.uses_mcu('rsinput'))
        self.assertFalse(policy.uses_mcu('retroid'))
        with patch.object(calibration, 'calibration_backend', return_value='rsinput'):
            with self.assertRaisesRegex(RuntimeError, 'managed by the MCU'):
                calibration.reset_calibration_params()
        # Absence of a misc node does not reactivate legacy software calibration.
        with patch.object(policy, 'device_path', return_value=None):
            self.assertEqual(policy.capability('rsinput')['sticks'], 'mcu')
            self.assertFalse(policy.capability('rsinput')['available'])

    def test_non_opted_in_board_keeps_legacy_trigger_support(self):
        (self.tree / 'compatible').write_bytes(b'retroidpocket,rp6\0')
        self.assertEqual(policy.capability('rsinput')['sticks'], 'software')
        self.assertTrue(policy.capability('rsinput')['triggers'])
        self.enable()
        self.assertFalse(policy.capability('rsinput')['triggers'])

    def test_config_api_cannot_reintroduce_axis_overrides(self):
        self.enable()
        app = script('armada-control')
        app.CONFIG_PATHS['calibration'] = self.config
        app.CALIBRATION_BACKENDS['rsinput'] = self.params
        app.action_write_config({'name': 'calibration', 'text': json.dumps(self.old)})
        self.assertNotIn('axis_leftx_center', json.loads(self.config.read_text()))
        self.assertFalse((self.params / 'axis_leftx_center').exists())
        self.assertEqual((self.params / 'trigger_left_deadzone').read_text(), '42')



if __name__ == '__main__':
    unittest.main()
