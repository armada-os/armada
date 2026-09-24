"""Shared policy for devices opting in to MCU stick calibration in their DT."""

from functools import lru_cache
from pathlib import Path

DEVICE_TREE = Path('/sys/firmware/devicetree/base')


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
    return {key: value for key, value in params.items() if not key.startswith('axis_')}


def prepare_sticks(parameters):
    """One live-session preparation; normal boot already has driver defaults."""
    for name, value in stick_defaults().items():
        (parameters / name).write_text(str(value), encoding='utf-8')
    (parameters / 'update_params').write_text('1', encoding='utf-8')



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
