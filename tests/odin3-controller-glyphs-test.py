#!/usr/bin/env python3
"""Regression policy for the Odin 3-only Armada Control glyph integration."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "decky/themes/handheld-controller-glyphs"
ASSET_ROOT = THEME / "assets"
ODIN_ASSETS = ASSET_ROOT / "ayn/odin-3"
THEMES_ROOT = THEME / "themes"
CONTROL = ROOT / "decky/armada-control"
DEVICES = ROOT / "system_files/usr/lib/armada/devices"

EXPECTED_ASSETS = {
    "a-color.png",
    "a.png",
    "b-color.png",
    "b.png",
    "back.png",
    "controller-left.png",
    "controller-right.png",
    "controller.png",
    "dpad-down.png",
    "dpad-left.png",
    "dpad-right.png",
    "dpad-up.png",
    "dpad.png",
    "home.png",
    "l1.png",
    "l2-soft.png",
    "l2.png",
    "lstick-click.png",
    "lstick-down.png",
    "lstick-left.png",
    "lstick-right.png",
    "lstick-touch.png",
    "lstick-up.png",
    "lstick.png",
    "m1.png",
    "m2.png",
    "r1.png",
    "r2-soft.png",
    "r2.png",
    "rstick-click.png",
    "rstick-down.png",
    "rstick-left.png",
    "rstick-right.png",
    "rstick-touch.png",
    "rstick-up.png",
    "rstick.png",
    "select.png",
    "start.png",
    "x-color.png",
    "x.png",
    "y-color.png",
    "y.png",
}
EXPECTED_STYLESHEETS = {
    "themes/armada/ayn-retroid-buttons.css",
    "themes/ayn/odin-3-colored-face-buttons.css",
    "themes/ayn/odin-3.css",
}
THEME_PREFIX = "/themes_custom/handheld-controller-glyphs/"
URL_RE = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""")


def relative_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def parse_assignments(path: Path) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        assignments[key] = value.strip().strip("'\"")
    return assignments


