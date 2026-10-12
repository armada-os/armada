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
        (self.tree / 'compatible').write_bytes(b'retroidpocket,rp6\0')
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
        # Ordinary files cannot acknowledge a driver update; timeout is tested separately.
        with patch.object(policy, 'wait_parameters') as wait:
            app.main()
            if policy.uses_mcu(json.loads(self.config.read_text()).get("backend", "rsinput") if self.config.exists() else "rsinput"):
                wait.assert_called_once_with(self.params)

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
                self.assertEqual((self.params / 'axis_leftx_max').read_text(), str(span * 95 // 100))
                self.assertEqual((self.params / 'axis_leftx_center').read_text(), '0')
                self.assertEqual((self.params / 'axis_leftx_deadzone').read_text(), str(deadzone))
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
                saved = {**self.old, 'backend': backend, 'version': 2}
                self.config.write_text(json.dumps(saved))
                before = self.config.read_bytes()
                self.boot()
                self.assertEqual(self.config.read_bytes(), before)
                for key, value in saved.items():
                    if key not in ('backend', 'version'):
                        self.assertEqual((self.params / key).read_text(), str(value))

    def test_live_cleanup_uses_dt_defaults_without_touching_triggers(self):
        self.enable(1300, 17)
        for name, value in self.old.items():
            if name != 'backend':
                (self.params / name).write_text(str(value))
        policy.prepare_sticks(self.params)
        self.assertEqual((self.params / 'axis_leftx_max').read_text(), '1235')
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

    def test_mcu_opt_in_preserves_upstream_trigger_support(self):
        for board in ('retroidpocket,rp6', 'retroidpocket,rpnova', 'ayn,thor', 'ayn,odin3'):
            with self.subTest(board=board):
                (self.tree / 'compatible').write_bytes(board.encode() + b'\0')
                for opted_in in (False, True):
                    with self.subTest(opted_in=opted_in):
                        if opted_in:
                            self.enable()
                        else:
                            (self.node / 'mcu-calibration').unlink(missing_ok=True)
                            policy.mcu_node.cache_clear()
                        self.assertEqual(policy.capability('rsinput')['sticks'],
                                         'mcu' if opted_in else 'software')
                        self.assertTrue(policy.capability('rsinput')['triggers'])
        self.assertFalse(policy.capability(None)['triggers'])

    def test_config_api_cannot_reintroduce_axis_overrides(self):
        self.enable()
        app = script('armada-control')
        app.CONFIG_PATHS['calibration'] = self.config
        app.CALIBRATION_BACKENDS['rsinput'] = self.params
        with patch.object(policy, 'wait_parameters'):
            app.action_write_config({'name': 'calibration', 'text': json.dumps(self.old)})
        self.assertNotIn('axis_leftx_center', json.loads(self.config.read_text()))
        self.assertEqual((self.params / 'axis_leftx_center').read_text(), '0')
        self.assertEqual((self.params / 'axis_leftx_max').read_text(), '972')
        self.assertEqual((self.params / 'trigger_left_deadzone').read_text(), '42')

    def test_mcu_trigger_recording_preserves_stick_ownership_and_untouched_controls(self):
        self.enable()
        for board in ('retroidpocket,rp6', 'retroidpocket,rpnova', 'ayn,thor', 'ayn,odin3'):
            with self.subTest(board=board):
                (self.tree / 'compatible').write_bytes(board.encode() + b'\0')
                current = {name: 0 for name in calibration.CALIBRATION_PARAMS}
                current.update(self.old)
                state = {'backend': 'rsinput', 'canApply': True, 'controls': {}}
                capture = {'left_trigger': {'min': 0, 'max': 1497},
                           'left_x': {'min': -1000, 'max': 1000, 'rest_min': 20, 'rest_max': 20}}
                with patch.object(calibration, 'read_controller_state', return_value=state), \
                     patch.object(calibration, 'read_calibration_params', return_value=current), \
                     patch.object(calibration, 'controller_state', return_value=state), \
                     patch.object(calibration, 'calibration_status', return_value={}), \
                     patch.object(calibration, 'call') as call:
                    calibration.start_recording()
                    self.assertTrue(calibration._recording.triggers_only)
                    with patch.object(calibration._recording, 'capture', return_value=capture):
                        calibration.save_calibration()
                    saved = json.loads(call.call_args.kwargs['text'])
                self.assertFalse(any(k.startswith('axis_') for k in saved))
                self.assertEqual(saved['trigger_left_max'], 1455)
                for key in ('max', 'deadzone', 'antideadzone'):
                    self.assertEqual(saved[f'trigger_right_{key}'], current[f'trigger_right_{key}'])
                self.assertEqual(saved['version'], 2)
                calibration._ranges_stale = False

    def test_non_mcu_config_save_preserves_software_axes_and_triggers(self):
        app = self.control_app()
        app.action_write_config({'name': 'calibration', 'text': json.dumps(self.old)})
        self.assertEqual(json.loads(self.config.read_text()), self.old)
        for name, value in self.old.items():
            if name.startswith(('axis_', 'trigger_')):
                self.assertEqual((self.params / name).read_text(), str(value))

    def test_close_refresh_survives_lost_trigger_save_reply(self):
        self.enable()
        (self.tree / 'compatible').write_bytes(b'ayn,odin3\0')
        current = {name: 0 for name in calibration.CALIBRATION_PARAMS}
        current.update(self.old)
        state = {'backend': 'rsinput', 'canApply': True, 'controls': {}}
        with patch.object(calibration, 'read_controller_state', return_value=state), \
             patch.object(calibration, 'read_calibration_params', return_value=current), \
             patch.object(calibration, '_ranges_stale', False), \
             patch.object(calibration, '_recording') as recording, \
             patch.object(calibration, 'call', side_effect=RuntimeError('lost reply')):
            recording.capture.return_value = {'left_trigger': {'min': 0, 'max': 1497}}
            with self.assertRaisesRegex(RuntimeError, 'lost reply'):
                calibration.save_calibration()
            self.assertTrue(calibration._ranges_stale)

    def test_rp6_trigger_reset_uses_upstream_defaults_without_stick_overrides(self):
        self.enable()
        with patch.object(calibration, 'calibration_backend', return_value='rsinput'), \
             patch.object(calibration, 'calibration_event', return_value={}), \
             patch.object(calibration, 'device_tree_u32', return_value=0), \
             patch.object(calibration, 'read_calibration_params', return_value=dict(self.old)), \
             patch.object(calibration, 'calibration_status', return_value={}), \
             patch.object(calibration, '_ranges_stale', False), \
             patch.object(calibration, 'call') as call:
            calibration.reset_calibration_params(triggers_only=True)
            call.assert_called_once()
            self.assertEqual(call.call_args.args, ('write_config',))
            saved = json.loads(call.call_args.kwargs['text'])
            self.assertFalse(any(k.startswith('axis_') for k in saved))
            for side in ('left', 'right'):
                self.assertEqual(saved[f'trigger_{side}_max'], 1552)
                self.assertEqual(saved[f'trigger_{side}_deadzone'], 0)
                self.assertEqual(saved[f'trigger_{side}_antideadzone'], 0)
            self.assertTrue(calibration._ranges_stale)

    def control_app(self):
        app = script('armada-control')
        app.CONFIG_PATHS['calibration'] = self.config
        app.CALIBRATION_BACKENDS['rsinput'] = self.params
        return app

    def test_boot_applies_the_outer_margin_without_a_saved_config(self):
        self.enable()
        self.config.unlink(missing_ok=True)
        self.boot()
        self.assertEqual(policy.STICK_OUTER_MARGIN_PERCENT, 5)
        for axis in ('leftx', 'lefty', 'rightx', 'righty'):
            self.assertEqual((self.params / f'axis_{axis}_max').read_text(), '972')
            self.assertEqual((self.params / f'axis_{axis}_min').read_text(), '-972')
        self.assertFalse(self.config.exists())

    def test_boot_and_trigger_save_tolerate_a_late_metadata_acknowledgement(self):
        self.enable()
        self.config.write_text(json.dumps(self.old))
        boot = script('apply-input-calibration')
        boot.CONFIG = self.config
        boot.CALIBRATION_BACKENDS = {'rsinput': self.params}
        late = RuntimeError('Controller did not activate the stick ranges')
        with patch.object(policy, 'wait_parameters', side_effect=late):
            boot.main()
            self.control_app().action_write_config({'name': 'calibration', 'text': json.dumps(self.old)})
        self.assertEqual((self.params / 'update_params').read_text(), '1')

    def test_saved_axes_are_inert_at_boot_save_and_close(self):
        self.enable()
        app = self.control_app()
        self.config.write_text(json.dumps(self.old))
        self.boot()
        self.assertEqual((self.params / 'axis_leftx_max').read_text(), '972')
        self.assertEqual(json.loads(self.config.read_text()), self.old)
        with patch.object(policy, 'wait_parameters'), patch.object(mcu, 'write_calibration') as write:
            app.action_write_config({'name': 'calibration', 'text': json.dumps(self.old)})
            write.assert_not_called()
        cleaned = json.loads(self.config.read_text())
        self.assertEqual(cleaned, {k: v for k, v in self.old.items() if not k.startswith('axis_')})
        self.boot()
        self.assertEqual((self.params / 'axis_leftx_max').read_text(), '972')
        # Simulate stale live settings on Close; defaults must replace them.
        (self.params / 'axis_leftx_max').write_text('1003')
        app.RSINPUT_CALIBRATION.state = 'ready'
        def ack(parameters):
            self.assertEqual((parameters / 'axis_leftx_max').read_text(), '972')
            self.assertEqual((parameters / 'trigger_left_deadzone').read_text(), '42')
        with patch.object(policy, 'wait_parameters', side_effect=ack), \
             patch.object(app, 'unit_active', return_value=True), patch.object(app, 'run') as run:
            app.action_reload_input_ranges({})
            self.assertEqual(run.call_count, 2)
        self.assertEqual(app.RSINPUT_CALIBRATION.state, 'cancelled')

    def test_persistence_failure_does_not_mutate_live_settings(self):
        self.enable()
        app = self.control_app()
        before = self.config.read_bytes()
        with patch.object(app.os, 'fsync', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                app.action_write_config({'name': 'calibration', 'text': json.dumps(self.old)})
        self.assertEqual(self.config.read_bytes(), before)
        self.assertFalse((self.params / 'update_params').exists())

    def test_sensor_capture_and_apply_exclude_software_config_changes(self):
        self.enable()
        app = self.control_app()
        for state in ('measuring', 'measured', 'ready', 'applying'):
            app.RSINPUT_CALIBRATION.state = state
            with self.assertRaisesRegex(RuntimeError, 'Finish or cancel'):
                app.action_write_config({'name': 'calibration', 'text': json.dumps(self.old)})
        with self.assertRaisesRegex(RuntimeError, 'still applying'):
            app.action_reload_input_ranges({})

    def test_metadata_timeout_prevents_consumer_restart_and_close_can_retry(self):
        self.enable()
        app = self.control_app()
        with patch.object(policy.time, 'monotonic', side_effect=[0, 1]), patch.object(app, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'did not activate'):
                app.action_reload_input_ranges({})
            run.assert_not_called()
        with patch.object(policy, 'wait_parameters'), patch.object(app, 'unit_active', return_value=True), \
             patch.object(app, 'run') as run:
            app.action_reload_input_ranges({})
            self.assertEqual(run.call_count, 2)

    def test_close_refresh_survives_lost_trigger_reset_reply(self):
        self.enable()
        (self.tree / 'compatible').write_bytes(b'ayn,odin3\0')
        with patch.object(calibration, 'calibration_backend', return_value='rsinput'), \
             patch.object(calibration, 'calibration_event', return_value={}), \
             patch.object(calibration, 'read_calibration_params', return_value=self.old), \
             patch.object(calibration, '_ranges_stale', False), \
             patch.object(calibration, 'call', side_effect=RuntimeError('lost reply')):
            with self.assertRaisesRegex(RuntimeError, 'lost reply'):
                calibration.reset_calibration_params(triggers_only=True)
            self.assertTrue(calibration._ranges_stale)

    def test_missing_transport_cannot_start_or_fall_back_to_software(self):
        self.enable()
        manager = mcu.CalibrationManager()
        with patch.object(policy, 'device_path', return_value=None):
            self.assertEqual(policy.capability('rsinput'),
                             {'sticks': 'mcu', 'available': False, 'triggers': True})
            with self.assertRaisesRegex(RuntimeError, 'unavailable'):
                manager.dispatch('start', 'missing-transport')
            with patch.object(calibration, 'calibration_backend', return_value='rsinput'):
                with self.assertRaisesRegex(RuntimeError, 'managed by the MCU'):
                    calibration.reset_calibration_params()


if __name__ == '__main__':
    unittest.main()
