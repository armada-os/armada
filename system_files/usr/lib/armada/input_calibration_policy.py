"""Shared policy for devices opting in to MCU stick calibration in their DT."""

import os
import time
from functools import lru_cache
from pathlib import Path

DEVICE_TREE = Path('/sys/firmware/devicetree/base')
# Outer share of stick travel that already reads as full deflection.
STICK_OUTER_MARGIN_PERCENT = 5


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

    # Match rsinput probe defaults and the board's DT overrides, less the outer margin.
    span = word('axis-range', 0x580) * (100 - STICK_OUTER_MARGIN_PERCENT) // 100
    deadzone = word('axis-deadzone', 0)
    return {f'axis_{axis}_{name}': value
            for axis in ('leftx', 'lefty', 'rightx', 'righty')
            for name, value in {'min': -span, 'max': span, 'center': 0,
                                'deadzone': deadzone, 'antideadzone': 0}.items()}


def clean_config(params):
    if not uses_mcu(params.get('backend', 'rsinput')):
        return dict(params)
    # MCU sticks own their calibration; discard old host trim.
    return {key: value for key, value in params.items() if not key.startswith('axis_')}


def prepare_sticks(parameters):
    """Restore DT stick defaults without altering independent trigger settings."""
    for name, value in stick_defaults().items():
        (parameters / name).write_text(str(value), encoding='utf-8')
    (parameters / 'update_params').write_text('1', encoding='utf-8')


def wait_parameters(parameters):
    # rsinput applies ABS metadata on its next report, not at the sysfs write.
    deadline = time.monotonic() + 0.5
    while (parameters / 'update_params').read_text().strip() != '0':
        if time.monotonic() >= deadline:
            raise RuntimeError('Controller did not activate the stick ranges')
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
    # MCU opt-in changes stick ownership, not upstream software trigger support.
    return {"sticks": "mcu" if mcu else "software",
            "available": device_path() is not None if mcu else backend is not None,
            "triggers": backend is not None}


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
