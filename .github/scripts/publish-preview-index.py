#!/usr/bin/env python3

import datetime
import json
import os
import re
import subprocess
from pathlib import Path


IMAGE_KEY = re.compile(r"preview/armada-\d{8}(?:\.[0-9a-f]{7,40})?\.img\.gz")
KEEP_IMAGES = 5


def expired_keys(objects, current_key):
    if not IMAGE_KEY.fullmatch(current_key):
        raise ValueError("Current image is not a Preview disk image under preview/")

    images = []
    keys = {obj["Key"] for obj in objects}
    nonempty_keys = {obj["Key"] for obj in objects if obj["Size"] > 0}
    for obj in objects:
        if IMAGE_KEY.fullmatch(obj["Key"]):
            modified = datetime.datetime.fromisoformat(obj["LastModified"].replace("Z", "+00:00"))
            images.append((modified, obj["Key"]))
    if current_key not in nonempty_keys or current_key + ".sha256" not in nonempty_keys:
        raise ValueError("Current image and checksum must exist before pruning")

    images.sort(reverse=True)
    retained = {current_key}
    for _, key in images:
        if key not in nonempty_keys or key + ".sha256" not in nonempty_keys:
            continue
        if len(retained) < KEEP_IMAGES:
            retained.add(key)

    expired = []
    for _, key in images:
        if key not in retained:
            if key + ".sha256" in keys:
                expired.append(key + ".sha256")
            expired.append(key)
    return expired


def main():
    if os.environ.get("R2_PREFIX", "preview").strip("/") != "preview":
        raise ValueError("Preview pruning is restricted to preview/")
    endpoint = os.environ["R2_ENDPOINT_URL"]
    bucket = os.environ["R2_BUCKET"]
    current = json.loads(Path("output/current-build.json").read_text())
    current_key = current["image"]["key"]
    aws = ["aws", "--endpoint-url", endpoint, "s3api"]
    listing = subprocess.check_output(
        aws + ["list-objects-v2", "--bucket", bucket, "--prefix", "preview/", "--output", "json"],
        text=True,
    )
    objects = json.loads(listing).get("Contents", [])
    managed_keys = set()
    for obj in objects:
        key = obj["Key"]
        if not IMAGE_KEY.fullmatch(key):
            continue
        details = json.loads(subprocess.check_output(
            aws + ["head-object", "--bucket", bucket, "--key", key, "--output", "json"],
            text=True,
        ))
        if details.get("Metadata", {}).get("armada-preview") == "true":
            managed_keys.update((key, key + ".sha256"))
    managed_objects = [obj for obj in objects if obj["Key"] in managed_keys]
    expired = expired_keys(managed_objects, current_key)

    def read_object(key):
        return subprocess.check_output(
            ["aws", "s3", "cp", f"s3://{bucket}/{key}", "-",
             "--endpoint-url", endpoint, "--only-show-errors"], text=True,
        )

    keys = {obj["Key"] for obj in objects}
    previous = []
    if "preview/builds.json" in keys:
        previous = json.loads(read_object("preview/builds.json"))["builds"]
    known = {build["image"]["key"]: build for build in previous}
    builds = [current]
    for obj in sorted(managed_objects, key=lambda obj: obj["LastModified"], reverse=True):
        key = obj["Key"]
        if key not in known or key == current_key or key in expired:
            continue
        sha256 = read_object(key + ".sha256").split()[0]
        if not re.fullmatch(r"[a-f0-9]{64}", sha256):
            raise ValueError(f"Invalid checksum for {key}")
        build = dict(known[key])
        if build["image"]["sha256"] != sha256:
            build["published_at"] = obj["LastModified"]
        build["published_at"] = build["published_at"].replace("+00:00", "Z")
        build["image"] = {**build["image"], "size": obj["Size"], "sha256": sha256}
        builds.append(build)
    index = {"channel": "preview", "latest": current["version"], "builds": builds}
    Path("output/builds.json").write_text(json.dumps(index, indent=2) + "\n")
    for key in expired:
        subprocess.run(aws + ["delete-object", "--bucket", bucket, "--key", key], check=True)
        print(f"Deleted s3://{bucket}/{key}")

    subprocess.run(
        ["aws", "s3", "cp", "output/builds.json", f"s3://{bucket}/preview/builds.json",
         "--endpoint-url", endpoint, "--content-type", "application/json",
         "--cache-control", "no-store", "--only-show-errors"], check=True,
    )

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as output:
            output.write(f"\nPreview retention: keep {KEEP_IMAGES} images; deleted {len(expired)} older objects.\n")


if __name__ == "__main__":
    main()
