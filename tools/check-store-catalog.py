#!/usr/bin/env python3
"""Check Armada Store catalogs the way a Store built from this checkout reads
them: every category and entry must pass, and every category icon must be a
usable SVG. Merging publishes, so a rejected entry would vanish from every
Store. Usage: tools/check-store-catalog.py [catalog ...]"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "decky/armada-store"
os.environ["DECKY_PLUGIN_DIR"] = str(STORE)
sys.path[:0] = [str(ROOT / "decky/shared/armada-apps/py_modules"), str(STORE / "py_modules")]

import armada_store  # noqa: E402,F401  configures the engine as the Store
from armada_apps import catalog, icons  # noqa: E402


def problems(path):
    doc = catalog.parse_document(Path(path).read_bytes())
    found, shown = [], set()
    for category in doc["categories"]:
        problem = catalog.category_problem(category)
        if not problem and category.get("icon"):
            try:
                data = (STORE / icons.FOLDER / category["icon"]).read_bytes()
            except OSError:
                problem = "icon file missing: " + category["icon"]
            else:
                problem = icons.svg_problem(data)
        if problem:
            found.append("category {}: {}".format(category.get("id"), problem))
        else:
            shown.add(category["id"])
    for app in doc["apps"]:
        problem = catalog.entry_problem(app, shown)
        # System entries point into the image, which this checkout is not.
        if problem and not ((app.get("install") or {}).get("type") == "system"
                            and problem.startswith("not in this image")):
            found.append("app {}: {}".format(app.get("id"), problem))
    return found


def main(paths):
    failed = False
    for path in paths or sorted(str(p) for p in STORE.glob("catalog-v*.json")):
        for problem in problems(path):
            print("::error::{}: {}".format(path, problem))
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
