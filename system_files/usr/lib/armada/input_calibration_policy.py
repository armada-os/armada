"""Shared policy for devices opting in to MCU stick calibration in their DT."""

import hashlib
import json
import os
import time
from functools import lru_cache
from pathlib import Path

DEVICE_TREE = Path('/sys/firmware/devicetree/base')
SOC_SERIAL = Path('/sys/devices/soc0/serial_number')
JOURNAL_ROOT = Path('/var/lib/armada/calibration')
OUTPUT_KEY = 'mcuOutput'


@lru_cache(maxsize=1)
def mcu_node():
    nodes = []
    for flag in DEVICE_TREE.rglob('mcu-calibration'):
        node = flag.parent
        if b'gamepad,rsinput' not in (node / 'compatible').read_bytes().split(b'\0'):
            continue
        enabled = True
        for ancestor in (node, *node.parents):
            status = ancestor / 'status'
            if status.exists() and status.read_bytes().rstrip(b'\0') not in (b'ok', b'okay'):
                enabled = False
            if ancestor == DEVICE_TREE:
                break
        if enabled:
            nodes.append(node)
    return nodes[0] if len(nodes) == 1 else None


def uses_mcu(backend='rsinput'):
    return backend == 'rsinput' and mcu_node() is not None


def stick_defaults():
    node = mcu_node()
    if node is None:
        return {}

    def word(name, default):
        path = node / name
        return int.from_bytes(path.read_bytes(), 'big') if path.exists() else default

    # Match rsinput probe defaults and the board's DT overrides.
    span, deadzone = word('axis-range', 0x580), word('axis-deadzone', 0)
    return {f'axis_{axis}_{name}': value
            for axis in ('leftx', 'lefty', 'rightx', 'righty')
            for name, value in {'min': -span, 'max': span, 'center': 0,
                                'deadzone': deadzone, 'antideadzone': 0}.items()}


def clean_config(params):
    if not uses_mcu(params.get('backend', 'rsinput')):
        return dict(params)
    if valid_output(params):
        return dict(params)
    return {key: value for key, value in params.items()
            if not key.startswith('axis_') and key != OUTPUT_KEY}


def output_binding():
    """Bind software measurements to this unit and every durable sensor-write attempt.

    The MCU writer exclusively creates and fsyncs a commit journal before opening
    the transport. Even an empty/uncertain attempt therefore invalidates old trim.
    Capture-only sessions do not change this generation. Never delete these journals.
    """
    serial = SOC_SERIAL.read_text().strip()
    if not serial:
        raise RuntimeError('Cannot identify the controller unit')
    try:
        attempts = sorted(p.name for p in JOURNAL_ROOT.iterdir()
                          if p.name.startswith('commit-') and p.suffix == '.ndjson')
    except FileNotFoundError:
        attempts = []
    identity = [serial, (DEVICE_TREE / 'compatible').read_bytes().hex(), attempts]
    return {'version': 1, 'generation': hashlib.sha256(
        json.dumps(identity, separators=(',', ':')).encode()).hexdigest()}


def valid_output(params):
    try:
        return params.get(OUTPUT_KEY) == output_binding()
    except (OSError, RuntimeError):
        return False


def restore_sticks(parameters, config):
    """Restore only a current, unit-bound output trim; otherwise neutral defaults."""
    values = stick_defaults()
    if config.exists():
        params = clean_config(json.loads(config.read_text()))
        if params.get('backend', 'rsinput') == 'rsinput':
            values.update({k: v for k, v in params.items() if k in values})
    for name, value in values.items():
        (parameters / name).write_text(str(int(value)), encoding='utf-8')
    (parameters / 'update_params').write_text('1', encoding='utf-8')


def prepare_sticks(parameters):
    """One live-session preparation; normal boot already has driver defaults."""
    for name, value in stick_defaults().items():
        (parameters / name).write_text(str(value), encoding='utf-8')
    (parameters / 'update_params').write_text('1', encoding='utf-8')


def wait_parameters(parameters):
    # rsinput applies ABS metadata on its next report, not at the sysfs write.
    deadline = time.monotonic() + 0.5
    while (parameters / 'update_params').read_text().strip() != '0':
        if time.monotonic() >= deadline:
            raise RuntimeError('Controller did not activate the output measurement ranges')
        time.sleep(0.01)



def physical_axes(stick, x, y):
    # Match the driver's sign conversion, including alternate stick mounting.
    node = mcu_node()
    prefix = "" if stick == "left" else "r"
    return tuple(value if node and (node / f"invert-{prefix}{axis}").exists() else -value
                 for axis, value in (("x", x), ("y", y)))


def device_path():
    matches = sorted(Path("/dev").glob("rsinput-calibration-*"))
    return str(matches[0]) if len(matches) == 1 else None


def capability(backend):
    mcu = uses_mcu(backend)
    # Preserve the existing trigger restrictions; stick support is DT-owned.
    compatible = DEVICE_TREE / "compatible"
    board = compatible.read_bytes().split(b"\0")[0] if compatible.exists() else b""
    trigger_read_only = mcu and board in (
        b"retroidpocket,rp6", b"retroidpocket,rpnova", b"ayn,thor")
    return {"sticks": "mcu" if mcu else "software",
            "available": device_path() is not None if mcu else backend is not None,
            "triggers": backend is not None and not trigger_read_only}


def capture_configuration():
    """Read the units and settings needed to interpret a failed or completed trace."""
    node = mcu_node()
    result = {"kernel": os.uname().release, "deviceNode": str(node) if node else None,
              "stickDefaults": stick_defaults(), "parameters": {}}
    for key, path in (("compatible", DEVICE_TREE / "compatible"),
                      ("imageVersion", Path("/usr/lib/armada/version"))):
        if path.exists():
            result[key] = path.read_text().replace("\0", " ").strip()
    result["invertedAxes"] = [name for name in ("invert-x", "invert-y", "invert-rx", "invert-ry")
                              if node and (node / name).exists()]
    parameters = Path("/sys/module/rsinput/parameters")
    for path in sorted(parameters.glob("*")):
        if path.name.startswith(("axis_", "trigger_")) or path.name == "update_params":
            result["parameters"][path.name] = path.read_text().strip()
    return result
