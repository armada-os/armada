#!/usr/bin/env python3
import hashlib
import pathlib
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

MANIFEST = "steam_client_steamdeck_publicbeta_linuxarm64"
CDN = "https://client-update.steamstatic.com"


def packages(contents, version):
    match = re.search(r'"version"\s+"(\d+)"', contents)
    if match is None or match.group(1) != version:
        raise ValueError("Pinned manifest version differs from BASE.env")
    result = []
    for block in re.findall(r'\{([^{}]*)\}', contents):
        fields = dict(re.findall(r'"([^"\n]+)"\s+"([^"\n]+)"', block))
        if "file" not in fields:
            continue
        for name_key, hash_key in (("file", "sha2"), ("zipvz", "sha2vz")):
            if name_key not in fields:
                continue
            name, digest = fields[name_key], fields.get(hash_key, "")
            if not re.fullmatch(r'[a-zA-Z0-9_.-]+', name) or not re.fullmatch(r'[a-f0-9]{64}', digest):
                raise ValueError(f"Invalid package name or SHA256: {name}")
            result.append((name, digest))
    if not result:
        raise ValueError("Pinned manifest contains no packages")
    return result


def download(url, path, expected):
    if path.is_file():
        with path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() == expected:
                return
    temporary = path.with_name(path.name + ".partial")
    subprocess.run(["curl", "--retry", "5", "-fLsS", "-o", str(temporary), url], check=True)
    with temporary.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != expected:
            raise ValueError(f"SHA256 mismatch: {path.name}")
    temporary.replace(path)
    print(f"Verified {path.name}", flush=True)


def prepare_manifest(version, feed):
    override = pathlib.Path("manifests") / version
    manifest = feed / MANIFEST
    if override.is_file():
        shutil.copyfile(override, manifest)
    else:
        subprocess.run(["curl", "--retry", "5", "-fLsS", "-o", str(manifest), f"{CDN}/{MANIFEST}"], check=True)
    return packages(manifest.read_text(), version)


def main():
    version, runtime, runtime_sha256 = sys.argv[1:]
    feed = pathlib.Path("work/feed")
    feed.mkdir(parents=True, exist_ok=True)
    archives = prepare_manifest(version, feed)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda item: download(f"{CDN}/{item[0]}", feed / item[0], item[1]), archives))
    download(
        f"https://repo.steampowered.com/steamrt3c/images/{runtime}/steam-runtime-steamrt-arm64.tar.xz",
        pathlib.Path("work/runtime.tar.xz"), runtime_sha256,
    )


if __name__ == "__main__":
    main()
