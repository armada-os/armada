#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "$ROOT" <<'PY'
import ast
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
controller_type = root / "system_files/usr/libexec/armada/controller-type"
devices = root / "system_files/usr/share/inputplumber/devices"
device_env = root / "system_files/usr/libexec/armada/device-env"
device_quirks = root / "system_files/usr/lib/armada/devices"
udev_rules = root / "system_files/usr/lib/udev/rules.d/70-armada-inputplumber.rules"

# Controller targets come from per-device ARMADA_IP_TARGETS and are
# filtered against the types supported by controller-type.
module = ast.parse(controller_type.read_text(encoding="utf-8"))
controller_types = None
for node in module.body:
    if not isinstance(node, ast.Assign):
        continue
    if any(isinstance(target, ast.Name) and target.id == "CONTROLLER_TYPES" for target in node.targets):
        controller_types = ast.literal_eval(node.value)
if not isinstance(controller_types, dict) or not controller_types:
    raise SystemExit("controller-type has no CONTROLLER_TYPES map")

if "ARMADA_IP_TARGETS" not in device_env.read_text(encoding="utf-8"):
    raise SystemExit("device-env does not publish ARMADA_IP_TARGETS")


def ip_targets(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("ARMADA_IP_TARGETS="):
            return [item.strip() for item in line.split("=", 1)[1].split(",") if item.strip()]
    return None


default_targets = ip_targets(device_quirks / "defaults.conf")
if not default_targets:
    raise SystemExit("device quirks defaults.conf declares no ARMADA_IP_TARGETS")

for conf in sorted(device_quirks.glob("*.conf")):
    targets = ip_targets(conf)
    if targets is None:
        continue
    unknown = [item for item in targets if item not in controller_types]
    if unknown:
        raise SystemExit(
            f"{conf.relative_to(root)} offers unknown controller targets: {', '.join(unknown)}"
        )

shipped_names = set()
passthrough_paths = set()
for profile in sorted(devices.glob("*.yaml")):
    text = profile.read_text(encoding="utf-8")
    match = re.search(r"^name:\s*(.+?)\s*$", text, re.MULTILINE)
    if not match:
        raise SystemExit(f"{profile.relative_to(root)} has no top-level name")
    profile_name = match.group(1)
    shipped_names.add(profile_name)

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "passthrough: true":
            continue
        source_indent = len(line) - len(line.lstrip())
        phys_path = None
        for previous in reversed(lines[:index]):
            indent = len(previous) - len(previous.lstrip())
            if previous.strip().startswith("phys_path:"):
                phys_path = previous.split(":", 1)[1].strip()
                break
            if previous.strip() and indent < source_indent:
                break
        if not phys_path:
            raise SystemExit(f"{profile.relative_to(root)} has passthrough without phys_path")
        passthrough_paths.add(phys_path)

rules = udev_rules.read_text(encoding="utf-8")
missing_rules = sorted(path for path in passthrough_paths if path not in rules)
if missing_rules:
    raise SystemExit(f"udev rules are missing passthrough paths: {', '.join(missing_rules)}")

print(
    f"controller profile test passed "
    f"({len(shipped_names)} profiles, {len(passthrough_paths)} passthrough paths, "
    f"{len(default_targets)} default targets)"
)
PY
