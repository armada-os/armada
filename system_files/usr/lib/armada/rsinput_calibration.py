"""Privileged rsinput MCU calibration capture and explicit commit transport."""

import hashlib
import json
import math
import os
from pathlib import Path
import select
import struct
import threading
import time

import input_calibration_policy as policy


ABI_VERSION = 1
COMMAND = struct.Struct("<HBB58s2x")
SAMPLE = struct.Struct("<QIBB26sIHH")
MODE_COMMANDS = {"left": 0xA0, "right": 0xA1}
PHASES = {"center", "range"}
CENTER_DIRECTIONS = (
    "left", "right", "up", "down",
    "up-left", "up-right", "down-left", "down-right",
)
CENTER_STABLE_SAMPLE_GOAL = 30
# Signed MCU logical-report counts, before the driver's sign/deadzone handling.
# These are distinct from RangeTracker's raw Hall radius and evdev's advertised range.
CENTER_CARDINAL_MIN = 700
CENTER_DIAGONAL_MIN = 500
CENTER_RETURN_MAX = 350
# Maximum peak-to-peak Hall movement within a settling window, in raw counts.
CENTER_STABLE_RAW_SPREAD = 32
RIGHT_SLOT_ANGLES = (90, 180, 270, 0, 45, 135, 225, 315)
DATA_COMMANDS = {"left": (0xA2, 0xA3), "right": (0xA5, 0xA6)}
WRITE_DELAY_SECONDS = 1.0
RANGE_TURN_GOAL = 4
RANGE_BIN_COUNT = 72
MIN_BIN_SAMPLES = 3
MIN_SLOT_SAMPLES = 8
MIN_OUTER_RADIUS = 600
MAX_RADIAL_RATIO = 2.2
# Compare 15-degree sectors across three complete revolutions after the first
# approach-to-rim revolution. These are agreement limits, not proof of rim contact.
RANGE_REPEAT_BINS = 24
MIN_REPEAT_SAMPLES = 2
MAX_REPEAT_RATIO = 1.10
MAX_CAPTURE_GAP_NS = 100_000_000
MAX_SESSION_SECONDS = 120
JOURNAL_ROOT = Path("/var/lib/armada/calibration")

def mode_record(stick, enabled):
    if stick not in MODE_COMMANDS:
        raise ValueError("invalid stick")
    command = MODE_COMMANDS[stick] if enabled else 0xA0
    payload = b"\1" if enabled else b"\0"
    return COMMAND.pack(ABI_VERSION, command, 1, payload.ljust(58, b"\0"))


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def make_directory(path):
    if not path.exists():
        make_directory(path.parent)
        path.mkdir(exist_ok=True)
        sync_directory(path.parent)


