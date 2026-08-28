#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/system_files/usr/lib/armada/update-lib"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/bin"

cat > "$tmp/bin/skopeo" <<'EOF'
#!/bin/bash
[[ "$1" == "inspect" && "$2" != "--raw" ]] || exit 1
[[ -z "${SKOPEO_FAIL:-}" ]] || exit 1
cat "$SKOPEO_FIXTURE"
EOF
cat > "$tmp/bin/ostree" <<'EOF'
#!/bin/bash
if [[ "$1" == config ]]; then
    case "$3" in
        get)
            [[ -f "$OSTREE_CONFIG_FILE" ]] || exit 1
            cat "$OSTREE_CONFIG_FILE"
            ;;
        set)
            [[ -z "${OSTREE_SET_FAIL:-}" ]] || exit 1
            count=0
            [[ ! -f "$OSTREE_SET_COUNT" ]] || read -r count < "$OSTREE_SET_COUNT"
            printf '%s\n' "$((count + 1))" > "$OSTREE_SET_COUNT"
            printf '%s\n' "$5" > "$OSTREE_CONFIG_FILE"
            ;;
        *) exit 1 ;;
    esac
    exit
fi
[[ -z "${OSTREE_REFS_FAIL:-}" ]] || exit 1
printf '%s\n' 'ostree/container/blob/sha256_3A_present'
EOF
chmod +x "$tmp/bin/skopeo" "$tmp/bin/ostree"

cat > "$tmp/image.json" <<'EOF'
{
  "Digest": "sha256:image",
  "Labels": {"org.opencontainers.image.version": "20260822 test build"},
  "LayersData": [
    {"Digest": "sha256:present", "Size": 100},
    {"Digest": "sha256:missing", "Size": 250}
  ]
}
EOF
export SKOPEO_FIXTURE="$tmp/image.json"
export OSTREE_CONFIG_FILE="$tmp/ostree-config"
export OSTREE_SET_COUNT="$tmp/ostree-set-count"
PATH="$tmp/bin:$PATH"

ARMADA_OSTREE_REPO="$tmp"
stat() {
    case "${3:-}" in
        '%S %f') printf '4096 12345\n' ;;
        '%S %b') printf '4096 67890\n' ;;
        *) command stat "$@" ;;
    esac
}
[[ "$(armada_available_bytes)" == "$((4096 * 12345))" ]]
[[ "$(armada_total_bytes)" == "$((4096 * 67890))" ]]
unset -f stat
ARMADA_OSTREE_REPO="$tmp/missing"
if armada_available_bytes >/dev/null; then
    echo "filesystem byte calculation accepted a missing repository" >&2
    exit 1
fi
ARMADA_OSTREE_REPO="$tmp"

# Full skopeo inspection resolves both single manifests and image indexes to
# platform-specific LayersData; unlike --raw, the parser never assumes a
# top-level OCI manifest shape.
info=$(armada_remote_info testing "$ARMADA_CANONICAL_REGISTRY")
[[ "$info" == "250 sha256:image 20260822 test build" ]]
read -r required digest version <<<"$info"
[[ "$required" == 250 && "$digest" == "sha256:image" && "$version" == "20260822 test build" ]]

export SKOPEO_FAIL=1
if armada_remote_info testing "$ARMADA_CANONICAL_REGISTRY" >/dev/null; then
    echo "update metadata inspection ignored a registry failure" >&2
    exit 1
fi
unset SKOPEO_FAIL

set +e
OSTREE_REFS_FAIL=1 armada_remote_info testing "$ARMADA_CANONICAL_REGISTRY" >/dev/null
status=$?
set -e
[[ "$status" == 2 ]]

cat > "$tmp/image.json" <<'EOF'
{"Digest":"sha256:image","Labels":null,"LayersData":{}}
EOF
if armada_remote_info testing "$ARMADA_CANONICAL_REGISTRY" >/dev/null; then
    echo "update metadata parser accepted invalid LayersData" >&2
    exit 1
fi

mock_required=$((5 * 1024 * 1024 * 1024 / 2))
armada_available_bytes() { printf '%s\n' $((mock_required + ARMADA_UPDATE_RESERVE_BYTES)); }
armada_update_fits "$mock_required"

armada_available_bytes() { printf '%s\n' $((mock_required + ARMADA_UPDATE_RESERVE_BYTES - 1)); }
if armada_update_fits "$mock_required" 2>/dev/null; then
    echo "update fit check accepted a target one byte over capacity" >&2
    exit 1
fi

mock_required=0
armada_available_bytes() { printf '1\n'; }
armada_update_fits "$mock_required"

armada_available_bytes() { printf 'not-a-number\n'; }
set +e
armada_update_fits 1 2>/dev/null
status=$?
set -e
[[ "$status" == 2 ]]

armada_total_bytes() { printf '%s\n' $((10 * 1024 * 1024 * 1024)); }
[[ "$(armada_fallback_reserve_bytes)" == "$ARMADA_UPDATE_RESERVE_BYTES" ]]

armada_total_bytes() { printf '511111573504\n'; }
[[ "$(armada_fallback_reserve_bytes)" == "15333347206" ]]

[[ "$(armada_update_reserve_bytes 2>/dev/null)" == "15333347206" ]]

printf '2GB\n' > "$OSTREE_CONFIG_FILE"
[[ "$(armada_update_reserve_bytes)" == "$ARMADA_UPDATE_RESERVE_BYTES" ]]

MIGRATION="$ROOT/system_files/usr/libexec/armada/armada-update-reserve"
UNIT="$ROOT/system_files/usr/lib/systemd/system/armada-update-reserve.service"
BUILD="$ROOT/build_files/40-vendor-system-files.sh"
export ARMADA_UPDATE_LIB="$ROOT/system_files/usr/lib/armada/update-lib"

rm -f "$OSTREE_CONFIG_FILE" "$OSTREE_SET_COUNT"
ARMADA_MIGRATION_OSTREE_REPO="$tmp/repo" "$MIGRATION" --needed
ARMADA_MIGRATION_OSTREE_REPO="$tmp/repo" "$MIGRATION" >/dev/null
[[ "$(<"$OSTREE_CONFIG_FILE")" == "2GB" ]]
[[ "$(<"$OSTREE_SET_COUNT")" == 1 ]]

# The configured value itself is the migration state and skips future remounts.
if ARMADA_MIGRATION_OSTREE_REPO="$tmp/repo" "$MIGRATION" --needed; then
    echo "update reserve migration remained necessary after success" >&2
    exit 1
fi
ARMADA_MIGRATION_OSTREE_REPO="$tmp/repo" OSTREE_SET_FAIL=1 "$MIGRATION" >/dev/null
[[ "$(<"$OSTREE_SET_COUNT")" == 1 ]]

rm -f "$OSTREE_CONFIG_FILE"
if ARMADA_MIGRATION_OSTREE_REPO="$tmp/repo" OSTREE_SET_FAIL=1 "$MIGRATION" 2>/dev/null; then
    echo "update reserve migration ignored a config write failure" >&2
    exit 1
fi

grep -Fxq 'PrivateMounts=yes' "$UNIT"
grep -Fxq 'ExecCondition=/usr/libexec/armada/armada-update-reserve --needed' "$UNIT"
grep -Fxq 'ExecStartPre=/usr/bin/mount -o remount,rw /sysroot' "$UNIT"
grep -Fq 'systemctl enable armada-update-reserve.service' "$BUILD"

printf 'update space test passed\n'
