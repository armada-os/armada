#!/usr/bin/env python3
"""Pure calibration calculations, transport failures, and session transitions."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
import rsinput_calibration
import input_calibration_policy as policy


class CalculationTests(unittest.TestCase):
    def test_moving_center_is_rejected_then_settled_window_is_averaged(self):
        tracker = rsinput_calibration.CenterTracker('left')
        with patch.object(policy, 'mcu_node', return_value=None):
            tracker.observe(dict(logicalX=800, logicalY=0, rawX=33568, rawY=32768))
            for i in range(120):
                offset = 300 if i % 2 else -300
                tracker.observe(dict(logicalX=offset, logicalY=0,
                                     rawX=32768 + offset, rawY=32768))
            self.assertEqual(tracker.progress()['directionCount'], 0)
            self.assertLess(tracker.stable, rsinput_calibration.CENTER_STABLE_SAMPLE_GOAL)
            for i in range(30):
                tracker.observe(dict(logicalX=0, logicalY=0,
                                     rawX=32768 + i % 2 * 10, rawY=32768))
            self.assertEqual(tracker.returns, [(32773, 32768)])
            self.assertEqual(tracker.progress()['directionCount'], 1)

    def test_center_drift_and_leaving_center_restart_settling(self):
        tracker = rsinput_calibration.CenterTracker('left')
        with patch.object(policy, 'mcu_node', return_value=None):
            tracker.observe(dict(logicalX=800, logicalY=0, rawX=33568, rawY=32768))
            for i in range(100):
                tracker.observe(dict(logicalX=0, logicalY=0, rawX=32768 + i * 2, rawY=32768))
            self.assertEqual(tracker.returns, [])
            tracker.observe(dict(logicalX=800, logicalY=0, rawX=33568, rawY=32768))
            for _ in range(29):
                tracker.observe(dict(logicalX=0, logicalY=0, rawX=32768, rawY=32768))
            self.assertEqual(tracker.returns, [])
            tracker.observe(dict(logicalX=0, logicalY=0, rawX=32768, rawY=32768))
            self.assertEqual(tracker.returns, [(32768, 32768)])

    def test_measurement_gates_and_stock_coefficients(self):
        assert rsinput_calibration.COMMAND.size == 64
        assert rsinput_calibration.SAMPLE.size == 48
        version, command, length, payload = rsinput_calibration.COMMAND.unpack(
            rsinput_calibration.mode_record("left", True)
        )
        assert (version, command, length) == (1, 0xA0, 1)
        assert payload == b"\1" + b"\0" * 57
        assert set(rsinput_calibration.MODE_COMMANDS.values()) == {0xA0, 0xA1}
        sample = rsinput_calibration.SAMPLE.pack(1, 2, 255, 26, b"\0" * 26, 7, 1, 0)
        decoded = rsinput_calibration.decode_sample(sample, "left")
        assert decoded["generation"] == 2 and decoded["dropped"] == 7

        center = rsinput_calibration.CenterTracker("left")
        physical_directions = {
            "left": (-800, 0), "right": (800, 0), "up": (0, -800), "down": (0, 800),
            "up-left": (-600, -600), "up-right": (600, -600),
            "down-left": (-600, 600), "down-right": (600, 600),
        }
        for index, name in enumerate(rsinput_calibration.CENTER_DIRECTIONS):
            physical_x, physical_y = physical_directions[name]
            center.observe({"logicalX": -physical_x, "logicalY": -physical_y,
                            "rawX": 32600 + index, "rawY": 32500 + index})
            assert center.progress()["pendingDirection"] == name
            for _ in range(rsinput_calibration.CENTER_STABLE_SAMPLE_GOAL):
                center.observe({"logicalX": 0, "logicalY": 0,
                                "rawX": 32600 + index, "rawY": 32500 + index})
        assert center.complete
        assert center.progress()["directionCount"] == 8
        assert center.result()["centerWords"] == [32603, 32503]
        assert center.result()["returns"] == [[32600 + index, 32500 + index] for index in range(8)]

        def sweep(tracker, radius_x=1000, radius_y=1000, short_positive_y=False):
            for degree in range(0, 1801):
                angle = math.radians(degree % 360)
                logical_y_scale = 908 if short_positive_y and math.sin(angle) > 0 else 1024
                tracker.observe({
                    "timestampNs": degree * 4_000_000, "generation": degree + 1,
                    "sequence": degree % 255 + 1, "length": 26, "dropped": 0,
                    "logicalX": round(math.cos(angle) * 1024),
                    "logicalY": round(math.sin(angle) * logical_y_scale),
                    "rawX": 32768 + round(math.cos(angle) * radius_x),
                    "rawY": 32768 + round(math.sin(angle) * radius_y), "rawZ": 40000,
                })


        range_tracker = rsinput_calibration.RangeTracker("right", (32768, 32768))
        sweep(range_tracker)
        assert range_tracker.complete
        assert range_tracker.progress()["coveredHeadings"] == 8
        assert len(range_tracker.result()["rawSpaceCandidate"]["tableWords"]) == 29
        assert range_tracker.progress()["coveredSectors"] == 72
        result = range_tracker.result()
        observed = {(r["rawX"], r["rawY"], r["rawZ"]) for r in range_tracker.trace}
        assert all(tuple(triple) in observed for triple in result["rawSpaceCandidate"]["triples"])

        # Logical-axis distortion must not affect raw-space selection.
        distorted = rsinput_calibration.RangeTracker("left", (32768, 32768))
        sweep(distorted, radius_x=800, radius_y=1250, short_positive_y=True)
        distorted_result = distorted.result()
        assert distorted_result["quality"]["outerRadiusRatio"] < rsinput_calibration.MAX_RADIAL_RATIO
        assert distorted_result["rawSpaceCandidate"]["available"]
        assert distorted_result["slotRawAngles"] == [90, 180, 270, 0, 45, 135, 225, 315]

        # Coverage alone is insufficient without firm gate contact.
        weak = rsinput_calibration.RangeTracker("left", (32768, 32768))
        sweep(weak, radius_x=400, radius_y=400)
        assert weak.complete and weak.progress()["coveredSectors"] == 72
        try:
            weak.result()
        except RuntimeError as error:
            assert "weak outer-gate contact" in str(error)
        else:
            raise AssertionError("weak full-coverage sweep was accepted")

        malformed = rsinput_calibration.RangeTracker("left", (32768, 32768))
        try:
            malformed.observe({"length": 14})
        except RuntimeError:
            pass
        else:
            raise AssertionError("malformed range report was accepted")

        arithmetic = rsinput_calibration.RangeTracker("left", (32768, 32768))
        bad = {"timestampNs": 0, "generation": 1, "sequence": 1, "length": 26,
               "dropped": 0, "logicalX": 0, "logicalY": 0, "rawX": 10 ** 400,
               "rawY": 32768, "rawZ": 40000}
        try:
            arithmetic.observe(bad)
        except RuntimeError as error:
            assert "arithmetic" in str(error)
        else:
            raise AssertionError("raw arithmetic overflow was accepted")

        # The left stick's 180-degree rotation maps logical +Y to A3 triple 2.
        left_range = rsinput_calibration.RangeTracker("left", (32768, 32768))
        sweep(left_range)
        left_result = left_range.result()
        assert left_result["stick"] == "left"
        assert left_result["slotRawAngles"] == [90, 180, 270, 0, 45, 135, 225, 315]
        selected = left_result["rawSpaceCandidate"]["selectedTraceIndices"]
        assert all(left_range.distance(left_range.trace[index]["rawAngle"], target) <= 5
                   for index, target in zip(selected, [90, 180, 270, 0, 45, 135, 225, 315]))
        assert all(left_result["rawSpaceCandidate"]["triples"][slot] == [left_range.trace[index][key]
                   for key in ("rawX", "rawY", "rawZ")] for slot, index in enumerate(selected))
        rp6_stock_triples = [
            (0x7F32, 0x848A, 0x951D), (0x7A34, 0x7EAA, 0x946E),
            (0x7FB8, 0x79EE, 0x9468), (0x84DA, 0x7F23, 0x9546),
            (0x834C, 0x8347, 0x954F), (0x7B42, 0x82C2, 0x94B8),
            (0x7C35, 0x7B80, 0x9400), (0x8324, 0x7B77, 0x94BE),
        ]
        assert rsinput_calibration.derived_words(rp6_stock_triples) == (
            0x01CA, 0x0DD9, 0x13F2, 0x24F9, 0x5C7F,
        )


def results():
    return {(stick, phase): ({"centerWords": [32768, 32768], "returns": [[32768, 32768]] * 8}
                            if phase == "center" else {"rawSpaceCandidate": {"tableWords": [32768] * 29}})
            for stick, phase in rsinput_calibration.STEPS}


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.enterContext(patch.object(rsinput_calibration, 'JOURNAL_ROOT', Path(self.temp.name)))
        self.enterContext(patch.object(policy, 'uses_mcu', return_value=True))
        self.enterContext(patch.object(policy, 'device_path', return_value='/dev/test'))
        self.enterContext(patch.object(rsinput_calibration.os, 'open', return_value=99))
        self.close = self.enterContext(patch.object(rsinput_calibration.os, 'close'))
        self.delay = self.enterContext(patch.object(rsinput_calibration.time, 'sleep'))
        self.write = self.enterContext(patch.object(rsinput_calibration.os, 'write', return_value=64))

    def test_command_order_pacing_and_restart_recovery(self):
        rsinput_calibration.write_calibration('test', results())
        opcodes = [rsinput_calibration.COMMAND.unpack(call.args[1])[1] for call in self.write.call_args_list]
        self.assertEqual(opcodes, [0xA0, 0xA2, 0xA3, 0xA0, 0xA1, 0xA5, 0xA6, 0xA0])
        self.assertEqual([call.args[0] for call in self.delay.call_args_list], [1.0] * 8)
        # A new daemon and a retried RPC must recover success without writing again.
        manager = rsinput_calibration.CalibrationManager()
        self.assertEqual(manager.dispatch('status', 'test')['state'], 'applied')
        self.assertEqual(manager.dispatch('apply', 'test')['state'], 'applied')
        self.assertEqual(self.write.call_count, 8)
        with self.assertRaises(FileExistsError):
            rsinput_calibration.write_calibration('test', results())
        self.assertEqual(self.write.call_count, 8)
        self.close.assert_called_once_with(99)

    def test_failures_and_short_writes_at_every_command_are_uncertain(self):
        for index in range(8):
            for short in (False, True):
                token = f'test-{index}-{short}'
                with self.subTest(command=index, short=short):
                    self.write.reset_mock()
                    self.write.side_effect = [64] * index + [1 if short else OSError('UART failed')]
                    with self.assertRaises((RuntimeError, OSError)):
                        rsinput_calibration.write_calibration(token, results())
                    manager = rsinput_calibration.CalibrationManager()
                    status = manager.dispatch('status', token)
                    self.assertEqual(status['state'], 'uncertain')
                    self.assertNotIn('apply', status['actions'])
                    manager.dispatch('apply', token)
                    self.assertEqual(self.write.call_count, index + 1)

    def test_preflight_and_open_failures_send_nothing(self):
        with patch.object(policy, 'device_path', return_value=None):
            with self.assertRaises(RuntimeError):
                rsinput_calibration.write_calibration('absent', results())
        self.assertIsNone(rsinput_calibration.recorded_outcome('absent'))
        with patch.object(rsinput_calibration.os, 'open', side_effect=OSError('busy')):
            with self.assertRaises(OSError):
                rsinput_calibration.write_calibration('busy', results())
        self.assertEqual(rsinput_calibration.recorded_outcome('busy')['state'], 'failed')
        self.write.assert_not_called()

    def test_truncated_journal_is_uncertain(self):
        rsinput_calibration.write_calibration('test', results())
        with rsinput_calibration.journal_path('test').open('a') as handle:
            handle.write('{')
        self.assertEqual(rsinput_calibration.recorded_outcome('test')['state'], 'uncertain')

    def test_journal_failure_prevents_unrecorded_write(self):
        original = rsinput_calibration.append_journal
        def append(path, event):
            if event['event'] == 'before-write':
                raise OSError('disk full')
            original(path, event)
        with patch.object(rsinput_calibration, 'append_journal', side_effect=append):
            with self.assertRaises(OSError):
                rsinput_calibration.write_calibration('test', results())
        self.write.assert_not_called()
        self.assertEqual(rsinput_calibration.recorded_outcome('test')['state'], 'failed')


class CompletedCapture(rsinput_calibration.CaptureSession):
    """Supply measured data while using the real evidence persistence path."""
    def start(self):
        self._update(complete=True, result=results()[(self.stick, self.phase)])
        try:
            self._save_capture(self.snapshot())
        except OSError as error:
            self._update(error=str(error))
        self._update(active=False)

    def stop(self):
        self.stop_event.set()
        return self.snapshot()


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.enterContext(patch.object(rsinput_calibration, 'JOURNAL_ROOT', Path(self.temp.name)))
        self.enterContext(patch.object(policy, 'uses_mcu', return_value=True))
        self.enterContext(patch.object(policy, 'device_path', return_value='/dev/test'))
        self.prepare = self.enterContext(patch.object(policy, 'prepare_sticks'))
        self.enterContext(patch.object(rsinput_calibration, 'CaptureSession', CompletedCapture))
        self.manager = rsinput_calibration.CalibrationManager()

    def ready(self):
        status = self.manager.dispatch('start', 'test')
        for index in range(4):
            self.assertEqual(status['state'], 'measured')
            self.assertEqual((status['stick'], status['phase']), rsinput_calibration.STEPS[index])
            self.assertEqual(len(list(rsinput_calibration.JOURNAL_ROOT.glob('capture-*'))), index + 1)
            status = self.manager.dispatch('continue', 'test', index)
        self.assertEqual(status['state'], 'ready')
        return status

    def test_step_order_persistence_and_duplicate_requests(self):
        first = self.manager.dispatch('start', 'test')
        self.assertEqual(first, self.manager.dispatch('start', 'test'))
        self.prepare.assert_called_once()
        with self.assertRaises(RuntimeError):
            self.manager.dispatch('apply', 'test')
        self.assertEqual(self.manager.dispatch('continue', 'test', 3)['step'], 0)
        advanced = self.manager.dispatch('continue', 'test', 0)
        self.assertEqual(advanced['step'], 1)
        self.assertEqual(advanced, self.manager.dispatch('continue', 'test', 0))
        for step in (1, 2, 3):
            final = self.manager.dispatch('continue', 'test', step)
        self.assertEqual(final['state'], 'ready')
        self.assertEqual(final, self.manager.dispatch('continue', 'test', 3))
        self.assertEqual(len(self.manager.results), 4)

    def test_cancel_discards_candidates_and_new_session_starts_at_left_center(self):
        self.ready()
        cancelled = self.manager.dispatch('cancel', 'test')
        self.assertEqual(cancelled['state'], 'cancelled')
        self.assertEqual(self.manager.results, {})
        self.assertNotIn('apply', self.manager.dispatch('apply', 'test')['actions'])
        fresh = self.manager.dispatch('start', 'new')
        self.assertEqual(fresh['step'], 0)
        self.manager.dispatch('cancel', 'test')  # A stale client cannot cancel the new session.
        self.assertEqual(self.manager.dispatch('status', 'new')['state'], 'measured')

    def test_reopening_can_replace_abandoned_measurements(self):
        self.ready()
        fresh = self.manager.dispatch('start', 'new')
        self.assertEqual(fresh['step'], 0)
        self.assertEqual(self.manager.results, {})

    def test_failed_evidence_save_cannot_advance_or_apply(self):
        with patch.object(CompletedCapture, '_save_capture', side_effect=OSError('disk full')):
            status = self.manager.dispatch('start', 'test')
        self.assertEqual(status['state'], 'failed')
        self.assertNotIn('continue', status['actions'])
        self.assertNotIn('apply', status['actions'])
        self.assertEqual(self.manager.results, {})

    def test_apply_runs_once_without_blocking_status_or_allowing_replacement(self):
        self.ready()
        entered, release = threading.Event(), threading.Event()
        def writer(token, data):
            self.assertEqual(len(data), 4)
            entered.set()
            if not release.wait(2):
                raise RuntimeError('test timeout')
            rsinput_calibration.append_journal(rsinput_calibration.journal_path(token),
                {'event': 'finish', 'outcome': 'all-frames-transmitted'})
        with patch.object(rsinput_calibration, 'write_calibration', side_effect=writer) as write:
            self.assertEqual(self.manager.dispatch('apply', 'test')['state'], 'applying')
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.manager.dispatch('status', 'test')['state'], 'applying')
            self.assertEqual(self.manager.dispatch('apply', 'test')['actions'], [])
            self.assertEqual(self.manager.dispatch('cancel', 'test')['state'], 'applying')
            with self.assertRaises(RuntimeError):
                self.manager.dispatch('start', 'new')
            release.set()
            self.manager.writer.join(2)
            self.assertEqual(self.manager.dispatch('status', 'test')['state'], 'applied')
            write.assert_called_once()

    def test_lost_measurement_session_after_restart_requires_new_capture(self):
        self.ready()
        restarted = rsinput_calibration.CalibrationManager()
        status = restarted.dispatch('apply', 'test')
        self.assertEqual(status['state'], 'failed')
        self.assertNotIn('apply', status['actions'])


class CaptureTests(unittest.TestCase):
    def test_completion_saves_without_a_continue_request(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(rsinput_calibration, 'JOURNAL_ROOT', Path(temp)):
            capture = rsinput_calibration.CaptureSession('test', 'left', 'center')
            class Tracker:
                complete = True
                def observe(self, sample): pass
                def progress(self): return {'directionCount': 8}
                def result(self): return results()[('left', 'center')]
            capture.tracker = Tracker()
            sample = rsinput_calibration.SAMPLE.pack(1, 1, 1, 26, b'\0' * 26, 0, 1, 0)
            with patch.object(policy, 'device_path', return_value='/dev/test'), \
                 patch.object(rsinput_calibration.os, 'open', return_value=99), \
                 patch.object(rsinput_calibration.os, 'read', return_value=sample), \
                 patch.object(rsinput_calibration.os, 'write', return_value=64), \
                 patch.object(rsinput_calibration.os, 'close'), \
                 patch.object(rsinput_calibration.select, 'poll') as poll:
                poll.return_value.poll.return_value = [(99, 1)]
                capture.start()
                capture.thread.join(2)
            state = capture.snapshot()
            self.assertFalse(state['active'])
            self.assertFalse(state['error'])
            self.assertTrue(Path(state['result']['capturePath']).exists())

    def test_cancel_closes_capture_mode_without_persistent_commands(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(rsinput_calibration, 'JOURNAL_ROOT', Path(temp)):
            capture = rsinput_calibration.CaptureSession('cancelled', 'right', 'center')
            def poll_once(_timeout):
                capture.stop_event.set()
                return []
            with patch.object(policy, 'device_path', return_value='/dev/test'), \
                 patch.object(rsinput_calibration.os, 'open', return_value=99), \
                 patch.object(rsinput_calibration.os, 'write', return_value=64) as write, \
                 patch.object(rsinput_calibration.os, 'close') as close, \
                 patch.object(rsinput_calibration.select, 'poll') as poll:
                poll.return_value.poll.side_effect = poll_once
                capture.start()
                capture.thread.join(2)
            self.assertFalse(capture.snapshot()['active'])
            self.assertEqual([rsinput_calibration.COMMAND.unpack(c.args[1])[1] for c in write.call_args_list],
                             [0xA1, 0xA0])
            close.assert_called_once_with(99)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_physical_direction_mapping_is_owned_by_backend(self):
        for stick in ('left', 'right'):
            with patch.object(policy, 'mcu_node', return_value=None):
                self.assertEqual(rsinput_calibration.reached_direction(stick, 800, 0), 'left')
        with tempfile.TemporaryDirectory() as temp:
            node = Path(temp)
            (node / 'invert-x').touch()
            with patch.object(policy, 'mcu_node', return_value=node):
                self.assertEqual(rsinput_calibration.reached_direction('left', 800, 0), 'right')
                self.assertEqual(rsinput_calibration.reached_direction('right', 800, 0), 'left')


if __name__ == '__main__':
    unittest.main()
