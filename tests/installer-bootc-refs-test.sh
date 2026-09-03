#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLER="$ROOT/system_files/usr/libexec/armada/armada-installer"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_logged() {
    grep -Fxq "$1" "$WORK/log" || fail "missing operation: $1"
}
assert_not_logged() {
    grep -Fxq "$1" "$WORK/log" && fail "unexpected operation: $1"
    return 0
}
pulled_marker() {
    printf '%s/pulled-%s' "$WORK" "${1//\//_}"
}

commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
layer_one=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
layer_two=cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
unrelated=dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
blob_one="ostree/container/blob/sha256_3A_${layer_one}"
blob_two="ostree/container/blob/sha256_3A_${layer_two}"
image_ref=ostree/container/image/docker_3A__2F__2F_ghcr_2E_io/armada-os/armada_3A_testing
other_image=ostree/container/image/docker_3A__2F__2F_example_2E_invalid/os_3A_latest
TARGET="$WORK/target"
mkdir -p "$TARGET/ostree/repo"
: > "$WORK/log"

ostree() {
    local command="$1" ref
    shift
    case "$command" in
        pull-local)
            ref="${*: -1}"
            printf 'pull %s\n' "$ref" >> "$WORK/log"
            [[ $ref != "$blob_two" || ! -e $WORK/fail-layer-two ]] || return 1
            [[ $ref != "$blob_two" || ! -e $WORK/drop-layer-two ]] || return 0
            touch "$(pulled_marker "$ref")"
            ;;
        show)
            if [[ " $* " == *" --print-metadata-key=ostree.manifest "* ]]; then
                printf "'{\"schemaVersion\":2,\"layers\":[{\"digest\":\"sha256:%s\"},{\"digest\":\"sha256:%s\"}]}'\n" \
                    "$layer_one" "$layer_two"
            else
                printf 'commit %s\n' "$commit"
            fi
            ;;
        refs)
            [[ ! -e $WORK/no-image-ref ]] || return 0
            printf '%s\n' "$blob_one" "$blob_two" "$image_ref" "$other_image"
            ;;
        rev-parse)
            ref="${*: -1}"
            if [[ " $* " == *" --repo=$TARGET/ostree/repo "* ]]; then
                [[ -e $(pulled_marker "$ref") ]] || return 1
                printf '%s\n' "$ref"
                return 0
            fi
            case "$ref" in
                "$image_ref") printf '%s\n' "$commit" ;;
                "$other_image") printf '%s\n' "$unrelated" ;;
                *) return 1 ;;
            esac
            ;;
        *) fail "unexpected ostree command: $command $*" ;;
    esac
}

# Exercise the shipped functions without running the installer's command dispatch.
eval "$(sed -n '/^copy_bootc_ref()/,/^seed_kernel()/p' "$INSTALLER" | sed '$d')"

copy_current_bootc_deployment
assert_logged "pull $commit"
assert_logged "pull $blob_one"
assert_logged "pull $blob_two"
assert_logged "pull $image_ref"
assert_not_logged "pull $other_image"

# A missing layer commit must abort rather than leave a bootc deployment that boots
# but cannot compute status or upgrade.
rm -f "$WORK"/pulled-*
: > "$WORK/log"
touch "$WORK/fail-layer-two"
if copy_current_bootc_deployment >/dev/null 2>&1; then
    fail "missing manifest layer unexpectedly succeeded"
fi
assert_not_logged "pull $image_ref"
rm -f "$WORK/fail-layer-two"

# Successful pull output is not enough: verify that every expected ref actually
# resolves in the destination before allowing the install to continue.
rm -f "$WORK"/pulled-*
: > "$WORK/log"
touch "$WORK/drop-layer-two"
if copy_current_bootc_deployment >/dev/null 2>&1; then
    fail "missing target layer ref unexpectedly succeeded validation"
fi
rm -f "$WORK/drop-layer-two"

# Without the image ref, the copied commit is not a complete bootc deployment.
rm -f "$WORK"/pulled-*
: > "$WORK/log"
touch "$WORK/no-image-ref"
if copy_current_bootc_deployment >/dev/null 2>&1; then
    fail "deployment without a matching image ref unexpectedly succeeded"
fi
rm -f "$WORK/no-image-ref"

printf 'installer bootc ref tests passed\n'
