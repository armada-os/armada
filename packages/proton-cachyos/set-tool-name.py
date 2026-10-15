#!/usr/bin/env python3
import pathlib
import re
import sys


def set_display_name(compatibilitytool_path):
    text = compatibilitytool_path.read_text()
    text, count = re.subn(
        r'("display_name"\s+)"[^"]+"',
        r'\1"Proton 11.0 CachyOS (ARM64)"',
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit("missing display_name entry")
    compatibilitytool_path.write_text(text)


def set_compat_tool_name(compatibilitytool_path, tool_name):
    text = compatibilitytool_path.read_text()

    text, count = re.subn(
        r'("compat_tools"\s*\{\s*)"[^"]+"',
        lambda match: f'{match.group(1)}"{tool_name}"',
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit("missing compat_tools entry")
    compatibilitytool_path.write_text(text)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: set-steam-default-compat.py TOOL_NAME COMPAT_DIR")

    tool_name = sys.argv[1]
    tool_dir = pathlib.Path(sys.argv[2]) / tool_name

    compatibilitytool_path = tool_dir / "compatibilitytool.vdf"
    set_compat_tool_name(compatibilitytool_path, tool_name)
    set_display_name(compatibilitytool_path)


if __name__ == "__main__":
    main()
