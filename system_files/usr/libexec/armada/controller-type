#!/usr/bin/env python3
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

CONFIG = Path("/etc/armada/controller.conf")
SERVICE = "org.shadowblip.InputPlumber"
IFACE = "org.shadowblip.Input.CompositeDevice"
DEVICE_ENV = "/usr/libexec/armada/device-env"
CONTROLLER_TYPES = {
    "deck-uhid": "Steam Deck",
    "xbox-series": "Xbox Series",
    "xb360": "Xbox 360",
    "ds5": "DualSense",
}


def available_types():
    try:
        result = subprocess.run(
            [DEVICE_ENV],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return list(CONTROLLER_TYPES)
    raw = ""
    for line in result.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "ARMADA_IP_TARGETS":
            try:
                raw = shlex.split(value)[0] if value.strip() else ""
            except ValueError:
                raw = value.strip()
            break
    types = []
    for item in raw.split(","):
        item = item.strip()
        if item in CONTROLLER_TYPES and item not in types:
            types.append(item)
    return types or list(CONTROLLER_TYPES)


def load_type(types):
    try:
        lines = CONFIG.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return types[0]
    value = ""
    for line in lines:
        key, sep, raw = line.partition("=")
        if sep and key.strip() == "controller_type":
            value = raw.strip()
            break
    return value if value in types else types[0]


def save_type(value):
    if value not in CONTROLLER_TYPES:
        raise ValueError(f"invalid controller type: {value}")
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG.with_name(f".{CONFIG.name}.tmp")
    tmp.write_text(f"controller_type={value}\n", encoding="utf-8")
    tmp.chmod(0o644)
    tmp.replace(CONFIG)


def composite_paths():
    try:
        result = subprocess.run(
            ["busctl", "--system", "tree", SERVICE],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    paths = []
    for line in result.stdout.splitlines():
        match = re.search(r"(/org/shadowblip/InputPlumber/CompositeDevice[0-9]+)", line)
        if match:
            paths.append(match.group(1))
    return sorted(set(paths))


def composite_name(path):
    try:
        result = subprocess.run(
            ["busctl", "--system", "get-property", SERVICE, path, IFACE, "Name"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    parts = result.stdout.strip().split('"')
    return parts[1] if len(parts) >= 2 else ""


def current_target_paths(path):
    try:
        result = subprocess.run(
            ["busctl", "--system", "get-property", SERVICE, path, IFACE, "TargetDevices"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return re.findall(r'"([^"]*)"', result.stdout)


def extra_targets(path):
    extras = []
    for target_path in current_target_paths(path):
        segment = target_path.rsplit("/", 1)[-1].rstrip("0123456789")
        if segment in ("keyboard", "mouse") and segment not in extras:
            extras.append(segment)
    return extras


def apply_type(value):
    paths = composite_paths()
    if not paths:
        return False
    ok = False
    for path in paths:
        targets = [value] + extra_targets(path)
        try:
            subprocess.run(
                ["busctl", "--system", "call", SERVICE, path, IFACE, "SetTargetDevices", "as", str(len(targets)), *targets],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )
            ok = True
        except (OSError, subprocess.SubprocessError):
            pass
    return ok


def apply_with_retry(value):
    for _ in range(30):
        if apply_type(value):
            return True
        time.sleep(0.5)
    return False


def main(argv):
    command = argv[1] if len(argv) > 1 else "get"
    if command == "get":
        print(load_type(available_types()))
        return 0
    if command == "set":
        types = available_types()
        if len(argv) != 3:
            print(f"usage: controller-type set <{'|'.join(types)}>", file=sys.stderr)
            return 2
        if argv[2] not in types:
            print(f"invalid controller type: {argv[2]}", file=sys.stderr)
            return 2
        if not apply_with_retry(argv[2]):
            return 1
        save_type(argv[2])
        return 0
    if command == "apply":
        return 0 if apply_with_retry(load_type(available_types())) else 1
    print("usage: controller-type get|set|apply", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
