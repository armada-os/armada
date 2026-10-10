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
    @staticmethod
    def settle_reference(tracker, logical=(0, 0), raw=(32768, 32768)):
        for _ in range(rsinput_calibration.CENTER_STABLE_SAMPLE_GOAL):
            tracker.observe(dict(logicalX=logical[0], logicalY=logical[1], rawX=raw[0], rawY=raw[1]))

    def test_center_excursions_are_translation_invariant(self):
        directions = [(-800, 0), (800, 0), (0, -800), (0, 800),
                      (-600, -600), (600, -600), (-600, 600), (600, 600)]
        for stick in ('left', 'right'):
            results = []
            for origin in ((0, 0), (190, -130), (-120, 280)):
                tracker = rsinput_calibration.CenterTracker(stick)
                self.settle_reference(tracker, origin, (32961, 32638))
                self.assertEqual(tracker.progress()['directionCount'], 0)
                for dx, dy in directions:
                    tracker.observe(dict(logicalX=origin[0]+dx, logicalY=origin[1]+dy,
                                         rawX=32961+dx, rawY=32638+dy))
                    self.assertIsNotNone(tracker.pending)
                    self.settle_reference(tracker, origin, (32961, 32638))
                self.assertTrue(tracker.complete)
                results.append(tracker.result()['centerWords'])
            self.assertEqual(results, [[32961, 32638]]*3)

    def test_odin_offset_does_not_block_upper_right_excursion(self):
        tracker = rsinput_calibration.CenterTracker('right')
        # Physical rest (-190,+130); a (+600,-600) excursion formerly missed X.
        self.settle_reference(tracker, (190, -130), (32961, 32638))
        with patch.object(policy, 'mcu_node', return_value=None):
            self.assertNotEqual(rsinput_calibration.reached_direction('right', -410, 470), 'up-right')
            tracker.observe(dict(logicalX=-410, logicalY=470, rawX=32400, rawY=33200))
            self.assertEqual(tracker.pending, 'up-right')
            self.assertEqual(tracker.progress()['physicalReference'], [-190, 130])
        self.settle_reference(tracker, (190, -130), (32961, 32638))
        self.assertEqual(tracker.returns, [(32961, 32638)])

    def test_reference_rejects_deflection_and_movement_and_never_counts_a_return(self):
        tracker = rsinput_calibration.CenterTracker('right')
        self.settle_reference(tracker, (800, 0), (34000, 32768))
        self.assertIsNone(tracker.logical_reference)
        for i in range(100):
            tracker.observe(dict(logicalX=100, logicalY=-50, rawX=32768+i*2, rawY=32768))
        self.assertIsNone(tracker.logical_reference)
        self.settle_reference(tracker, (100, -50), (32961, 32638))
        self.assertEqual(tracker.logical_reference, (100, -50))
        self.assertEqual(tracker.returns, [])
        self.assertFalse(tracker.complete)

    @staticmethod
    def range_sample(degree, radius, index=0):
        angle = math.radians(degree)
        return {"timestampNs": index * 4_000_000, "generation": index + 1,
                "sequence": index % 255 + 1, "length": 26, "dropped": 0,
                "logicalX": 0, "logicalY": 0,
                "rawX": 32768 + round(math.cos(angle) * radius),
                "rawY": 32768 + round(math.sin(angle) * radius), "rawZ": 40000}

    def test_rest_noise_cannot_supply_range_turns_or_coverage(self):
        tracker = rsinput_calibration.RangeTracker('right', (32768, 32768))
        for degree in range(1801):
            tracker.observe(self.range_sample(degree, 10, degree))
        self.assertEqual(len(tracker.trace), 1801)
        self.assertEqual(tracker.turns, 0)
        self.assertEqual(tracker.progress()['coveredSectors'], 0)
        self.assertEqual(tracker.progress()['coveredHeadings'], 0)
        self.assertFalse(tracker.complete)
        self.assertIsNone(tracker.result())

    def test_waiting_at_rest_does_not_poison_outer_percentiles(self):
        tracker = rsinput_calibration.RangeTracker('right', (32768, 32768))
        # More rest samples than gate samples in one sector, as in the Odin trace.
        for i in range(1000):
            tracker.observe(self.range_sample(90, 5, i))
        for degree in range(1801):
            tracker.observe(self.range_sample(degree, 1000, 1000 + degree))
        self.assertTrue(tracker.complete)
        result = tracker.result()
        self.assertGreater(result['quality']['minimumOuterRadius'], 990)
        indices = result['rawSpaceCandidate']['selectedTraceIndices']
        self.assertTrue(all(i >= 1000 for i in indices))
        self.assertEqual(len(tracker.trace), 2801)

    def test_range_rotation_does_not_bridge_a_return_to_centre(self):
        tracker = rsinput_calibration.RangeTracker('right', (32768, 32768))
        for i, (degree, radius) in enumerate([(0, 1000), (10, 1000), (20, 5),
                                              (30, 1000), (40, 1000)]):
            tracker.observe(self.range_sample(degree, radius, i))
        self.assertAlmostEqual(tracker.turns * 360, 20, delta=0.1)

    def repeated_range(self, radii=(1000, 1000, 1000, 1000), direction=1, start=17,
                       z_offsets=None, spike=False):
        tracker = rsinput_calibration.RangeTracker('right', (32768, 32768))
        for degree in range(1443):
            lap = min(degree // 360, 3)
            row = self.range_sample(start + direction * degree, radii[lap], degree)
            if z_offsets:
                row['rawZ'] = 32768 + z_offsets[lap]
            if spike and degree == 720 + 90:
                row = self.range_sample(start + direction * degree, 1700, degree)
            tracker.observe(row)
        self.assertTrue(tracker.complete)
        return tracker

    def test_repeatability_accepts_both_directions_and_excludes_approach_lap(self):
        for direction in (-1, 1):
            tracker = self.repeated_range((1500, 1000, 1000, 1000), direction)
            result = tracker.result()
            self.assertEqual(result['quality']['repeatability']['comparedRotations'], 3)
            selected = result['rawSpaceCandidate']['selectedTraceIndices']
            self.assertTrue(all(i >= 360 for i in selected))
            self.assertTrue(all(tracker.trace[i]['rawRadius'] < 1001 for i in selected))

    def test_identical_paths_with_different_angular_dwell_are_repeatable(self):
        for direction in (-1, 1):
            tracker = rsinput_calibration.RangeTracker('left', (32768, 32768))
            index = 0
            for degree in range(1443):
                angle = math.radians(direction * degree)
                radius = 1100 / math.sqrt(math.cos(angle)**2 + (.52 * math.sin(angle))**2)
                lap = min(degree // 360, 3)
                # Identical geometry on all four turns; only time spent at a
                # heading changes. Time-weighted sector quartiles reject this.
                repeats = 30 if degree % 15 == (2 if lap == 2 else 12) else 1
                for _ in range(repeats):
                    tracker.observe(self.range_sample(direction * degree, radius, index))
                    index += 1
            result = tracker.result()
            self.assertIsNotNone(result)
            self.assertEqual(result['quality']['repeatability']['comparisonSampling'], 'uniform-angle-linear')
            for index, triple in zip(result['rawSpaceCandidate']['selectedTraceIndices'],
                                    result['rawSpaceCandidate']['triples']):
                self.assertEqual(triple, [tracker.trace[index][key] for key in ('rawX', 'rawY', 'rawZ')])

    def test_uniform_angle_comparison_does_not_bridge_unobserved_arcs(self):
        tracker = rsinput_calibration.RangeTracker('left', (32768, 32768))
        for degree in range(1443):
            # Each 15-degree bin still has >=2 real samples, but the missing
            # 16-degree arc must not be silently filled by interpolation.
            if 364 <= degree <= 378:
                continue
            tracker.observe(self.range_sample(degree, 1000, degree))
        self.assertTrue(tracker.complete)
        with self.assertRaisesRegex(RuntimeError, 'too fast or uneven'):
            tracker.result()

    def test_larger_or_drifting_laps_cannot_dominate_the_candidate(self):
        for radii in ((1000, 1000, 1400, 1000), (1000, 1000, 1090, 1190)):
            with self.assertRaisesRegex(RuntimeError, 'rotations disagree'):
                self.repeated_range(radii).result()
        # Provisional measured agreement policy, not an arbitrary-radius detector.
        self.assertIsNotNone(self.repeated_range((1000, 1000, 1040, 1090)).result())
        with self.assertRaisesRegex(RuntimeError, 'rotations disagree'):
            self.repeated_range((1000, 1000, 1040, 1110)).result()

    def test_z_only_changes_are_rejected_even_with_identical_xy_travel(self):
        with self.assertRaisesRegex(RuntimeError, 'rotations disagree'):
            self.repeated_range(z_offsets=(7000, 7000, 5400, 7000)).result()
        with self.assertRaisesRegex(RuntimeError, 'calibration domain'):
            self.repeated_range(z_offsets=(7000, 0, 7000, 7000)).result()
        with self.assertRaisesRegex(RuntimeError, 'range is zero'):
            rsinput_calibration.RangeTracker._hall_metrics(
                {'rawX':32768, 'rawY':32768, 'rawZ':40000, 'rawRadius':1000})

    def test_isolated_large_sample_is_retained_but_never_selected(self):
        tracker = self.repeated_range(start=0, spike=True)
        result = tracker.result()
        self.assertGreater(tracker.trace[810]['rawRadius'], 1600)
        self.assertNotIn(810, result['rawSpaceCandidate']['selectedTraceIndices'])
        self.assertTrue(all(tracker.trace[i]['rawRadius'] < 1001
                            for i in result['rawSpaceCandidate']['selectedTraceIndices']))

    def test_interrupted_sweeps_cannot_supply_repeatability(self):
        for interruption in ('centre', 'angular-jump'):
            tracker = rsinput_calibration.RangeTracker('left', (32768, 32768))
            for degree in range(1801):
                if degree == 720:
                    tracker.observe(self.range_sample(degree + 80,
                                    5 if interruption == 'centre' else 1000, degree))
                tracker.observe(self.range_sample(degree, 1000, degree))
            self.assertTrue(tracker.complete)
            with self.assertRaisesRegex(RuntimeError, 'rotations were interrupted'):
                tracker.result()

    def test_sparse_individual_laps_fail_even_when_total_coverage_passes(self):
        tracker = rsinput_calibration.RangeTracker('left', (32768, 32768))
        for degree in range(1443):
            # One measured lap skips most of a 15-degree sector; other laps
            # still satisfy the old aggregate heading and 72-sector gates.
            if 366 <= degree <= 374:
                continue
            if 376 <= degree <= 389:
                continue
            tracker.observe(self.range_sample(degree, 1000, degree))
        self.assertTrue(tracker.complete)
        with self.assertRaisesRegex(RuntimeError, 'too fast or uneven'):
            tracker.result()

    def test_consistency_alone_does_not_prove_physical_rim_contact(self):
        # A repeatable undersized circle above the independent 600-count floor
        # is indistinguishable from a smaller physical gate using this signal.
        self.assertIsNotNone(self.repeated_range((650,)*4).result())

    def test_moving_center_is_rejected_then_settled_window_is_averaged(self):
        tracker = rsinput_calibration.CenterTracker('left')
        self.settle_reference(tracker)
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
        self.settle_reference(tracker)
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
        self.settle_reference(center)
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
        assert not weak.complete and weak.progress()["coveredSectors"] == 0
        assert weak.turns == 0 and weak.result() is None

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
        self.enterContext(patch.object(rsinput_calibration, 'sync_directory'))
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

    def test_directory_sync_failure_prevents_uart_open_or_write(self):
        with patch.object(rsinput_calibration, 'sync_directory', side_effect=OSError('sync failed')), \
             patch.object(rsinput_calibration.os, 'open') as opened:
            with self.assertRaisesRegex(OSError, 'sync failed'):
                rsinput_calibration.write_calibration('no-directory-sync', results())
        opened.assert_not_called()
        self.write.assert_not_called()
        self.assertNotEqual(rsinput_calibration.recorded_outcome('no-directory-sync')['state'], 'applied')

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
    def test_inconsistent_range_is_saved_but_cannot_advance_or_apply(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(rsinput_calibration, 'JOURNAL_ROOT', Path(temp)):
            capture = rsinput_calibration.CaptureSession('uneven-range', 'left', 'range', (32768, 32768))
            records = []
            for degree in range(1803):
                row = CalculationTests.range_sample(degree, 1400 if 720 <= degree < 1080 else 1000, degree)
                payload = bytearray(26)
                rsinput_calibration.struct.pack_into('<HHH', payload, 14, row['rawX'], row['rawY'], row['rawZ'])
                records.append(rsinput_calibration.SAMPLE.pack(row['timestampNs'], row['generation'],
                               row['sequence'], 26, payload, 0, 1, 0))
            with patch.object(policy, 'device_path', return_value='/dev/test'), \
                 patch.object(policy, 'capture_configuration', return_value={'kernel':'fixture'}), \
                 patch.object(rsinput_calibration, 'sync_directory'), \
                 patch.object(rsinput_calibration.os, 'open', return_value=99), \
                 patch.object(rsinput_calibration.os, 'read', side_effect=records), \
                 patch.object(rsinput_calibration.os, 'write', return_value=64) as write, \
                 patch.object(rsinput_calibration.os, 'close'), \
                 patch.object(rsinput_calibration.select, 'poll') as poll:
                poll.return_value.poll.return_value = [(99, 1)]
                capture._run()
            state = capture.snapshot()
            self.assertIn('rotations disagree', state['error'])
            self.assertFalse(state['active'])
            artifact = json.loads(Path(state['capturePath']).read_text())
            self.assertIsNone(artifact['result'])
            self.assertEqual(artifact['abiRecordsHex'], [r.hex() for r in records[:state['sampleCount']]])
            self.assertGreater(len(artifact['trace']), 1400)
            self.assertEqual([rsinput_calibration.COMMAND.unpack(c.args[1])[1] for c in write.call_args_list],
                             [0xA0, 0xA0])
            manager = rsinput_calibration.CalibrationManager()
            manager.token, manager.state, manager.step, manager.capture = 'uneven-range', 'measuring', 1, capture
            with patch.object(rsinput_calibration, 'write_calibration') as persistent_write:
                status = manager.dispatch('apply', 'uneven-range')
                self.assertEqual(status['state'], 'failed')
                self.assertNotIn('continue', status['actions'])
                self.assertNotIn('apply', status['actions'])
                persistent_write.assert_not_called()

    def test_failed_low_logical_travel_retains_original_reports_and_stage(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(rsinput_calibration, 'JOURNAL_ROOT', Path(temp)):
            capture = rsinput_calibration.CaptureSession('short-travel', 'left', 'center')
            payload = bytearray(26)
            rsinput_calibration.struct.pack_into('<hh', payload, 6, 500, 0)
            rsinput_calibration.struct.pack_into('<HHH', payload, 14, 34000, 32768, 40000)
            rest = bytearray(26)
            rsinput_calibration.struct.pack_into('<HHH', rest, 14, 32768, 32768, 40000)
            records = [rsinput_calibration.SAMPLE.pack(i * 4_000_000, 0xffffffe1+i, i+1, 26, rest, 0, 1, 0)
                       for i in range(30)]
            records += [rsinput_calibration.SAMPLE.pack(i * 4_000_000, generation, i+1, 26, payload, 0, 1, 0)
                        for i, generation in ((30, 0xffffffff), (31, 0))]
            with patch.object(policy, 'device_path', return_value='/dev/test'), \
                 patch.object(policy, 'capture_configuration', return_value={'kernel': 'fixture'}), \
                 patch.object(rsinput_calibration, 'sync_directory'), \
                 patch.object(rsinput_calibration.os, 'open', return_value=99), \
                 patch.object(rsinput_calibration.os, 'read', side_effect=records), \
                 patch.object(rsinput_calibration.os, 'write', return_value=64) as write, \
                 patch.object(rsinput_calibration.os, 'close'), \
                 patch.object(rsinput_calibration.time, 'monotonic', side_effect=[0] * 33 + [121]), \
                 patch.object(rsinput_calibration.select, 'poll') as poll:
                poll.return_value.poll.return_value = [(99, 1)]
                capture._run()
            state = capture.snapshot()
            self.assertFalse(state['active'])
            self.assertFalse(state['complete'])
            self.assertIn('center: excursion coverage incomplete', state['error'])
            self.assertIn('max [500, 0]', state['error'])
            self.assertEqual(state['generationGaps'], 0)
            self.assertEqual(state['sequenceGaps'], 0)
            artifact = json.loads(Path(state['capturePath']).read_text())
            self.assertEqual(artifact['abiRecordsHex'], [raw.hex() for raw in records])
            self.assertEqual(artifact['configuration'], {'kernel': 'fixture'})
            self.assertEqual(artifact['state']['error'], state['error'])
            self.assertEqual(len(artifact['trace']), rsinput_calibration.CENTER_STABLE_SAMPLE_GOAL + 2)
            self.assertIsNone(artifact['result'])
            self.assertEqual([rsinput_calibration.COMMAND.unpack(c.args[1])[1] for c in write.call_args_list],
                             [0xA0, 0xA0])

    def test_timeout_distinguishes_reports_settling_and_range_coverage(self):
        capture = rsinput_calibration.CaptureSession('test', 'left', 'center')
        self.assertIn('no 26-byte', capture.timeout_reason())
        capture.state['rawSampleCount'] = 1
        self.assertIn('resting reference did not settle', capture.timeout_reason())
        CalculationTests.settle_reference(capture.tracker)
        capture.tracker.observe(dict(logicalX=800, logicalY=0, rawX=34000, rawY=32768))
        self.assertIn('return did not settle', capture.timeout_reason())
        capture = rsinput_calibration.CaptureSession('test', 'right', 'range', (32768, 32768))
        capture.state['rawSampleCount'] = 1
        self.assertIn('range: coverage incomplete', capture.timeout_reason())

    def test_completion_saves_without_a_continue_request(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(rsinput_calibration, 'JOURNAL_ROOT', Path(temp)):
            capture = rsinput_calibration.CaptureSession('test', 'left', 'center')
            class Tracker:
                complete = True
                trace = []
                def observe(self, sample): pass
                def progress(self): return {'directionCount': 8}
                def result(self): return results()[('left', 'center')]
            capture.tracker = Tracker()
            sample = rsinput_calibration.SAMPLE.pack(1, 1, 1, 26, b'\0' * 26, 0, 1, 0)
            with patch.object(policy, 'device_path', return_value='/dev/test'), \
                 patch.object(rsinput_calibration, 'sync_directory'), \
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
                 patch.object(rsinput_calibration, 'sync_directory'), \
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
            artifact = json.loads(next(Path(temp).glob('capture-*')).read_text())
            self.assertFalse(artifact['state']['complete'])
            self.assertEqual(artifact['abiRecordsHex'], [])

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
