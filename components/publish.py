#!/usr/bin/env python3
"""Publish remote components into a local tree laid out like downloads.armadaos.dev/components.

  publish.py add --out DIR --key KEY --channel testing --name turnip --version V
                 --payload PAYLOAD_DIR [--min-os-api N]
  publish.py promote --out DIR --key KEY --from testing --to beta --name turnip

--min-os-api defaults to the OS_API of the tree the payload was built from, so a build
never lands on an image older than the interfaces it was built against.

Blobs are content-addressed (<name>/<sha256>.tar.zst) and never rewritten. Every manifest
write is re-signed with `ssh-keygen -Y sign -n armada-components`. Upload DIR as is.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

NAMESPACE = "armada-components"
CHANNELS = ("testing", "beta", "stable")
UPDATER = Path(__file__).resolve().parents[1] / "system_files/usr/libexec/armada/armada-components"


def tree_os_api():
    return int(re.search(r"^OS_API = (\d+)$", UPDATER.read_text(), re.M).group(1))


def pack(payload, out_dir, name):
    blobs = out_dir / name
    blobs.mkdir(parents=True, exist_ok=True)
    tmp = blobs / ".pack.tar.zst"

    def owned_by_root(info):
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mtime = 0
        return info

    with tmp.open("wb") as out:
        zstd = subprocess.Popen(["zstd", "-19", "-q", "-T0"], stdin=subprocess.PIPE, stdout=out)
        with tarfile.open(fileobj=zstd.stdin, mode="w|", format=tarfile.PAX_FORMAT) as tar:
            for path in sorted(payload.rglob("*")):
                tar.add(path, path.relative_to(payload).as_posix(), recursive=False, filter=owned_by_root)
        zstd.stdin.close()
        if zstd.wait():
            sys.exit("zstd failed")
    data = tmp.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    tmp.rename(blobs / f"{sha}.tar.zst")
    return {"sha256": sha, "size": len(data)}


def load(out_dir, channel):
    path = out_dir / f"{channel}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"schema": 1, "channel": channel, "components": {}}


def save(out_dir, channel, manifest, key):
    path = out_dir / f"{channel}.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    Path(f"{path}.sig").unlink(missing_ok=True)
    subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", key, "-n", NAMESPACE, str(path)], check=True)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("--channel", choices=CHANNELS, required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--version", required=True)
    add.add_argument("--payload", type=Path, required=True)
    add.add_argument("--min-os-api", type=int, default=tree_os_api())
    promote = sub.add_parser("promote")
    promote.add_argument("--from", dest="source", choices=CHANNELS, required=True)
    promote.add_argument("--to", choices=CHANNELS, required=True)
    promote.add_argument("--name", required=True)
    for p in (add, promote):
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--key", required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    if args.command == "add":
        if not args.payload.is_dir():
            sys.exit(f"{args.payload} is not a directory")
        entry = {"version": args.version, "min_os_api": args.min_os_api, **pack(args.payload, args.out, args.name)}
        channel = args.channel
    else:
        entry = load(args.out, args.source)["components"].get(args.name)
        if not entry:
            sys.exit(f"{args.name} is not in {args.source}")
        channel = args.to
    manifest = load(args.out, channel)
    old = manifest["components"].get(args.name)
    # same bytes: keep the entry, so devices see no change
    if old and old["sha256"] == entry["sha256"] and old["min_os_api"] == entry["min_os_api"]:
        print(f"{channel}: {args.name} unchanged at {old['version']}")
        return
    manifest["components"][args.name] = entry
    save(args.out, channel, manifest, args.key)
    print(f"{channel}: {args.name} {entry['version']} ({entry['sha256'][:12]})")


if __name__ == "__main__":
    main()