def validate_png(path: Path) -> None:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError(f"{path.name}: invalid PNG signature")

    offset = 8
    chunks: list[bytes] = []
    while offset < len(data):
        if offset + 12 > len(data):
            raise AssertionError(f"{path.name}: truncated PNG chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise AssertionError(f"{path.name}: chunk extends past EOF")
        payload = data[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", data[offset + 8 + length : end])[0]
        actual_crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise AssertionError(f"{path.name}: bad {kind!r} CRC")
        chunks.append(kind)
        offset = end
        if kind == b"IEND":
            break

    if chunks[:1] != [b"IHDR"] or chunks[-1:] != [b"IEND"]:
        raise AssertionError(f"{path.name}: missing IHDR or IEND")
    if offset != len(data):
        raise AssertionError(f"{path.name}: trailing data after IEND")


class Odin3ControllerGlyphPolicyTests(unittest.TestCase):
    def test_exact_odin_asset_scope_and_png_validity(self) -> None:
        self.assertEqual(relative_files(ODIN_ASSETS), EXPECTED_ASSETS)
        self.assertEqual(
            {
                path.relative_to(ASSET_ROOT).as_posix()
                for path in ASSET_ROOT.rglob("*")
                if path.is_file()
            },
            {f"ayn/odin-3/{name}" for name in EXPECTED_ASSETS},
        )
        for name in sorted(EXPECTED_ASSETS):
            with self.subTest(asset=name):
                validate_png(ODIN_ASSETS / name)

    def test_css_scope_and_references_are_exact(self) -> None:
        self.assertEqual(
            relative_files(THEMES_ROOT),
            {path.removeprefix("themes/") for path in EXPECTED_STYLESHEETS},
        )
        referenced_assets: set[str] = set()
        for stylesheet in sorted(EXPECTED_STYLESHEETS):
            text = (THEME / stylesheet).read_text(encoding="utf-8")
            for _quote, url in URL_RE.findall(text):
                self.assertTrue(
                    url.startswith(THEME_PREFIX + "assets/ayn/odin-3/"),
                    f"{stylesheet} references non-Odin asset {url}",
                )
                relative = url.removeprefix(THEME_PREFIX)
                target = THEME / relative
                self.assertTrue(target.is_file(), f"missing CSS asset: {relative}")
                referenced_assets.add(target.name)
        self.assertEqual(referenced_assets, EXPECTED_ASSETS)

    def test_build_routing_emits_only_the_odin_theme(self) -> None:
        package = json.loads((CONTROL / "package.json").read_text(encoding="utf-8"))
        self.assertIn(
            "node tools/build-controller-glyph-theme.mjs",
            package["scripts"]["build"],
        )
        containerfile = (ROOT / "Containerfile").read_text(encoding="utf-8")
        self.assertIn(
            "COPY decky/themes/handheld-controller-glyphs/ "
            "/themes/handheld-controller-glyphs/",
            containerfile,
        )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "controller-theme"
            env = dict(os.environ)
            env["ARMADA_CONTROLLER_THEME_SOURCE"] = str(THEME)
            env["ARMADA_CONTROLLER_THEME_OUTPUT"] = str(output)
            subprocess.run(
                ["node", "tools/build-controller-glyph-theme.mjs"],
                cwd=CONTROL,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            expected = {
                "LICENSE",
                *EXPECTED_STYLESHEETS,
                *(f"assets/ayn/odin-3/{name}" for name in EXPECTED_ASSETS),
            }
            self.assertEqual(relative_files(output), expected)
            for stylesheet in EXPECTED_STYLESHEETS:
                built = (output / stylesheet).read_text(encoding="utf-8")
                self.assertNotIn(THEME_PREFIX, built)
                for _quote, url in URL_RE.findall(built):
                    self.assertTrue((output / stylesheet).parent.joinpath(url).resolve().is_file())

    def test_ayn_odin_3_is_the_only_device_mapping(self) -> None:
        mappings = {
            path.name: parse_assignments(path).get(
                "ARMADA_CONTROLLER_GLYPH_VARIANT", ""
            )
            for path in DEVICES.glob("*.conf")
        }
        self.assertEqual(
            {name: value for name, value in mappings.items() if value},
            {"ayn-odin-3.conf": "AYN Odin 3"},
        )
        self.assertEqual(mappings["defaults.conf"], "")

        source = (CONTROL / "src/lib/controllerGlyphs.ts").read_text(encoding="utf-8")
        self.assertIn('"AYN Odin 3": [', source)
        self.assertIn('return value === "AYN Odin 3";', source)
        self.assertNotIn("CSSLoader", source)
        self.assertNotIn("css-loader", source.lower())

    def test_monochrome_default_and_rainbow_persistence(self) -> None:
        contract = json.loads(
            (ROOT / "system_files/usr/share/armada/fex-profiles.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            contract["defaults"]["global"]["controllerGlyphStyle"],
            "monochrome",
        )

        sys.path.insert(0, str(CONTROL / "py_modules"))
        try:
            tweaks = importlib.import_module("armada_control.tweaks")
            self.assertEqual(
                tweaks.sanitize_tweaks({})["global"]["controllerGlyphStyle"],
                "monochrome",
            )
            self.assertEqual(
                tweaks.sanitize_tweaks(
                    {"global": {"controllerGlyphStyle": "rainbow"}}
                )["global"]["controllerGlyphStyle"],
                "rainbow",
            )
            self.assertEqual(
                tweaks.sanitize_tweaks(
                    {"global": {"controllerGlyphStyle": "unsupported"}}
                )["global"]["controllerGlyphStyle"],
                "monochrome",
            )
        finally:
            sys.path.remove(str(CONTROL / "py_modules"))

        frontend = (CONTROL / "src/lib/controllerGlyphs.ts").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            frontend,
            r'trim\(\)\.toLowerCase\(\) === "rainbow"\s*\?\s*"Rainbow"\s*:\s*"Monochrome"',
        )
        content = (CONTROL / "src/Content.tsx").read_text(encoding="utf-8")
        self.assertIn('field: "tweaks"', content)
        self.assertIn("save: saveTweaks", content)

    def test_no_other_device_profile_or_css_loader_additions(self) -> None:
        changed = subprocess.run(
            ["git", "diff", "--name-only", "HEAD^", "HEAD", "--"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        device_changes = {
            Path(name).as_posix()
            for name in changed
            if name.startswith("system_files/usr/lib/armada/devices/")
        }
        self.assertEqual(
            device_changes,
            {
                "system_files/usr/lib/armada/devices/ayn-odin-3.conf",
                "system_files/usr/lib/armada/devices/defaults.conf",
            },
        )

        runtime_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                CONTROL / "package.json",
                CONTROL / "src/lib/controllerGlyphs.ts",
                ROOT / "build_files/45-install-decky-plugins.sh",
                ROOT / "system_files/usr/lib/decky-loader/armada-decky-sync",
            )
        ).lower()
        self.assertNotIn("cssloader", runtime_text)
        self.assertNotIn("css loader", runtime_text)
        self.assertNotIn("themes_custom", runtime_text)


if __name__ == "__main__":
    unittest.main()
