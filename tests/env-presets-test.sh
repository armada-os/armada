#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 -B - "$ROOT" "$WORK" <<'PYEOF'
import json
import os
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
work = pathlib.Path(sys.argv[2])

LOCALES = ("en", "pt-BR", "pt-PT", "zh-CN")
factory_path = root / "system_files/usr/share/armada/env-presets.json"
factory = json.loads(factory_path.read_text(encoding="utf-8"))["presets"]

# The modal rejects names that are empty or carry '=' or NUL, so a preset that
# broke those rules would be unsaveable from the picker it ships in.
names = [preset["name"] for preset in factory]
assert len(set(names)) == len(names), "duplicate preset name"
for name in names:
    assert re.fullmatch(r"[A-Z][A-Z0-9_]*", name), name

# The modal picks its value widget from exactly one of these fields. Both on one
# preset means the widget chosen silently ignores the other.
for preset in factory:
    shapes = [field for field in ("options", "example") if field in preset]
    assert len(shapes) == 1, f"{preset['name']} declares {len(shapes)} value shapes"

# The picker exists so a name like VKD3D_SHADER_MODEL explains itself. A locale
# missing here falls back to English, which reads as an untranslated panel.
for preset in factory:
    description = preset["description"]
    assert isinstance(description, dict), f"{preset['name']} description is not translated"
    assert sorted(description) == sorted(LOCALES), f"{preset['name']} description misses a locale"
    for locale in LOCALES:
        assert description[locale].strip(), f"{preset['name']} description is empty in {locale}"

# An empty option or label reaches the dropdown as a blank row the user cannot
# read. A label carrying words is translated; one that is only an identifier is
# a bare string on purpose.
for preset in factory:
    for option in preset.get("options", []):
        assert option["data"], f"{preset['name']} has an empty option value"
        label = option["label"]
        if isinstance(label, str):
            assert label.strip(), f"{preset['name']} has an empty option label"
            continue
        assert sorted(label) == sorted(LOCALES), f"{preset['name']} option {option['data']} misses a locale"
        for locale in LOCALES:
            assert label[locale].strip(), f"{preset['name']} option {option['data']} is empty in {locale}"

# The two switches FeralAI asked for: one dropdown, on and off, nothing to type.
for name in ("PROTON_USE_WINED3D", "PROTON_USE_WOW64"):
    preset = next(item for item in factory if item["name"] == name)
    assert [option["data"] for option in preset["options"]] == ["1", "0"], name

os.environ["ARMADA_GAME_TWEAKS_LIB"] = str(root / "system_files/usr/lib/armada")
sys.path.insert(0, str(root / "decky/armada-control/py_modules"))
from armada_control import tweaks  # noqa: E402

missing = work / "absent.json"
broken = work / "broken.json"
broken.write_text("{ not json", encoding="utf-8")
override = work / "override.json"
override.write_text(json.dumps({"presets": [{"name": "MY_OWN_VARIABLE", "description": "Mine."}]}), encoding="utf-8")

# The factory file is the one the image ships, read as published.
tweaks.ENV_PRESETS_CONFIG = factory_path
tweaks.ENV_PRESETS_OVERRIDE = missing
assert [preset["name"] for preset in tweaks.load_env_presets()] == names

# An admin adds a variable in /etc/armada without waiting for an OTA.
tweaks.ENV_PRESETS_OVERRIDE = override
assert [preset["name"] for preset in tweaks.load_env_presets()] == ["MY_OWN_VARIABLE"]

# An override that does not parse must not cost the factory list. Unlike
# power.py, nothing is moved aside: the admin keeps their file to fix.
tweaks.ENV_PRESETS_OVERRIDE = broken
assert [preset["name"] for preset in tweaks.load_env_presets()] == names
assert broken.exists()

# No file and a broken factory file both give an empty list. The picker button
# disappears; the Compatibility tab and the custom-variable button stay.
tweaks.ENV_PRESETS_CONFIG = missing
tweaks.ENV_PRESETS_OVERRIDE = missing
assert tweaks.load_env_presets() == []
tweaks.ENV_PRESETS_CONFIG = broken
assert tweaks.load_env_presets() == []

# A file that parses but is not shaped like a preset list is not a list of
# presets either. Returning its contents would crash the panel instead.
for text in ('{"presets": {}}', '[]', '"presets"'):
    broken.write_text(text, encoding="utf-8")
    assert tweaks.load_env_presets() == [], text

print("env-presets tests passed: factory data, locales, override, and the fallbacks")
PYEOF
