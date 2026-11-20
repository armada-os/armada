#!/usr/bin/env python3
"""Unpacks a pinned client manifest's packages into a Steam root.

Valve's tarball is built the same way: every package unzipped in manifest order
and package/beta written, with no client run. Writes <steam>/.bootstrap-manifest,
the expected tree (size and CRC32, in Steam's .installed format), for
steam-verify, the build and CI.
"""
import pathlib
import shutil
import stat
import subprocess
import sys
import zipfile

import fetch

MANIFEST_NAME = ".bootstrap-manifest"


def extract(package, steam):
    """Extracts like Steam's updater: `\\` is a path separator, files are 0755."""
    root = steam.resolve()
    entries = {}
    for info in package.infolist():
        name = info.filename.replace("\\", "/").rstrip("/")
        target = steam / name
        if not target.resolve().is_relative_to(root):
            raise SystemExit(f"Package entry escapes the Steam root: {info.filename}")
        mode = info.external_attr >> 16
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            entries[name] = (-1, 0)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.unlink(missing_ok=True)
        if stat.S_ISLNK(mode):
            target.symlink_to(package.read(info).decode().replace("\\", "/"))
            entries[name] = (-2, 0)
        else:
            with package.open(info) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            target.chmod(0o755)
            entries[name] = (info.file_size, info.CRC)
    return entries


def main():
    feed, channel, version, steam = sys.argv[1:]
    feed, steam = pathlib.Path(feed), pathlib.Path(steam)
    archives = fetch.packages((feed / f"steam_client_{channel}_linuxarm64").read_text(), version)

    (steam / "package").mkdir(parents=True)
    (steam / "package/beta").write_text(channel + "\n")

    expected = {}
    for name, _ in archives:
        with zipfile.ZipFile(feed / name) as package:
            expected.update(extract(package, steam))

    versions = steam / "steamrt64/pv-runtime/steam-runtime-steamrt/VERSIONS.txt"
    if "steamrt3c" not in versions.read_text():
        raise SystemExit("Steam bootstrap does not carry the steamrt3c runtime")

    manifest = steam / MANIFEST_NAME
    manifest.write_text("".join(f"{path},{size};0;{crc}\n" for path, (size, crc) in sorted(expected.items())))
    subprocess.run([sys.executable, str(pathlib.Path(__file__).parent / "system/usr/lib/steam/steam-verify"),
                    "--crc", str(steam)], check=True)

    # Steam opens Decky's localhost CEF debugger only when this marker exists.
    (steam / ".cef-enable-remote-debugging").touch()
    print(f"Unpacked {len(archives)} packages, {len(expected)} entries")


if __name__ == "__main__":
    main()
