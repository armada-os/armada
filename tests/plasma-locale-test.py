#!/usr/bin/python3
"""Unit tests for the Steam UI language fallback helper."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

HELPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "system_files"
    / "usr"
    / "lib"
    / "armada"
    / "plasma-locale.py"
)
SPEC = importlib.util.spec_from_file_location("plasma_locale", HELPER_PATH)
plasma_locale = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plasma_locale)


def registry_text(branches):
    """Build a minimal Registry/HKCU/Software/Valve registry."""
    lines = [
        '"Registry"',
        "{",
        '\t"HKCU"',
        "\t{",
        '\t\t"Software"',
        "\t\t{",
        '\t\t\t"Valve"',
        "\t\t\t{",
    ]
    for branch, language in branches:
        lines.extend((f'\t\t\t\t"{branch}"', "\t\t\t\t{"))
        if language is not None:
            lines.append(f'\t\t\t\t\t"language"\t\t"{language}"')
        lines.append("\t\t\t\t}")
    lines.extend(("\t\t\t}", "\t\t}", "\t}", "}"))
    return "\n".join(lines) + "\n"


class SteamLanguageTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)

    def write_registry(self, text, relative=".steam/registry.vdf"):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def assert_language(self, expected):
        self.assertEqual(plasma_locale.steam_language(self.home), expected)

    def test_absent_registry_defaults_to_english(self):
        self.assert_language("en")

    def test_schinese(self):
        self.write_registry(registry_text([("Steam", "schinese")]))
        self.assert_language("zh_CN")

    def test_tchinese(self):
        self.write_registry(registry_text([("Steam", "tchinese")]))
        self.assert_language("zh_TW")

    def test_steamsteamglobal_overrides_steam(self):
        self.write_registry(
            registry_text(
                [("Steamsteamglobal", "schinese"), ("Steam", "english")]
            )
        )
        self.assert_language("zh_CN")

    def test_unknown_steamsteamglobal_falls_through_to_steam(self):
        self.write_registry(
            registry_text([("Steamsteamglobal", "klingon"), ("Steam", "german")])
        )
        self.assert_language("de")

    def test_case_insensitive_nodes(self):
        self.write_registry(
            "\n".join(
                (
                    '"registry"',
                    "{",
                    '\t"hkcu"',
                    "\t{",
                    '\t\t"SOFTWARE"',
                    "\t\t{",
                    '\t\t\t"valve"',
                    "\t\t\t{",
                    '\t\t\t\t"steam"',
                    "\t\t\t\t{",
                    '\t\t\t\t\t"LANGUAGE"\t\t"japanese"',
                    "\t\t\t\t}",
                    "\t\t\t}",
                    "\t\t}",
                    "\t}",
                    "}",
                    "",
                )
            )
        )
        self.assert_language("ja")

    def test_malformed_registry_defaults_to_english(self):
        self.write_registry("not a registry\n")
        self.assert_language("en")

    def test_broken_file_falls_through_to_next_path(self):
        self.write_registry("not a registry\n")
        self.write_registry(
            registry_text([("Steam", "german")]), ".steam/root/registry.vdf"
        )
        self.assert_language("de")

    def test_game_language_is_ignored(self):
        self.write_registry(
            "\n".join(
                (
                    '"Registry"',
                    "{",
                    '\t"HKCU"',
                    "\t{",
                    '\t\t"Software"',
                    "\t\t{",
                    '\t\t\t"Valve"',
                    "\t\t\t{",
                    '\t\t\t\t"Steam"',
                    "\t\t\t\t{",
                    '\t\t\t\t\t"apps"',
                    "\t\t\t\t\t{",
                    '\t\t\t\t\t\t"570"',
                    "\t\t\t\t\t\t{",
                    '\t\t\t\t\t\t\t"language"\t\t"schinese"',
                    "\t\t\t\t\t\t}",
                    "\t\t\t\t\t}",
                    "\t\t\t\t}",
                    "\t\t\t}",
                    "\t\t}",
                    "\t}",
                    "}",
                    "",
                )
            )
        )
        self.assert_language("en")

    def test_non_string_language_is_ignored(self):
        self.write_registry(
            "\n".join(
                (
                    '"Registry"',
                    "{",
                    '\t"HKCU"',
                    "\t{",
                    '\t\t"Software"',
                    "\t\t{",
                    '\t\t\t"Valve"',
                    "\t\t\t{",
                    '\t\t\t\t"Steam"',
                    "\t\t\t\t{",
                    '\t\t\t\t\t"language"',
                    "\t\t\t\t\t{",
                    '\t\t\t\t\t\t"nested"\t\t"schinese"',
                    "\t\t\t\t\t}",
                    "\t\t\t\t}",
                    "\t\t\t}",
                    "\t\t}",
                    "\t}",
                    "}",
                    "",
                )
            )
        )
        self.assert_language("en")

    def test_unknown_language_defaults_to_english(self):
        self.write_registry(registry_text([("Steam", "klingon")]))
        self.assert_language("en")

    def test_root_relative_registry_is_used(self):
        self.write_registry(
            registry_text([("Steam", "schinese")]), ".steam/root/registry.vdf"
        )
        self.assert_language("zh_CN")

    def test_local_share_registry_is_used(self):
        self.write_registry(
            registry_text([("Steam", "tchinese")]),
            ".local/share/Steam/registry.vdf",
        )
        self.assert_language("zh_TW")

    def test_representative_non_chinese_languages(self):
        cases = (
            ("german", "de"),
            ("japanese", "ja"),
            ("brazilian", "pt_BR"),
            ("latam", "es_MX:es"),
            ("ukrainian", "uk"),
        )
        for name, code in cases:
            with self.subTest(name=name):
                self.write_registry(registry_text([("Steam", name)]))
                self.assert_language(code)


if __name__ == "__main__":
    unittest.main()
