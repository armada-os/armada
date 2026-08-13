#!/usr/bin/env python3
import pathlib
import re
import sys


PROBE_PATTERN = re.compile(
    r"^([ \t]*MODERN_DXVK_FEATURES[ \t]*=[ \t]*)"
    r"\[[ \t]*(['\"])descriptorIndexing\2[ \t]*\]([ \t]*(?:#.*)?)$",
    re.MULTILINE,
)


def patch_probe(path):
    text = path.read_text(encoding="utf-8")
    matches = list(PROBE_PATTERN.finditer(text))
    if len(matches) != 1:
        raise SystemExit(
            f"ERROR: expected one descriptorIndexing-only DXVK feature probe in {path}, "
            f"found {len(matches)}"
        )

    match = matches[0]
    replacement = (
        f"{match.group(1)}['descriptorIndexing', 'storageBuffer8BitAccess']"
        f"{match.group(3)}"
    )
    path.write_text(
        text[:match.start()] + replacement + text[match.end():],
        encoding="utf-8",
    )


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch-proton-cachyos-dxvk-probe.py PROTON_SCRIPT")

    patch_probe(pathlib.Path(sys.argv[1]))


if __name__ == "__main__":
    main()