def append_journal(path, event):
    event["monotonicNs"] = time.monotonic_ns()
    make_directory(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def decode_sample(raw, stick):
    if len(raw) != SAMPLE.size:
        raise RuntimeError(f"short calibration sample: {len(raw)}/{SAMPLE.size}")
    timestamp, generation, sequence, length, payload, dropped, version, flags = SAMPLE.unpack(raw)
    if version != ABI_VERSION or flags:
        raise RuntimeError(f"unsupported calibration ABI {version}, flags 0x{flags:x}")
    if length not in (14, 26):
        raise RuntimeError(f"invalid calibration report length {length}")
    logical_offset = 6 if stick == "left" else 10
    logical_x, logical_y = struct.unpack_from("<hh", payload, logical_offset)
    result = {
        "timestampNs": timestamp,
        "generation": generation,
        "sequence": sequence,
        "length": length,
        "dropped": dropped,
        "logicalX": logical_x,
        "logicalY": logical_y,
    }
    if length == 26:
        raw_offset = 14 if stick == "left" else 20
        raw_x, raw_y, raw_z = struct.unpack_from("<HHH", payload, raw_offset)
        result.update({"rawX": raw_x, "rawY": raw_y, "rawZ": raw_z})
    return result


def physical_axes(stick, x, y):
    return policy.physical_axes(stick, x, y)


def reached_direction(stick, x, y):
    x, y = physical_axes(stick, x, y)
    checks = (
        ("up-left", x < -CENTER_DIAGONAL_MIN and y < -CENTER_DIAGONAL_MIN),
        ("up-right", x > CENTER_DIAGONAL_MIN and y < -CENTER_DIAGONAL_MIN),
        ("down-left", x < -CENTER_DIAGONAL_MIN and y > CENTER_DIAGONAL_MIN),
        ("down-right", x > CENTER_DIAGONAL_MIN and y > CENTER_DIAGONAL_MIN),
        ("left", x < -CENTER_CARDINAL_MIN), ("right", x > CENTER_CARDINAL_MIN),
        ("up", y < -CENTER_CARDINAL_MIN), ("down", y > CENTER_CARDINAL_MIN),
    )
    return next((name for name, reached in checks if reached), None)


def derived_words(triples):
    ratios = []
    for x, y, z in triples:
        denominator = z - 32768
        if denominator <= 0:
            raise RuntimeError("raw Hall Z is outside the calibration domain")
        ratios.append(math.hypot(x - 32768, y - 32768) / denominator)
    maximum = max(ratios)
    if maximum <= 0:
        raise RuntimeError("raw Hall range is zero")
    gain = min(15.0, 2.0 / maximum)
    return (
        int(1023 * gain / 15),
        int((1.09 / gain) * 65535 / 3),
        int((1.57 / gain) * 65535 / 3),
        int((2.91 / gain) * 65535 / 3),
        int((7.28 / gain) * 65535 / 3),
    )


class CenterTracker:
    def __init__(self, stick):
        self.stick = stick
        self.pending = None
        self.stable = 0
        self.window = []
        self.returns = []
        self.covered = set()
        self.trace = []
        self.logical_min = [None, None]
        self.logical_max = [None, None]
        self.reference_window = []
        self.logical_reference = None
        self.raw_reference = None

    def observe(self, sample):
        self.trace.append(dict(sample))
        for axis, key in enumerate(("logicalX", "logicalY")):
            value = sample[key]
            self.logical_min[axis] = value if self.logical_min[axis] is None else min(self.logical_min[axis], value)
            self.logical_max[axis] = value if self.logical_max[axis] is None else max(self.logical_max[axis], value)
        if self.logical_reference is None:
            # Establish the excursion origin at rest, not at the old calibration's
            # logical zero. This reference never becomes the sensor centre candidate.
            if any(abs(sample[key]) > CENTER_RETURN_MAX for key in ("logicalX", "logicalY")):
                self.reference_window.clear()
                return
            self.reference_window.append(dict(sample))
            while any(max(r[key] for r in self.reference_window) - min(r[key] for r in self.reference_window)
                      > CENTER_STABLE_RAW_SPREAD for key in ("rawX", "rawY")):
                self.reference_window.pop(0)
            if len(self.reference_window) >= CENTER_STABLE_SAMPLE_GOAL:
                self.logical_reference = tuple(sum(r[key] for r in self.reference_window) // len(self.reference_window)
                                               for key in ("logicalX", "logicalY"))
                self.raw_reference = tuple(sum(r[key] for r in self.reference_window) // len(self.reference_window)
                                           for key in ("rawX", "rawY"))
                self.reference_window.clear()
            return
        direction = reached_direction(self.stick, sample["logicalX"] - self.logical_reference[0],
                                      sample["logicalY"] - self.logical_reference[1])
        if direction and direction not in self.covered and self.pending is None:
            self.pending = direction
            self.stable = 0
        if self.pending is None:
            return
        if abs(sample["logicalX"]) <= CENTER_RETURN_MAX and abs(sample["logicalY"]) <= CENTER_RETURN_MAX:
            self.window.append((sample["rawX"], sample["rawY"]))
            # Keep only the contiguous suffix whose raw axes have settled.
            while any(max(p[axis] for p in self.window) - min(p[axis] for p in self.window)
                      > CENTER_STABLE_RAW_SPREAD for axis in (0, 1)):
                self.window.pop(0)
            self.stable = len(self.window)
            if self.stable >= CENTER_STABLE_SAMPLE_GOAL:
                self.covered.add(self.pending)
                self.returns.append(tuple(sum(p[axis] for p in self.window) // len(self.window)
                                          for axis in (0, 1)))
                self.pending = None
                self.stable = 0
                self.window.clear()
        else:
            self.stable = 0
            self.window.clear()

    @property
    def complete(self):
        return len(self.covered) == len(CENTER_DIRECTIONS)

    def progress(self):
        return {
            "coveredDirections": [name for name in CENTER_DIRECTIONS if name in self.covered],
            "directionCount": len(self.covered),
            "directionGoal": len(CENTER_DIRECTIONS),
            "pendingDirection": self.pending,
            "stableSamples": self.stable if self.logical_reference is not None else len(self.reference_window),
            "stableGoal": CENTER_STABLE_SAMPLE_GOAL,
            "stage": "reference" if self.logical_reference is None else "settling" if self.pending else "excursion",
            "logicalReference": list(self.logical_reference) if self.logical_reference is not None else None,
            "physicalReference": list(physical_axes(self.stick, *self.logical_reference))
                                 if self.logical_reference is not None else None,
            "logicalMinimum": list(self.logical_min),
            "logicalMaximum": list(self.logical_max),
            "thresholds": {"cardinalExclusive": CENTER_CARDINAL_MIN,
                           "diagonalExclusive": CENTER_DIAGONAL_MIN,
                           "returnInclusive": CENTER_RETURN_MAX},
        }

    def result(self):
        if not self.complete:
            return None
        spread_x = max(value[0] for value in self.returns) - min(value[0] for value in self.returns)
        spread_y = max(value[1] for value in self.returns) - min(value[1] for value in self.returns)
        if max(spread_x, spread_y) > 256:
            raise RuntimeError("stick returns are too inconsistent for a center candidate")
        center = (sum(value[0] for value in self.returns) // len(self.returns),
                  sum(value[1] for value in self.returns) // len(self.returns))
        return {"centerWords": list(center), "centerHex": "".join(f"{word:04X}" for word in center),
                "excursionReference": {"logical": list(self.logical_reference), "raw": list(self.raw_reference)},
                "returnSpread": [spread_x, spread_y],
                "returns": [list(value) for value in self.returns]}


class RangeTracker:
    """Retain raw measurements and select the eight sensor-coordinate table entries."""

    def __init__(self, stick, center):
        self.stick = stick
        self.center = tuple(center)
        self.trace = []
        self.bin_counts = [0] * RANGE_BIN_COUNT
        self.slot_counts = [0] * 8
        self.previous_angle = None
        self.travel = 0.0

    @staticmethod
    def distance(first, second):
        return abs((first - second + 180) % 360 - 180)

    def observe(self, sample):
        required = ("timestampNs", "generation", "sequence", "length", "dropped",
                    "logicalX", "logicalY", "rawX", "rawY", "rawZ")
        if sample.get("length") != 26 or any(key not in sample for key in required):
            raise RuntimeError("malformed 26-byte calibration report")
        record = {key: int(sample[key]) for key in required}
        try:
            dx, dy = record["rawX"] - self.center[0], record["rawY"] - self.center[1]
            radius = math.hypot(dx, dy)
            raw_angle = math.degrees(math.atan2(dy, dx)) % 360
        except (OverflowError, ValueError):
            raise RuntimeError("raw Hall arithmetic failure") from None
        if not math.isfinite(radius) or not math.isfinite(raw_angle):
            raise RuntimeError("raw Hall arithmetic failure")
        record.update({"traceIndex": len(self.trace), "rawRadius": radius,
                       "rawAngle": raw_angle})
        self.trace.append(record)
        # Near centre, tiny Hall noise can sweep through arbitrary angles. Retain
        # it as evidence, but count only sufficiently deflected samples toward
        # outer coverage/turns, and never bridge an excursion through the centre.
        if radius < MIN_OUTER_RADIUS:
            self.previous_angle = None
            return
        angle = raw_angle
        self.bin_counts[int(angle // (360 / RANGE_BIN_COUNT)) % RANGE_BIN_COUNT] += 1
        for slot, raw_target in enumerate(RIGHT_SLOT_ANGLES):
            if self.distance(angle, raw_target) <= 5:
                self.slot_counts[slot] += 1
        if self.previous_angle is not None:
            delta = (angle - self.previous_angle + 180) % 360 - 180
            if abs(delta) < 30:
                self.travel += delta
        self.previous_angle = angle

    @property
    def turns(self):
        return abs(self.travel) / 360

    @property
    def complete(self):
        return (self.turns >= RANGE_TURN_GOAL and
                min(self.bin_counts) >= MIN_BIN_SAMPLES and
                min(self.slot_counts) >= MIN_SLOT_SAMPLES)

    def progress(self):
        return {
            "turns": round(self.turns, 3),
            "turnGoal": RANGE_TURN_GOAL,
            "coveredHeadings": sum(value >= MIN_SLOT_SAMPLES for value in self.slot_counts),
            "headingGoal": 8,
            "samplesPerHeading": list(self.slot_counts),
            "coveredSectors": sum(value >= MIN_BIN_SAMPLES for value in self.bin_counts),
            "sectorGoal": RANGE_BIN_COUNT,
        }

    @staticmethod
    def _percentile(values, fraction):
        ordered = sorted(values)
        if not ordered:
            raise RuntimeError("sparse raw-space sector")
        return ordered[round((len(ordered) - 1) * fraction)]

    def _candidate(self, triples, selected, algorithm):
        derived = derived_words(triples)
        words = [value for triple in triples for value in triple] + list(derived)
        return {"available": True, "algorithm": algorithm,
                "triples": [list(value) for value in triples],
                "selectedTraceIndices": list(selected), "derivedWords": list(derived),
                "tableWords": words, "tableHex": "".join(f"{word:04X}" for word in words)}

    @staticmethod
    def _hall_metrics(row):
        z = row["rawZ"] - 32768
        if z <= 0:
            raise RuntimeError("raw Hall Z is outside the calibration domain")
        ratio = math.hypot(row["rawX"] - 32768, row["rawY"] - 32768) / z
        if ratio <= 0:
            raise RuntimeError("raw Hall range is zero")
        return row["rawRadius"], z, ratio

    def _repeat_measurements(self):
        laps, current = [], []
        previous, travel, direction = None, 0.0, 0
        for row in self.trace:
            if row["rawRadius"] < MIN_OUTER_RADIUS:
                laps, current, previous, travel, direction = [], [], None, 0.0, 0
                continue
            angle = row["rawAngle"]
            delta = 0 if previous is None else (angle - previous + 180) % 360 - 180
            if abs(delta) >= 30:
                laps, current, travel, direction = [], [], 0.0, 0
                delta = 0
            previous = angle
            current.append(row)
            travel += delta
            if abs(travel) >= 360 - 1e-9:
                next_direction = 1 if travel > 0 else -1
                if direction and next_direction != direction:
                    laps = []
                direction = next_direction
                laps.append(current)
                # Retain the observed boundary; carry angular overshoot without
                # inventing an interpolated XYZ sample.
                current = [row]
                travel -= direction * 360
        if len(laps) < RANGE_TURN_GOAL:
            raise RuntimeError("range rotations were interrupted; retry with four continuous circles in one direction")
        measured = laps[1:RANGE_TURN_GOAL]
        summaries = []
        for lap in measured:
            bins = [[] for _ in range(RANGE_REPEAT_BINS)]
            for row in lap:
                bins[int(row["rawAngle"] // (360 / RANGE_REPEAT_BINS)) % RANGE_REPEAT_BINS].append(row)
            if min(map(len, bins)) < MIN_REPEAT_SAMPLES:
                raise RuntimeError("range rotations were too fast or uneven; retry with slower complete circles")
            summaries.append([[self._percentile([self._hall_metrics(r)[axis] for r in rows], 0.75)
                               for axis in range(3)] for rows in bins])
        spreads = [[max(lap[sector][axis] for lap in summaries) /
                    min(lap[sector][axis] for lap in summaries)
                    for axis in range(3)] for sector in range(RANGE_REPEAT_BINS)]
        if max(max(values) for values in spreads) > MAX_REPEAT_RATIO:
            raise RuntimeError("range rotations disagree; retry with light, steady rim contact without pressing harder")
        quality = {"comparedRotations": len(measured), "sectorDegrees": 360 / RANGE_REPEAT_BINS,
                   "minimumSamplesPerSector": MIN_REPEAT_SAMPLES, "maximumAllowedRatio": MAX_REPEAT_RATIO,
                   "metrics": ["radius", "hallZOffset", "hallXYOverZ"],
                   "lapSectorQuartiles": summaries, "sectorRatios": spreads,
                   "traceIntervals": [[lap[0]["traceIndex"], lap[-1]["traceIndex"]] for lap in measured]}
        return measured, quality

    def result(self):
        if not self.complete:
            return None
        outer_trace = [r for r in self.trace if r["rawRadius"] >= MIN_OUTER_RADIUS]
        bin_outer = []
        for sector in range(RANGE_BIN_COUNT):
            radii = [r["rawRadius"] for r in outer_trace
                     if int(r["rawAngle"] // 5) % RANGE_BIN_COUNT == sector]
            bin_outer.append(self._percentile(radii, 0.75))
        if min(bin_outer) < MIN_OUTER_RADIUS:
            raise RuntimeError("weak outer-gate contact")
        if max(bin_outer) / min(bin_outer) > MAX_RADIAL_RATIO:
            raise RuntimeError("inconsistent outer-gate radii")
        laps, repeat_quality = self._repeat_measurements()
        triples, selected = [], []
        for raw_target in RIGHT_SLOT_ANGLES:
            by_lap = [[r for r in lap if self.distance(r["rawAngle"], raw_target) <= 5] for lap in laps]
            if any(not rows for rows in by_lap):
                raise RuntimeError("sparse repeated range heading; retry with slower complete circles")
            quartiles = [[self._percentile([self._hall_metrics(r)[axis] for r in rows], 0.75)
                          for axis in range(3)] for rows in by_lap]
            if any(max(q[axis] for q in quartiles) / min(q[axis] for q in quartiles) > MAX_REPEAT_RATIO
                   for axis in range(3)):
                raise RuntimeError("range headings disagree; retry with light, steady rim contact")
            # An isolated spike can be invisible to lap quartiles yet win the
            # angle-first selection. Require each actual selected observation to
            # agree with every lap's local radius, Z and gain-ratio quartiles.
            nearby = list({r["traceIndex"]: r for rows in by_lap for r in rows
                           if all(max(q[axis] for q in quartiles) / MAX_REPEAT_RATIO <= value <=
                                  min(q[axis] for q in quartiles) * MAX_REPEAT_RATIO
                                  for axis, value in enumerate(self._hall_metrics(r)))}.values())
            if not nearby:
                raise RuntimeError("no repeatable outer-range sample; retry with light, steady rim contact")
            cutoff = self._percentile([r["rawRadius"] for r in nearby], 0.75)
            outer = [r for r in nearby if r["rawRadius"] >= cutoff]
            target_radius = self._percentile([r["rawRadius"] for r in outer], 0.5)
            chosen = min(outer, key=lambda r: (self.distance(r["rawAngle"], raw_target),
                                                abs(r["rawRadius"] - target_radius), r["traceIndex"]))
            triples.append((chosen["rawX"], chosen["rawY"], chosen["rawZ"]))
            selected.append(chosen["traceIndex"])
        proposed = self._candidate(triples, selected, "raw-space-repeatable-outer-quartile")
        trace_json = json.dumps(self.trace, sort_keys=True, separators=(",", ":")).encode()
        return {
            "stick": self.stick,
            "centerWords": list(self.center),
            "slotRawAngles": list(RIGHT_SLOT_ANGLES), "traceSampleCount": len(self.trace),
            "traceSha256": hashlib.sha256(trace_json).hexdigest(),
            "quality": {"turns": self.turns, "sectorCounts": list(self.bin_counts),
                        "repeatability": repeat_quality,
                        "outerRadiusPerSector": bin_outer, "minimumOuterRadius": min(bin_outer),
                        "maximumOuterRadius": max(bin_outer),
                        "outerRadiusRatio": max(bin_outer) / min(bin_outer)},
            "rawSpaceCandidate": proposed,
        }


class CaptureSession:
    def __init__(self, token, stick, phase, center=None):
        if stick not in MODE_COMMANDS:
            raise ValueError("invalid stick")
        if phase not in PHASES:
            raise ValueError("invalid calibration phase")
        self.token = str(token)
        self.stick = stick
        self.phase = phase
        self.tracker = CenterTracker(stick) if phase == "center" else RangeTracker(stick, center)
        self.records = []
        self.configuration = {}
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, name="rsinput-calibration-capture", daemon=True)
        self.state = {
            "active": True,
            "stick": stick,
            "phase": phase,
            "sampleCount": 0,
            "rawSampleCount": 0,
            "generationGaps": 0,
            "sequenceGaps": 0,
            "captureGaps": 0,
            "droppedBaseline": None,
            "dropped": None,
            "error": "",
            "latest": None,
            "complete": False,
            "progress": self.tracker.progress(),
            "result": None,
        }

    def start(self):
        self.thread.start()

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=3)
        if self.thread.is_alive():
            raise RuntimeError("calibration capture did not stop")
        return self.snapshot()

    def _update(self, **values):
        with self.lock:
            self.state.update(values)

    def _run(self):
        path = policy.device_path()
        if not path:
            self._update(active=False, error="Calibration transport is unavailable")
            return
        fd = None
        previous_generation = None
        previous_sequence = None
        previous_raw_timestamp = None
        baseline = None
        try:
            self.configuration = policy.capture_configuration()
            fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
            if os.write(fd, mode_record(self.stick, True)) != COMMAND.size:
                raise RuntimeError("short calibration mode write")
            poller = select.poll()
            poller.register(fd, select.POLLIN | select.POLLERR | select.POLLHUP)
            deadline = time.monotonic() + MAX_SESSION_SECONDS
            while not self.stop_event.is_set():
                if time.monotonic() >= deadline:
                    raise RuntimeError(self.timeout_reason())
                events = poller.poll(100)
                if not events:
                    continue
                if events[0][1] & (select.POLLERR | select.POLLHUP):
                    raise RuntimeError("calibration transport disconnected")
                raw = os.read(fd, SAMPLE.size)
                self.records.append(raw.hex())
                sample = decode_sample(raw, self.stick)
                dropped = sample["dropped"]
                if baseline is None:
                    baseline = dropped
                generation_gap = 0 if previous_generation is None else max(
                    0, ((sample["generation"] - previous_generation) & 0xffffffff) - 1
                )
                expected = 1 if previous_sequence == 255 else (previous_sequence or 0) + 1
                sequence_gap = 0 if previous_sequence is None else (sample["sequence"] - expected) % 255
                previous_generation = sample["generation"]
                previous_sequence = sample["sequence"]
                if sample["length"] == 26:
                    capture_gap = int(previous_raw_timestamp is not None and
                                      sample["timestampNs"] - previous_raw_timestamp > MAX_CAPTURE_GAP_NS)
                    previous_raw_timestamp = sample["timestampNs"]
                    self.tracker.observe(sample)
                else:
                    capture_gap = 0
                complete = self.tracker.complete
                with self.lock:
                    self.state["sampleCount"] += 1
                    if sample["length"] == 26:
                        self.state["rawSampleCount"] += 1
                    self.state["generationGaps"] += generation_gap
                    self.state["sequenceGaps"] += sequence_gap
                    self.state["captureGaps"] += capture_gap
                    self.state["droppedBaseline"] = baseline
                    self.state["dropped"] = dropped
                    self.state["latest"] = sample
                    self.state["complete"] = complete
                    self.state["progress"] = self.tracker.progress()
                    self.state["result"] = self.tracker.result()
                    if dropped != baseline or generation_gap or sequence_gap or capture_gap:
                        self.state["error"] = "Calibration samples were dropped"
                        self.stop_event.set()
                    elif complete:
                        self.stop_event.set()
        except (OSError, RuntimeError) as error:
            self._update(error=str(error))
        finally:
            if fd is not None:
                try:
                    if os.write(fd, mode_record(self.stick, False)) != COMMAND.size:
                        raise OSError("short calibration end write")
                except OSError as error:
                    prior = self.snapshot()["error"]
                    self._update(error=f"{prior + '; ' if prior else ''}Could not end calibration mode: {error}")
                os.close(fd)
            try:
                state = self.snapshot()
                self._save_capture(state)
            except (OSError, ValueError) as error:
                self._update(error=f"Could not save calibration measurements: {error}")
            self._update(active=False)

    def timeout_reason(self):
        if not self.state["rawSampleCount"]:
            return f"{self.stick} {self.phase}: no 26-byte raw reports received"
        progress = self.tracker.progress()
        if self.phase == "center":
            if progress["stage"] == "reference":
                return (f"{self.stick} center: resting reference did not settle "
                        f"({progress['stableSamples']}/{CENTER_STABLE_SAMPLE_GOAL} stable reports); "
                        f"logical X/Y min {progress['logicalMinimum']}, max {progress['logicalMaximum']}")
            if progress["pendingDirection"]:
                return (f"{self.stick} center: return did not settle after {progress['pendingDirection']} "
                        f"({progress['stableSamples']}/{CENTER_STABLE_SAMPLE_GOAL} stable reports)")
            return (f"{self.stick} center: excursion coverage incomplete "
                    f"({progress['directionCount']}/8); logical X/Y min {progress['logicalMinimum']}, "
                    f"max {progress['logicalMaximum']}; requires >{CENTER_CARDINAL_MIN} cardinal "
                    f"or >{CENTER_DIAGONAL_MIN} on both diagonal axes relative to resting reference "
                    f"{progress['logicalReference']}")
        return (f"{self.stick} range: coverage incomplete; {progress['turns']}/{RANGE_TURN_GOAL} turns, "
                f"{progress['coveredSectors']}/{RANGE_BIN_COUNT} sectors, "
                f"{progress['coveredHeadings']}/8 headings")

    def _save_capture(self, state):
        path = journal_path(self.token).with_name(
            f"capture-{token_hash(self.token)}-{self.stick}-{self.phase}.json")
        artifact = {"schemaVersion": 2, "stick": self.stick, "phase": self.phase,
                    "configuration": self.configuration, "state": state,
                    "result": state["result"], "trace": self.tracker.trace,
                    "abiRecordsHex": self.records}
        data = json.dumps(artifact, sort_keys=True, separators=(",", ":")) + "\n"
        make_directory(path.parent)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        sync_directory(path.parent)
        evidence = {"capturePath": str(path), "captureSha256": hashlib.sha256(data.encode()).hexdigest()}
        self._update(**evidence)
        if state["result"] is not None:
            self._update(result=dict(state["result"], **evidence))


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def journal_path(token):
    return JOURNAL_ROOT / f"commit-{token_hash(token)}.ndjson"


def recorded_outcome(token):
    """Recover terminal state, conservatively, without ever retrying a write."""
    path = journal_path(token)
    if not path.exists():
        return None
    try:
        events = [json.loads(line) for line in path.read_text().splitlines()]
        if events and events[-1].get("outcome") == "all-frames-transmitted":
            return {"state": "applied", "error": ""}
        if events and not any(event.get("event") == "before-write" for event in events):
            return {"state": "failed", "error": events[-1].get("error") or "Apply did not start"}
    except (OSError, ValueError):
        pass
    return {"state": "uncertain", "error": ""}


def write_calibration(token, results):
    """One durable write attempt. The journal is claimed before opening the UART."""
    path = policy.device_path()
    if not policy.uses_mcu() or not path:
        raise RuntimeError("Calibration transport is unavailable")
    frames = []
    for stick in ("left", "right"):
        center = results[(stick, "center")]["centerWords"]
        table = results[(stick, "range")]["rawSpaceCandidate"]["tableWords"]
        center_command, table_command = DATA_COMMANDS[stick]
        for command, words in ((MODE_COMMANDS[stick], [1]), (center_command, center),
                               (table_command, table), (0xA0, [0])):
            payload = (bytes(words) if command in MODE_COMMANDS.values()
                       else b"".join(int(word).to_bytes(2, "big") for word in words))
            frames.append((command, payload, COMMAND.pack(
                ABI_VERSION, command, len(payload), payload.ljust(58, b"\0"))))
    journal = journal_path(token)
    make_directory(journal.parent)
    # Exclusive creation is also the durable one-shot guard after a restart.
    with journal.open("x"):
        pass
    # Persist the directory entry as well as the file before any transmission.
    sync_directory(journal.parent)
    append_journal(journal, {"event": "start", "outcome": "unknown",
                             "interCommandDelaySeconds": WRITE_DELAY_SECONDS,
                             "captures": {f"{stick}-{phase}": result
                                          for (stick, phase), result in results.items()}})
    fd = None
    try:
        fd = os.open(path, os.O_RDWR | os.O_CLOEXEC)
        for sequence, (command, payload, frame) in enumerate(frames, 1):
            append_journal(journal, {"event": "before-write", "outcome": "unknown",
                                     "sequence": sequence, "opcodeHex": f"{command:02X}",
                                     "payloadHex": payload.hex().upper(),
                                     "payloadSha256": hashlib.sha256(payload).hexdigest(),
                                     "frameSha256": hashlib.sha256(frame).hexdigest()})
            if os.write(fd, frame) != COMMAND.size:
                raise RuntimeError(f"Short calibration write at command {sequence}")
            append_journal(journal, {"event": "after-write", "outcome": "transmitted",
                                     "sequence": sequence, "opcodeHex": f"{command:02X}"})
            time.sleep(WRITE_DELAY_SECONDS)
    except BaseException as error:
        append_journal(journal, {"event": "finish", "outcome": "unknown", "error": str(error)})
        raise
    finally:
        if fd is not None:
            os.close(fd)
    append_journal(journal, {"event": "finish", "outcome": "all-frames-transmitted"})


STEPS = (("left", "center"), ("left", "range"), ("right", "center"), ("right", "range"))


class CalibrationManager:
    """Own the four measurement steps and the single explicit Apply operation.

    RPC handlers serialize transitions under lock. Capture and Apply have bounded
    workers; neither waits for the UI, and Apply does not block the control daemon.
    Only completed, durably saved captures can advance the session.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.token = None
        self.state = "idle"
        self.error = ""
        self.step = 0
        self.capture = None
        self.results = {}
        self.writer = None

    def _start_step(self):
        stick, phase = STEPS[self.step]
        center = self.results[(stick, "center")]["centerWords"] if phase == "range" else None
        self.capture = CaptureSession(self.token, stick, phase, center)
        self.state = "measuring"
        self.capture.start()

    def _snapshot(self):
        capture = self.capture.snapshot() if self.capture else None
        if self.state == "measuring" and capture and not capture["active"]:
            if capture["error"] or not capture["complete"]:
                self.state, self.error = "failed", capture["error"] or "Capture stopped"
            else:
                self.state = "measured"
        actions = {
            "idle": ["start"], "measuring": ["cancel"], "measured": ["continue", "cancel"],
            "ready": ["apply", "cancel"], "applying": [],
            "applied": ["start"], "uncertain": ["start"], "failed": ["start"],
            "cancelled": ["start"],
        }[self.state]
        return {"state": self.state, "error": self.error, "actions": actions,
                "step": self.step, "totalSteps": len(STEPS),
                "stick": STEPS[self.step][0], "phase": STEPS[self.step][1],
                "progress": capture["progress"] if capture else {}}

    def dispatch(self, operation, token, step=None):
        if operation not in {"start", "continue", "cancel", "apply", "status"}:
            raise ValueError("Invalid calibration operation")
        if not isinstance(token, str) or not token or len(token) > 128:
            raise ValueError("A calibration session token is required")
        with self.lock:
            self._snapshot()
            if token != self.token:
                # A live session cannot be displaced, including while Apply runs.
                if self.state == "applying":
                    raise RuntimeError("Another calibration session is active")
                recovered = recorded_outcome(token)
                if recovered:
                    return {**recovered, "actions": ["start"], "step": 3, "totalSteps": 4,
                            "stick": "right", "phase": "range", "progress": {}}
                if operation != "start":
                    return {"state": "failed", "error": "Calibration session expired",
                            "actions": ["start"], "step": 0, "totalSteps": 4,
                            "stick": "left", "phase": "center", "progress": {}}
                if not policy.uses_mcu() or policy.device_path() is None:
                    raise RuntimeError("MCU calibration is unavailable")
                if self.capture:
                    self.capture.stop()
                policy.prepare_sticks(Path("/sys/module/rsinput/parameters"))
                self.token, self.step, self.results, self.error = token, 0, {}, ""
                self._start_step()
            snapshot = self._snapshot()
            if operation in {"status", "start"}:
                return snapshot  # Duplicate start never restarts a capture.
            if operation == "continue" and (step != self.step or self.state == "ready"):
                return snapshot  # An old/double-clicked Continue cannot skip a step.
            if operation not in snapshot["actions"]:
                if operation in {"apply", "cancel"} and self.state in {
                        "applying", "applied", "uncertain", "failed", "cancelled"}:
                    return snapshot
                raise RuntimeError(f"Cannot {operation} calibration while {self.state}")
            if operation == "cancel":
                if self.capture:
                    self.capture.stop()
                self.capture, self.results, self.state = None, {}, "cancelled"
            elif operation == "continue":
                result = self.capture.snapshot()["result"]
                self.results[STEPS[self.step]] = result
                if self.step == len(STEPS) - 1:
                    self.capture, self.state = None, "ready"
                else:
                    self.step += 1
                    self._start_step()
            elif operation == "apply":
                self.state = "applying"
                self.writer = threading.Thread(target=self._apply, name="rsinput-calibration-apply", daemon=True)
                self.writer.start()
            return self._snapshot()

    def _apply(self):
        error = ""
        try:
            write_calibration(self.token, self.results)
        except Exception as exc:
            error = str(exc)
        with self.lock:
            outcome = recorded_outcome(self.token) or {"state": "failed", "error": error}
            self.state, self.error = outcome["state"], error or outcome["error"]
