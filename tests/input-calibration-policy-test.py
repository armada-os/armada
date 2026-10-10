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
from types import SimpleNamespace

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
        self.serial = self.root / 'serial'
        self.serial.write_text('test-unit-1')
        self.journals = self.root / 'journals'
        self.enterContext(patch.object(policy, 'SOC_SERIAL', self.serial))
        self.enterContext(patch.object(policy, 'JOURNAL_ROOT', self.journals))
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
            if policy.uses_mcu(json.loads(self.config.read_text()).get('backend')):
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

    def test_mcu_trigger_recording_preserves_stick_ownership_and_untouched_controls(self):
        self.enable()
        (self.tree / 'compatible').write_bytes(b'ayn,odin3\0')
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

    def test_trigger_reset_rejects_boards_without_raw_triggers(self):
        self.enable()
        (self.tree / 'compatible').write_bytes(b'retroidpocket,rp6\0')
        with patch.object(calibration, 'calibration_backend', return_value='rsinput'), \
             patch.object(calibration, 'call') as call:
            with self.assertRaisesRegex(RuntimeError, 'raw trigger support'):
                calibration.reset_calibration_params(triggers_only=True)
            call.assert_not_called()

    def output_config(self):
        return {**self.old, **policy.stick_defaults(), 'version': 2,
                'axis_leftx_center': -12, 'axis_leftx_min': -950, 'axis_leftx_max': 950,
                policy.OUTPUT_KEY: policy.output_binding()}

    def control_app(self):
        app = script('armada-control')
        app.CONFIG_PATHS['calibration'] = self.config
        app.CALIBRATION_BACKENDS['rsinput'] = self.params
        return app

    def test_bound_output_survives_boot_and_capture_but_not_another_unit_or_write(self):
        self.enable()
        saved = self.output_config()
        self.config.write_text(json.dumps(saved))
        self.boot()
        self.assertEqual((self.params / 'axis_leftx_center').read_text(), '-12')
        self.journals.mkdir()
        (self.journals / 'capture-only.json').write_text('{}')
        self.assertEqual(policy.clean_config(saved), saved)
        self.serial.write_text('test-unit-2')
        self.assertNotIn('axis_leftx_center', policy.clean_config(saved))
        self.serial.write_text('test-unit-1')
        # An empty journal already invalidates the old trim before any UART command.
        (self.journals / 'commit-new.ndjson').touch()
        clean = policy.clean_config(saved)
        self.assertNotIn('axis_leftx_center', clean)
        self.assertEqual(clean['trigger_left_deadzone'], 42)
        policy.restore_sticks(self.params, self.config)
        self.assertEqual((self.params / 'axis_leftx_center').read_text(), '0')
        self.assertEqual((self.params / 'axis_leftx_max').read_text(), '1024')

    def test_close_restores_valid_trim_and_refreshes_only_after_metadata_ack(self):
        self.enable()
        saved = self.output_config()
        self.config.write_text(json.dumps(saved))
        self.boot()
        policy.prepare_sticks(self.params)
        app = self.control_app()
        app.RSINPUT_CALIBRATION.state = 'ready'
        def ack(parameters):
            self.assertEqual((parameters / 'axis_leftx_max').read_text(), '950')
            self.assertEqual((parameters / 'trigger_left_deadzone').read_text(), '42')
        with patch.object(policy, 'wait_parameters', side_effect=ack) as wait, \
             patch.object(app, 'unit_active', return_value=True), patch.object(app, 'run') as run:
            app.action_reload_input_ranges({})
            wait.assert_called_once()
            self.assertEqual(run.call_count, 2)
        self.assertEqual(app.RSINPUT_CALIBRATION.state, 'cancelled')

    def test_output_save_rejects_stale_binding_and_malformed_ranges_without_mutation(self):
        self.enable()
        app = self.control_app()
        saved = self.output_config()
        for change in ({policy.OUTPUT_KEY: {'version': 1, 'generation': 'old'}},
                       {'axis_leftx_max': 0}, {'axis_leftx_center': True},
                       {'axis_leftx_deadzone': 950}):
            before = self.config.read_bytes()
            with self.assertRaises(ValueError):
                app.action_write_config({'name': 'calibration', 'text': json.dumps({**saved, **change})})
            self.assertEqual(self.config.read_bytes(), before)
            self.assertFalse((self.params / 'update_params').exists())

    def test_trigger_save_retains_bound_output_and_output_save_retains_triggers(self):
        self.enable()
        app = self.control_app()
        saved = self.output_config()
        app.action_write_config({'name': 'calibration', 'text': json.dumps(saved)})
        app.action_write_config({'name': 'calibration', 'text': json.dumps({**self.old, 'trigger_left_max': 1450})})
        actual = json.loads(self.config.read_text())
        self.assertEqual(actual['axis_leftx_max'], 950)
        self.assertEqual(actual[policy.OUTPUT_KEY], saved[policy.OUTPUT_KEY])
        self.assertEqual(actual['trigger_left_max'], 1450)
        self.assertEqual((self.params / 'axis_leftx_max').read_text(), '950')
        self.assertEqual((self.params / 'trigger_left_max').read_text(), '1450')

    def test_sensor_capture_and_apply_exclude_output_changes(self):
        self.enable()
        app = self.control_app()
        for state in ('measuring', 'measured', 'ready', 'applying'):
            app.RSINPUT_CALIBRATION.state = state
            with self.assertRaisesRegex(RuntimeError, 'Finish or cancel'):
                app.action_prepare_output_calibration({})
            with self.assertRaisesRegex(RuntimeError, 'Finish or cancel'):
                app.action_write_config({'name': 'calibration', 'text': json.dumps(self.old)})
        with self.assertRaisesRegex(RuntimeError, 'still applying'):
            app.action_reload_input_ranges({})

    def test_output_prepare_waits_for_neutral_ranges_without_sensor_transport(self):
        self.enable()
        app = self.control_app()
        self.boot()
        def ack(parameters):
            self.assertEqual((parameters / 'axis_leftx_center').read_text(), '0')
            self.assertEqual((parameters / 'axis_leftx_max').read_text(), '1024')
        with patch.object(policy, 'wait_parameters', side_effect=ack), \
             patch.object(mcu, 'write_calibration') as write:
            self.assertEqual(app.action_prepare_output_calibration({}), policy.output_binding())
            write.assert_not_called()
        self.assertEqual((self.params / 'trigger_left_deadzone').read_text(), '42')

    def test_output_persistence_failure_does_not_change_live_ranges(self):
        self.enable()
        app = self.control_app()
        saved = self.output_config()
        before = self.config.read_bytes()
        with patch.object(app.os, 'fsync', side_effect=OSError('disk failure')):
            with self.assertRaisesRegex(OSError, 'disk failure'):
                app.action_write_config({'name': 'calibration', 'text': json.dumps(saved)})
        self.assertEqual(self.config.read_bytes(), before)
        self.assertFalse((self.params / 'update_params').exists())

    def test_metadata_timeout_prevents_consumer_restart_and_close_can_retry(self):
        self.enable()
        app = self.control_app()
        with patch.object(policy.time, 'monotonic', side_effect=[0, 1]), \
             patch.object(app, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'did not activate'):
                app.action_reload_input_ranges({})
            run.assert_not_called()
        with patch.object(policy, 'wait_parameters'), patch.object(app, 'unit_active', return_value=True), \
             patch.object(app, 'run') as run:
            app.action_reload_input_ranges({})
            self.assertEqual(run.call_count, 2)

    def test_actual_write_invalidates_binding_before_first_transport_frame(self):
        self.enable()
        saved = self.output_config()
        transport = self.root / 'fake-transport'
        transport.touch()
        results = {(stick, phase): ({'centerWords': [32768, 32768]} if phase == 'center'
                   else {'rawSpaceCandidate': {'tableWords': [1] * 29}})
                   for stick in ('left', 'right') for phase in ('center', 'range')}
        def write(_fd, frame):
            self.assertFalse(policy.valid_output(saved))
            return len(frame)
        with patch.object(mcu, 'JOURNAL_ROOT', self.journals), \
             patch.object(policy, 'device_path', return_value=transport), \
             patch.object(mcu.os, 'write', side_effect=write) as send, patch.object(mcu.time, 'sleep'):
            mcu.write_calibration('synthetic-offline-test', results)
            self.assertEqual(send.call_count, 8)
        self.assertFalse(policy.valid_output(saved))

    def test_output_recording_requires_both_sticks_and_ignores_triggers(self):
        self.enable()
        recording = calibration.Recording(policy.stick_defaults(), sticks_only=True)
        now = 0
        def sample(left, right):
            nonlocal now
            for _ in range(8):
                controls = {key: {'value': value, 'min': -1024, 'max': 1024}
                            for key, value in zip(calibration.AXIS_PARAMS, (*left, *right))}
                controls['left_trigger'] = {'value': 1500, 'min': 0, 'max': 1500}
                recording.sample(controls, now)
                now += 0.1
        sample((12, -6), (0, 0))
        for value in ((-1000, 0), (1000, 0), (0, -1000), (0, 1000)):
            sample(value, (0, 0))
            sample((12, -6), (0, 0))
        self.assertFalse(recording.progress()['ready'])
        for value in ((-1000, 0), (1000, 0), (0, -1000), (0, 1000)):
            sample((12, -6), value)
            sample((12, -6), (0, 0))
        self.assertTrue(recording.progress()['ready'])
        self.assertNotIn('left_trigger', recording.capture())
        derived = calibration.calibration_from_capture(recording.capture())
        self.assertEqual(derived['axis_leftx_center'], -12)
        self.assertEqual(derived['axis_leftx_max'], 938)
        self.assertEqual(derived['axis_rightx_max'], 950)

    def test_rp6_output_save_uses_upstream_margin_despite_disabled_trigger_calibration(self):
        self.enable()
        capture = {key: {'min': -1000, 'max': 1000, 'rest_min': 0, 'rest_max': 0}
                   for key in calibration.AXIS_PARAMS}
        current = {**self.old, **policy.stick_defaults()}
        state = {'backend': 'rsinput', 'canApply': True}
        recording = SimpleNamespace(sticks_only=True, output_binding=policy.output_binding(), capture=lambda: capture)
        with patch.object(calibration, '_recording', recording), \
             patch.object(calibration, '_ranges_stale', False), \
             patch.object(calibration, 'read_controller_state', return_value=state), \
             patch.object(calibration, 'read_calibration_params', return_value=current), \
             patch.object(calibration, 'calibration_event', return_value=None), \
             patch.object(calibration, 'stick_defaults', return_value=(1024, 0)), \
             patch.object(calibration, 'inverted_axes', return_value=()), \
             patch.object(calibration, 'calibration_status', return_value={}), \
             patch.object(calibration, 'call') as call:
            calibration.save_calibration()
            saved = json.loads(call.call_args.kwargs['text'])
        self.assertEqual(saved['axis_leftx_max'], 950)
        self.assertEqual(saved['axis_leftx_deadzone'], 47)
        self.assertEqual(saved['trigger_left_max'], self.old['trigger_left_max'])
        self.assertEqual(saved[policy.OUTPUT_KEY], policy.output_binding())

    def test_partial_or_insufficient_output_measurement_cannot_save(self):
        self.enable()
        state = {'backend': 'rsinput', 'canApply': True}
        for capture in ({'left_x': {'min': -1000, 'max': 1000}},
                        {key: {'min': -10, 'max': 10} for key in calibration.AXIS_PARAMS}):
            recording = SimpleNamespace(sticks_only=True, output_binding=policy.output_binding(), capture=lambda: capture)
            with patch.object(calibration, '_recording', recording), \
                 patch.object(calibration, 'read_controller_state', return_value=state), \
                 patch.object(calibration, 'read_calibration_params', return_value=policy.stick_defaults()), \
                 patch.object(calibration, 'calibration_event', return_value=None), \
                 patch.object(calibration, 'stick_defaults', return_value=(1024, 0)), \
                 patch.object(calibration, 'inverted_axes', return_value=()), \
                 patch.object(calibration, 'call') as call:
                with self.assertRaises(RuntimeError):
                    calibration.save_calibration()
                call.assert_not_called()



if __name__ == '__main__':
    unittest.main()
