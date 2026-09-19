"""Privileged rsinput MCU calibration capture and explicit commit transport."""

import glob
import hashlib
import json
import math
import os
from pathlib import Path
import select
import struct
import threading
import time


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
RIGHT_SLOT_ANGLES = (90, 180, 270, 0, 45, 135, 225, 315)
RAW_MOUNTING_ROTATION = {"left": 180, "right": 180}
DATA_COMMANDS = {"left": (0xA2, 0xA3), "right": (0xA5, 0xA6)}
WRITE_DELAY_SECONDS = 1.0
RANGE_TURN_GOAL = 4
RANGE_BIN_COUNT = 72
MIN_BIN_SAMPLES = 3
MIN_SLOT_SAMPLES = 8
MIN_OUTER_RADIUS = 600
MAX_RADIAL_RATIO = 2.2
MAX_CAPTURE_GAP_NS = 100_000_000
MAX_SESSION_SECONDS = 120
JOURNAL_ROOT = Path("/var/lib/armada/calibration")
def device_path():
    matches = sorted(glob.glob("/dev/rsinput-calibration-*"))
    if len(matches) != 1:
        return None
    return matches[0]

def mode_record(stick, enabled):
    if stick not in MODE_COMMANDS:
        raise ValueError("invalid stick")
    command = MODE_COMMANDS[stick] if enabled else 0xA0
    payload = b"\1" if enabled else b"\0"
    return COMMAND.pack(ABI_VERSION, command, 1, payload.ljust(58, b"\0"))


def append_journal(path, event):
    event["monotonicNs"] = time.monotonic_ns()
    path.parent.mkdir(parents=True, exist_ok=True)
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
    return (-x, -y) if stick == "left" else (x, y)


