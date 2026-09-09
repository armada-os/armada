#!/usr/bin/env python3

import datetime
import json
import os
import re
import subprocess


IMAGE_KEY = re.compile(r"preview/armada-\d{8}(?:\.[0-9a-f]{7,40})?\.img\.gz")
KEEP_IMAGES = 5


def expired_keys(objects, current_key):
    if not IMAGE_KEY.fullmatch(current_key):
        raise ValueError("Current image is not a Preview disk image under preview/")

    images = []
    keys = {obj["Key"] for obj in objects}
    for obj in objects:
        if IMAGE_KEY.fullmatch(obj["Key"]):
            modified = datetime.datetime.fromisoformat(obj["LastModified"].replace("Z", "+00:00"))
            images.append((modified, obj["Key"]))
    if current_key not in keys or current_key + ".sha256" not in keys:
        raise ValueError("Current image and checksum must exist before pruning")

    images.sort(reverse=True)
    retained = {current_key}
    for _, key in images:
        if key + ".sha256" not in keys:
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
    current_key = os.environ["CURRENT_IMAGE_KEY"]
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
    for key in expired:
        subprocess.run(aws + ["delete-object", "--bucket", bucket, "--key", key], check=True)
        print(f"Deleted s3://{bucket}/{key}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as output:
            output.write(f"\nPreview retention: keep {KEEP_IMAGES} images; deleted {len(expired)} older objects.\n")


if __name__ == "__main__":
    main()
