#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/system_files/usr/lib/armada/update-lib"

assert_registry() {
    local expected="$1" ref="$2" actual
    actual="$(armada_registry_from_ref "$ref")"
    if [[ "$actual" != "$expected" ]]; then
        printf 'registry parse failed: expected %q, got %q for %q\n' \
            "$expected" "$actual" "$ref" >&2
        exit 1
    fi
}

assert_registry "$ARMADA_LEGACY_REGISTRY" \
    "ostree-image-signed:docker://${ARMADA_LEGACY_REGISTRY}:stable"
assert_registry "$ARMADA_CANONICAL_REGISTRY" \
    "ostree-image-signed:docker://${ARMADA_CANONICAL_REGISTRY}@sha256:deadbeef"
assert_registry "$ARMADA_CANONICAL_REGISTRY" \
    "docker://${ARMADA_CANONICAL_REGISTRY}:testing"
assert_registry "$ARMADA_CANONICAL_REGISTRY" \
    "ostree-unverified-registry:${ARMADA_CANONICAL_REGISTRY}:testing"
assert_registry "" \
    "ostree-image-signed:docker://example.invalid/${ARMADA_LEGACY_REGISTRY}:stable"

assert_repository() {
    local expected="$1" ref="$2" actual
    actual="$(armada_repository_from_ref "$ref" || true)"
    if [[ "$actual" != "$expected" ]]; then
        printf 'repository parse failed: expected %q, got %q for %q\n' \
            "$expected" "$actual" "$ref" >&2
        exit 1
    fi
}

assert_repository "local.armadaos.dev/armada" \
    "ostree-unverified-registry:docker://local.armadaos.dev/armada:feature-a"
assert_repository "$ARMADA_CANONICAL_REGISTRY" \
    "ostree-unverified-registry:${ARMADA_CANONICAL_REGISTRY}:testing"
assert_repository "example.invalid/${ARMADA_LEGACY_REGISTRY}" \
    "ostree-image-signed:docker://example.invalid/${ARMADA_LEGACY_REGISTRY}:stable"
assert_repository "" "containers-storage:localhost/armada:latest"
assert_repository "" "ostree-unverified-registry:docker://invalid"

armada_steam_channels_apply "$ARMADA_CANONICAL_REGISTRY" stable
armada_steam_channels_apply "$ARMADA_LEGACY_REGISTRY" beta
if armada_steam_channels_apply "$ARMADA_CANONICAL_REGISTRY" feature-a; then
    echo "non-channel tag unexpectedly uses Steam channels" >&2
    exit 1
fi
if armada_steam_channels_apply "local.armadaos.dev/armada" stable; then
    echo "external registry unexpectedly uses Steam channels" >&2
    exit 1
fi

TEST_TMP=$(mktemp -d)
trap 'rm -rf "$TEST_TMP"' EXIT
ARMADA_CHANNEL_STATE="$TEST_TMP/channel"

assert_target() {
    local expected_repository="$1" expected_tag="$2" state="$3" ref="$4" actual
    if [[ "$state" == - ]]; then
        rm -f "$ARMADA_CHANNEL_STATE"
    else
        printf '%s\n' "$state" > "$ARMADA_CHANNEL_STATE"
    fi
    actual="$(armada_update_target "$ref" || true)"
    if [[ "$actual" != "$expected_repository $expected_tag" ]]; then
        printf 'target selection failed: expected %q, got %q for %q\n' \
            "$expected_repository $expected_tag" "$actual" "$ref" >&2
        exit 1
    fi
}

assert_target "$ARMADA_CANONICAL_REGISTRY" beta beta \
    "ostree-image-signed:docker://${ARMADA_CANONICAL_REGISTRY}:stable"
assert_target "$ARMADA_LEGACY_REGISTRY" stable stable \
    "ostree-image-signed:docker://${ARMADA_LEGACY_REGISTRY}:testing"
assert_target "$ARMADA_CANONICAL_REGISTRY" stable invalid \
    "ostree-image-signed:docker://${ARMADA_CANONICAL_REGISTRY}:stable"
assert_target "$ARMADA_CANONICAL_REGISTRY" testing - \
    "ostree-image-signed:docker://${ARMADA_CANONICAL_REGISTRY}:testing"
assert_target "$ARMADA_CANONICAL_REGISTRY" feature-a beta \
    "ostree-image-signed:docker://${ARMADA_CANONICAL_REGISTRY}:feature-a"
assert_target "local.armadaos.dev/armada" feature-a beta \
    "ostree-unverified-registry:docker://local.armadaos.dev/armada:feature-a"
assert_target "$ARMADA_CANONICAL_REGISTRY" beta beta \
    "ostree-image-signed:docker://${ARMADA_CANONICAL_REGISTRY}@sha256:deadbeef"
assert_target "$ARMADA_CANONICAL_REGISTRY" beta beta \
    "containers-storage:localhost/armada:latest"
assert_target "example.invalid/${ARMADA_LEGACY_REGISTRY}" stable beta \
    "ostree-image-signed:docker://example.invalid/${ARMADA_LEGACY_REGISTRY}:stable"

assert_no_target() {
    local state="$1" ref="$2" actual
    if [[ "$state" == - ]]; then
        rm -f "$ARMADA_CHANNEL_STATE"
    else
        printf '%s\n' "$state" > "$ARMADA_CHANNEL_STATE"
    fi
    if actual=$(armada_update_target "$ref"); then
        printf 'target unexpectedly accepted: %q for %q\n' "$actual" "$ref" >&2
        exit 1
    fi
}

assert_no_target beta \
    "ostree-unverified-registry:docker://local.armadaos.dev/armada@sha256:deadbeef"
assert_no_target testing \
    "ostree-image-signed:docker://example.invalid/${ARMADA_LEGACY_REGISTRY}@sha256:deadbeef"
(
    armada_booted_channel() { :; }
    assert_no_target - \
        "ostree-image-signed:docker://${ARMADA_CANONICAL_REGISTRY}@sha256:deadbeef"
)

UPDATE="$ROOT/system_files/usr/libexec/armada/armada-update"
grep -Fq 'if armada_steam_channels_apply "$repository" "$desired"; then' "$UPDATE"

python3 - "$ROOT" <<'PY'
import json
from pathlib import Path
import sys
import tomllib

root = Path(sys.argv[1])
canonical = "ghcr.io/armada-os/armada"
legacy = "ghcr.io/virtudude/armada"
mirror_path = (
    root / "system_files/etc/containers/registries.conf.d/50-armada-migration.conf"
)

policy = json.loads(
    (root / "system_files/etc/containers/policy.json").read_text()
)
docker = policy["transports"]["docker"]
assert docker[legacy][0]["signedIdentity"] == {
    "type": "exactRepository",
    "dockerRepository": canonical,
}
assert docker[canonical][0]["signedIdentity"] == {"type": "matchRepository"}

assert mirror_path.is_file()
assert not (
    root
    / "system_files/usr/share/containers/registries.conf.d/50-armada-migration.conf"
).exists()
mirror = tomllib.loads(mirror_path.read_text())
registry = mirror["registry"][0]
assert registry["prefix"] == legacy
assert registry["location"] == legacy
assert registry["mirror"] == [{"location": canonical}]

sigstore = (
    root / "system_files/etc/containers/registries.d/ghcr-armada.yaml"
).read_text()
for repository in (legacy, canonical):
    assert f"  {repository}:\n    use-sigstore-attachments: true" in sigstore
PY

printf 'update repository migration test passed\n'