def reached_direction(stick, x, y):
    x, y = physical_axes(stick, x, y)
    checks = (
        ("up-left", x < -500 and y < -500),
        ("up-right", x > 500 and y < -500),
        ("down-left", x < -500 and y > 500),
        ("down-right", x > 500 and y > 500),
        ("left", x < -700), ("right", x > 700),
        ("up", y < -700), ("down", y > 700),
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
        self.returns = []
        self.covered = set()

    def observe(self, sample):
        direction = reached_direction(self.stick, sample["logicalX"], sample["logicalY"])
        if direction and direction not in self.covered and self.pending is None:
            self.pending = direction
            self.stable = 0
        if self.pending is None:
            return
        if abs(sample["logicalX"]) <= 350 and abs(sample["logicalY"]) <= 350:
            self.stable += 1
            if self.stable >= CENTER_STABLE_SAMPLE_GOAL:
                self.covered.add(self.pending)
                self.returns.append((sample["rawX"], sample["rawY"]))
                self.pending = None
                self.stable = 0
        else:
            self.stable = 0

    @property
    def complete(self):
        return len(self.covered) == len(CENTER_DIRECTIONS)

    def progress(self):
        return {
            "coveredDirections": [name for name in CENTER_DIRECTIONS if name in self.covered],
            "directionCount": len(self.covered),
            "directionGoal": len(CENTER_DIRECTIONS),
            "pendingDirection": self.pending,
            "stableSamples": self.stable,
            "stableGoal": CENTER_STABLE_SAMPLE_GOAL,
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
                "returnSpread": [spread_x, spread_y],
                "returns": [list(value) for value in self.returns]}


class RangeTracker:
    """Retain an immutable raw trace and derive legacy and raw-space candidates."""

    def __init__(self, stick, center):
        self.stick = stick
        self.center = tuple(center)
        self.mounting_rotation = RAW_MOUNTING_ROTATION[stick]
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
        physical_angle = (raw_angle + self.mounting_rotation) % 360
        record.update({"traceIndex": len(self.trace), "rawRadius": radius,
                       "rawAngle": raw_angle, "physicalAngle": physical_angle})
        self.trace.append(record)
        angle = physical_angle
        self.bin_counts[int(angle // (360 / RANGE_BIN_COUNT)) % RANGE_BIN_COUNT] += 1
        for slot, raw_target in enumerate(RIGHT_SLOT_ANGLES):
            physical_target = (raw_target + self.mounting_rotation) % 360
            if self.distance(angle, physical_target) <= 5:
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

    def result(self):
        if not self.complete:
            return None
        bin_outer = []
        for sector in range(RANGE_BIN_COUNT):
            radii = [r["rawRadius"] for r in self.trace
                     if int(r["physicalAngle"] // 5) % RANGE_BIN_COUNT == sector]
            bin_outer.append(self._percentile(radii, 0.75))
        if min(bin_outer) < MIN_OUTER_RADIUS:
            raise RuntimeError("weak outer-gate contact")
        if max(bin_outer) / min(bin_outer) > MAX_RADIAL_RATIO:
            raise RuntimeError("inconsistent outer-gate radii")
        triples, selected = [], []
        for raw_target in RIGHT_SLOT_ANGLES:
            physical_target = (raw_target + self.mounting_rotation) % 360
            nearby = [r for r in self.trace if self.distance(r["physicalAngle"], physical_target) <= 5]
            cutoff = self._percentile([r["rawRadius"] for r in nearby], 0.75)
            outer = [r for r in nearby if r["rawRadius"] >= cutoff]
            target_radius = self._percentile([r["rawRadius"] for r in outer], 0.5)
            chosen = min(outer, key=lambda r: (self.distance(r["physicalAngle"], physical_target),
                                                abs(r["rawRadius"] - target_radius), r["traceIndex"]))
            triples.append((chosen["rawX"], chosen["rawY"], chosen["rawZ"]))
            selected.append(chosen["traceIndex"])
        proposed = self._candidate(triples, selected, "raw-space-outer-quartile")
        trace_json = json.dumps(self.trace, sort_keys=True, separators=(",", ":")).encode()
        return {
            "stick": self.stick,
            "centerWords": list(self.center), "mountingRotationDegrees": self.mounting_rotation,
            "slotRawAngles": list(RIGHT_SLOT_ANGLES), "traceSampleCount": len(self.trace),
            "traceSha256": hashlib.sha256(trace_json).hexdigest(),
            "quality": {"turns": self.turns, "sectorCounts": list(self.bin_counts),
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
        path = device_path()
        if not path:
            self._update(active=False, error="Calibration transport is unavailable")
            return
        fd = None
        previous_generation = None
        previous_sequence = None
        previous_raw_timestamp = None
        baseline = None
        try:
            fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
            if os.write(fd, mode_record(self.stick, True)) != COMMAND.size:
                raise RuntimeError("short calibration mode write")
            poller = select.poll()
            poller.register(fd, select.POLLIN | select.POLLERR | select.POLLHUP)
            deadline = time.monotonic() + MAX_SESSION_SECONDS
            while not self.stop_event.is_set():
                if time.monotonic() >= deadline:
                    raise RuntimeError("calibration capture timed out")
                events = poller.poll(100)
                if not events:
                    continue
                if events[0][1] & (select.POLLERR | select.POLLHUP):
                    raise RuntimeError("calibration transport disconnected")
                sample = decode_sample(os.read(fd, SAMPLE.size), self.stick)
                dropped = sample["dropped"]
                if baseline is None:
                    baseline = dropped
                generation_gap = 0 if previous_generation is None else max(
                    0, sample["generation"] - previous_generation - 1
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
                    os.write(fd, mode_record(self.stick, False))
                except OSError:
                    pass
                os.close(fd)
            self._update(active=False)


class CaptureManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.session = None
        self.completed = {}

    def capability(self):
        return {"available": device_path() is not None}

    def begin(self, token, stick, phase):
        if not token:
            raise ValueError("calibration capture token is required")
        if device_path() is None:
            raise RuntimeError("MCU calibration is not supported on this device")
        with self.lock:
            if self.session and self.session.snapshot()["active"]:
                raise RuntimeError("another calibration capture is active")
            if stick == "left" and phase == "center":
                self.completed = {key: value for key, value in self.completed.items()
                                  if key[0] != str(token)}
            if phase == "range":
                center = self.completed.get((str(token), stick, "center"), {}).get("centerWords")
                if not center:
                    raise RuntimeError("a completed center capture is required before raw-space range capture")
            else:
                center = None
            self.session = CaptureSession(token, stick, phase, center)
            self.session.start()
            return self.session.snapshot()

    def status(self, token):
        with self.lock:
            if not self.session or self.session.token != str(token):
                raise RuntimeError("calibration capture session not found")
            return self.session.snapshot()

    def end(self, token):
        with self.lock:
            if not self.session or self.session.token != str(token):
                return False
            session = self.session
            self.session = None
        session.stop()
        state = session.snapshot()
        if state["complete"] and not state["error"] and state["result"]:
            token_hash = hashlib.sha256(str(token).encode()).hexdigest()[:16]
            capture_path = JOURNAL_ROOT / f"capture-{token_hash}-{state['stick']}-{state['phase']}.json"
            JOURNAL_ROOT.mkdir(parents=True, exist_ok=True)
            artifact = {"schemaVersion": 1, "stick": state["stick"], "phase": state["phase"],
                        "result": state["result"]}
            if state["phase"] == "range":
                artifact["trace"] = session.tracker.trace
            data = json.dumps(artifact, sort_keys=True, separators=(",", ":")) + "\n"
            tmp = capture_path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, capture_path)
            state["result"]["capturePath"] = str(capture_path)
            state["result"]["captureSha256"] = hashlib.sha256(data.encode()).hexdigest()
            with self.lock:
                self.completed[(str(token), state["stick"], state["phase"])] = state["result"]
        return True

    def commit(self, token):
        token = str(token or "")
        with self.lock:
            if self.session and self.session.snapshot()["active"]:
                raise RuntimeError("calibration capture is still active")
            results = {(stick, phase): self.completed.get((token, stick, phase))
                       for stick in MODE_COMMANDS for phase in PHASES}
        if any(result is None for result in results.values()):
            raise RuntimeError("all calibration steps must complete before apply")
        operations = []
        for stick in ("left", "right"):
            center = results[(stick, "center")]["centerWords"]
            table = results[(stick, "range")]["rawSpaceCandidate"]["tableWords"]
            center_command, table_command = DATA_COMMANDS[stick]
            operations.extend(((MODE_COMMANDS[stick], [1]), (center_command, center),
                               (table_command, table), (0xA0, [0])))
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
        journal = JOURNAL_ROOT / f"commit-{token_hash}.ndjson"
        if journal.exists():
            raise RuntimeError("this calibration session was already applied")
        path = device_path()
        if not path:
            raise RuntimeError("calibration transport is unavailable")
        frames = []
        for command, words in operations:
            payload = (bytes([words[0]]) if command in (0xA0, 0xA1)
                       else b"".join(int(word).to_bytes(2, "big") for word in words))
            frame = COMMAND.pack(ABI_VERSION, command, len(payload), payload.ljust(58, b"\0"))
            frames.append((command, payload, frame))
        append_journal(journal, {"event": "start", "outcome": "unknown", "tokenHash": token_hash,
                                 "interCommandDelaySeconds": WRITE_DELAY_SECONDS,
                                 "candidates": {
                                     stick: {"centerWords": results[(stick, "center")]["centerWords"],
                                             "centerReturns": results[(stick, "center")]["returns"],
                                             "centerCaptureSha256": results[(stick, "center")].get("captureSha256"),
                                             "tableWords": results[(stick, "range")]["rawSpaceCandidate"]["tableWords"],
                                             "rangeCaptureSha256": results[(stick, "range")].get("captureSha256"),
                                             "traceSha256": results[(stick, "range")].get("traceSha256")}
                                     for stick in ("left", "right")}})
        fd = os.open(path, os.O_RDWR | os.O_CLOEXEC)
        try:
            for sequence, (command, payload, frame) in enumerate(frames, 1):
                append_journal(journal, {"event": "before-write", "outcome": "unknown",
                                         "sequence": sequence, "opcodeHex": f"{command:02X}",
                                         "payloadHex": payload.hex().upper(),
                                         "payloadSha256": hashlib.sha256(payload).hexdigest(),
                                         "frameSha256": hashlib.sha256(frame).hexdigest()})
                if os.write(fd, frame) != COMMAND.size:
                    raise RuntimeError(f"short calibration write at command {sequence}")
                append_journal(journal, {"event": "after-write", "outcome": "transmitted",
                                         "sequence": sequence, "opcodeHex": f"{command:02X}"})
                time.sleep(WRITE_DELAY_SECONDS)
        except BaseException as error:
            append_journal(journal, {"event": "finish", "outcome": "unknown", "error": repr(error)})
            raise
        finally:
            os.close(fd)
        append_journal(journal, {"event": "finish", "outcome": "all-frames-transmitted"})
        return {"committed": True, "journal": str(journal), "outcome": "all-frames-transmitted"}
