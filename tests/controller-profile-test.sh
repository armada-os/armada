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
capability_maps = root / "system_files/usr/share/inputplumber/capability_maps"
udev_rules = root / "system_files/usr/lib/udev/rules.d/70-armada-inputplumber.rules"

module = ast.parse(controller_type.read_text(encoding="utf-8"))
profile_names = None
for node in module.body:
    if not isinstance(node, ast.Assign):
        continue
    if any(isinstance(target, ast.Name) and target.id == "ARMADA_PROFILE_NAMES" for target in node.targets):
        profile_names = ast.literal_eval(node.value)
if profile_names is None:
    raise SystemExit("controller-type has no ARMADA_PROFILE_NAMES assignment")

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

missing_names = sorted(shipped_names - profile_names)
if missing_names:
    raise SystemExit(f"controller-type is missing profile names: {', '.join(missing_names)}")

rules = udev_rules.read_text(encoding="utf-8")
missing_rules = sorted(path for path in passthrough_paths if path not in rules)
if missing_rules:
    raise SystemExit(f"udev rules are missing passthrough paths: {', '.join(missing_rules)}")

pocket_fit = (devices / "03-ayaneo-standard-controller.yaml").read_text(encoding="utf-8")
required_pocket_fit_entries = {
    "unlimited composite sources": "maximum_sources: 0",
    "AYANEO/DInput gamepad": "name: AYANEO Controller",
    "Pocket FIT DirectInput map": "capability_map_id: pocket_fit_dinput",
    "AYANEO/DInput vendor ID": "vendor_id: 4001",
    "AYANEO/DInput product ID": "product_id: 0428",
    "AYANEO/DInput haptics vendor ID": "vendor_id: 0x4001",
    "AYANEO/DInput haptics product ID": "product_id: 0x0428",
    "AYANEO/DInput haptics interface": "interface_num: 0",
    "AYANEO auxiliary device": "name: AYANEO DEVICE",
    "AYANEO type 9 map": "capability_map_id: aya9",
    "Steam Deck target": "- deck-uhid",
}
missing_pocket_fit_entries = [
    label for label, entry in required_pocket_fit_entries.items() if entry not in pocket_fit
]
if missing_pocket_fit_entries:
    raise SystemExit(
        "Pocket FIT profile is missing: " + ", ".join(missing_pocket_fit_entries)
    )
if "capability_map_id: ayaneo_mcu_xbox_standard" in pocket_fit:
    raise SystemExit("Pocket FIT profile still applies the gamepad map to the auxiliary device")


def require_button_mapping(text, source, target, label):
    pattern = rf"event_code:\s*{re.escape(source)}\b.*?button:\s*{re.escape(target)}\b"
    if not re.search(pattern, text, re.DOTALL):
        raise SystemExit(f"{label} is missing mapping {source} -> {target}")


pocket_fit_dinput_path = capability_maps / "pocket_fit_dinput.yaml"
if not pocket_fit_dinput_path.exists():
    raise SystemExit("Pocket FIT profile references missing main gamepad capability map")
pocket_fit_dinput = pocket_fit_dinput_path.read_text(encoding="utf-8")
for source, target in {
    "BTN_MODE": "Guide",
    "BTN_SOUTH": "South",
    "BTN_EAST": "East",
    "BTN_WEST": "West",
    "BTN_NORTH": "North",
    "BTN_START": "Start",
    "BTN_SELECT": "Select",
    "BTN_TL": "LeftBumper",
    "BTN_TR": "RightBumper",
    "BTN_Z": "LeftPaddle2",
    "BTN_C": "RightPaddle2",
}.items():
    require_button_mapping(pocket_fit_dinput, source, target, "Pocket FIT main gamepad map")

ayaneo_type9_path = capability_maps / "ayaneo_type9.yaml"
if not ayaneo_type9_path.exists():
    raise SystemExit("Pocket FIT profile references missing AYANEO type 9 capability map")
ayaneo_type9 = ayaneo_type9_path.read_text(encoding="utf-8")
for source, target in (
    ("BTN7", "QuickAccess"),
    ("BTN6", "Guide"),
    ("BTN6", "North"),
    ("BTN5", "Screenshot"),
    ("BTN3", "LeftTop"),
    ("BTN4", "RightTop"),
):
    require_button_mapping(ayaneo_type9, source, target, "AYANEO auxiliary map")

print(
    f"controller profile test passed "
    f"({len(shipped_names)} profiles, {len(passthrough_paths)} passthrough paths)"
)
PY
