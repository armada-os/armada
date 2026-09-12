#!/usr/bin/env python3

import argparse
import json
import pathlib
import re
import stat
import sys
import tarfile


MANIFEST_NAME = "steam_client_steamdeck_publicbeta_linuxarm64.installed"
STEAM_PREFIX = "var/home/armada/.local/share/Steam"


def parse_manifest(contents):
    entries = []
    for line in contents.splitlines():
        if re.fullmatch(r"(?:OSVER=-?\d+|VERSION=\d+|SHA1=[0-9A-Fa-f]{40})", line):
            continue
        match = re.fullmatch(r"(.+),(-?\d+);\d+;\d+", line)
        if match:
            entries.append((match.group(1), int(match.group(2))))
    if not entries:
        raise SystemExit("Steam manifest contains no entries")
    return entries


def report_failures(missing, mismatched, not_directories, not_symlinks):
    if not (missing or mismatched or not_directories or not_symlinks):
        return
    for item in missing[:20]:
        print(f"missing: {item}", file=sys.stderr)
    for item in mismatched[:20]:
        print(f"size mismatch: {item}", file=sys.stderr)
    for item in not_directories[:20]:
        print(f"not a directory: {item}", file=sys.stderr)
    for item in not_symlinks[:20]:
        print(f"not a symlink: {item}", file=sys.stderr)
    print(
        f"Steam manifest check failed: {len(missing)} missing, "
        f"{len(mismatched)} size mismatches, "
        f"{len(not_directories)} invalid directories, "
        f"{len(not_symlinks)} invalid symlinks",
        file=sys.stderr,
    )
    raise SystemExit(1)


def verify_filesystem(manifest, steam):
    missing = []
    mismatched = []
    not_directories = []
    not_symlinks = []
    entries = parse_manifest(manifest.read_text(errors="ignore"))

    for relative_name, expected in entries:
        if expected < -2:
            continue
        relative = pathlib.Path(relative_name)
        path = steam / relative
        try:
            path_stat = path.lstat() if expected < 0 else path.stat()
        except OSError as error:
            missing.append(f"{relative}: {error.strerror}")
            continue
        if expected == -1 and not stat.S_ISDIR(path_stat.st_mode):
            not_directories.append(str(relative))
        elif expected == -2 and not stat.S_ISLNK(path_stat.st_mode):
            not_symlinks.append(str(relative))
        elif expected >= 0 and path_stat.st_size != expected:
            mismatched.append(
                f"{relative}: expected {expected}, got {path_stat.st_size}"
            )

    report_failures(missing, mismatched, not_directories, not_symlinks)


def blob_path(layout, digest):
    algorithm, value = digest.split(":", 1)
    return layout / "blobs" / algorithm / value


def find_steam_layer(layout):
    index = json.loads((layout / "index.json").read_text())
    manifest_path = blob_path(layout, index["manifests"][0]["digest"])
    image_manifest = json.loads(manifest_path.read_text())
    if "layers" not in image_manifest:
        raise SystemExit("OCI index does not reference an image manifest")
    manifest_member_name = f"{STEAM_PREFIX}/package/{MANIFEST_NAME}"

    # The Steam component xattr keeps its manifest and content in one layer.
    for layer in image_manifest["layers"]:
        members = {}
        manifest_contents = None
        layer_path = blob_path(layout, layer["digest"])
        with tarfile.open(layer_path, "r:*") as archive:
            for member in archive:
                name = member.name.removeprefix("./").lstrip("/")
                if name == manifest_member_name:
                    manifest_file = archive.extractfile(member)
                    if manifest_file is None:
                        raise SystemExit("Steam manifest is not a regular file")
                    manifest_contents = manifest_file.read().decode(errors="ignore")
                if name == STEAM_PREFIX or name.startswith(f"{STEAM_PREFIX}/"):
                    relative = name.removeprefix(STEAM_PREFIX).lstrip("/").rstrip("/")
                    members[relative] = member
        if manifest_contents is not None:
            return manifest_contents, members

    raise SystemExit("Steam manifest not found in Chunkah output")


def verify_oci(layout):
    manifest_contents, members = find_steam_layer(layout)
    missing = []
    mismatched = []
    not_directories = []
    not_symlinks = []

    for relative, expected in parse_manifest(manifest_contents):
        if expected < -2:
            continue
        member = members.get(relative.rstrip("/"))
        if member is None:
            missing.append(relative)
        elif expected == -1 and not member.isdir():
            not_directories.append(relative)
        elif expected == -2 and not member.issym():
            not_symlinks.append(relative)
        elif expected >= 0 and (not member.isfile() or member.size != expected):
            actual = member.size if member.isfile() else "non-file"
            mismatched.append(f"{relative}: expected {expected}, got {actual}")

    report_failures(missing, mismatched, not_directories, not_symlinks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--oci", type=pathlib.Path)
    parser.add_argument("manifest", nargs="?", type=pathlib.Path)
    parser.add_argument("steam", nargs="?", type=pathlib.Path)
    args = parser.parse_args()

    if args.oci:
        if args.manifest or args.steam:
            parser.error("--oci cannot be combined with filesystem paths")
        verify_oci(args.oci)
    elif args.manifest and args.steam:
        verify_filesystem(args.manifest, args.steam)
    else:
        parser.error("provide --oci or MANIFEST STEAM")


if __name__ == "__main__":
    main()
