#!/usr/bin/python3
"""Print the gettext/KDE LANGUAGE code matching Steam's UI language."""

import sys
from pathlib import Path

import vdf

# Steam's official UI language names, mapped to gettext language codes.
STEAM_UI_LANGUAGES = {
    "english": "en",
    "german": "de",
    "french": "fr",
    "italian": "it",
    "koreana": "ko",
    "spanish": "es",
    "schinese": "zh_CN",
    "tchinese": "zh_TW",
    "russian": "ru",
    "thai": "th",
    "japanese": "ja",
    "portuguese": "pt",
    "polish": "pl",
    "danish": "da",
    "dutch": "nl",
    "finnish": "fi",
    "norwegian": "nb",
    "swedish": "sv",
    "hungarian": "hu",
    "czech": "cs",
    "romanian": "ro",
    "turkish": "tr",
    "brazilian": "pt_BR",
    "bulgarian": "bg",
    "greek": "el",
    "ukrainian": "uk",
    "latam": "es_MX:es",
    "vietnamese": "vi",
    "indonesian": "id",
    "malay": "ms",
}

REGISTRY_PATHS = (
    Path(".steam", "registry.vdf"),
    Path(".steam", "root", "registry.vdf"),
    Path(".local", "share", "Steam", "registry.vdf"),
)

STEAM_BRANCHES = ("Steamsteamglobal", "Steam")


def _child(node, name):
    """Return a case-insensitive child of a VDF mapping, if any."""
    if not isinstance(node, dict):
        return None
    wanted = name.casefold()
    for key, value in node.items():
        if isinstance(key, str) and key.casefold() == wanted:
            return value
    return None


def _registry_language(tree):
    """Return a mapped language from the exact Steam UI registry path."""
    node = tree
    for name in ("Registry", "HKCU", "Software", "Valve"):
        node = _child(node, name)
        if not isinstance(node, dict):
            return None

    # The client stores the UI language under Steamsteamglobal; older layouts
    # only have Steam. Never search app or game scopes.
    for branch in STEAM_BRANCHES:
        value = _child(_child(node, branch), "language")
        if isinstance(value, str):
            code = STEAM_UI_LANGUAGES.get(value.strip().casefold())
            if code:
                return code
    return None


def _read_registry(path):
    try:
        with path.open("r", encoding="utf-8") as stream:
            return vdf.load(stream)
    except (OSError, UnicodeError, ValueError, SyntaxError):
        return None


def steam_language(home: Path) -> str:
    """Resolve the Steam UI language for *home*, falling back to English."""
    home = Path(home)
    for relative in REGISTRY_PATHS:
        tree = _read_registry(home / relative)
        if tree is None:
            continue
        code = _registry_language(tree)
        if code:
            return code
    return "en"


def main():
    print(steam_language(Path.home()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
