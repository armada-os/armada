import argparse
import pathlib
import re
import stat
import sys


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


def verify_version(manifest, expected):
    match = re.search(r'"version"\s+"(\d+)"', manifest.read_text())
    actual = match.group(1) if match else "missing"
    if actual != expected:
        raise SystemExit(f"Steam client version mismatch: expected {expected}, got {actual}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version")
    parser.add_argument("manifest", type=pathlib.Path)
    parser.add_argument("steam", type=pathlib.Path, nargs="?")
    args = parser.parse_args()
    if args.version and not args.steam:
        verify_version(args.manifest, args.version)
    elif args.steam and not args.version:
        verify_filesystem(args.manifest, args.steam)
    else:
        parser.error("provide --version VERSION MANIFEST or MANIFEST STEAM")
