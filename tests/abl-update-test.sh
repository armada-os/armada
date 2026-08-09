#!/usr/bin/env bash
# Exercise ABL safety policy with file-backed partitions.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
UPDATE="$ROOT/system_files/usr/libexec/armada/armada-abl-update"
FINALIZE="$ROOT/system_files/usr/libexec/armada/armada-abl-finalize"
VERSION_TOOL="$ROOT/system_files/usr/lib/armada/abl-version"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_contains() { [[ "$1" == *"$2"* ]] || fail "expected ${2@Q} in ${1@Q}"; }

TARGET="$WORK/target"
PAYLOAD_DIR="$TARGET/usr/lib/armada/abl"
mkdir -p "$PAYLOAD_DIR" "$WORK/bin"
payload="$PAYLOAD_DIR/abl_signed-SM8550.elf"
old="$WORK/old"
unknown="$WORK/unknown"
newer="$WORK/newer"
same_version="$WORK/same-version"
make_abl() {
    python3 - "$1" "$2" "$3" <<'PY'
import lzma
import struct
import sys

path, version, tag = sys.argv[1:]
if version == "unknown":
    volume = b"OEM-ABL\0" + tag.encode()
else:
    volume = b"ROCKNIX-ABL\0" + version.encode() + b"\0" + tag.encode()
filters = [{"id": lzma.FILTER_LZMA1, "dict_size": 16 * 1024 * 1024,
            "lc": 3, "lp": 0, "pb": 2}]
compressed = lzma.compress(volume, format=lzma.FORMAT_ALONE, filters=filters)
guid = bytes.fromhex("98584eee143959429d6edc7bd79403cf")
image = bytearray(8192)
struct.pack_into("<16sHHIIIIIHHHHHH", image, 0,
                 b"\x7fELF\x01\x01\x01" + bytes(9), 2, 40, 1, 0, 52, 0, 0,
                 52, 32, 1, 0, 0, 0)
struct.pack_into("<IIIIIIII", image, 52, 1, 0, 0, 0,
                 len(image), len(image), 7, 4096)
body = b"_FVH" + bytes(124) + guid + b"\x18\x00\x01\x00" + compressed
image[128:128 + len(body)] = body
with open(path, "wb") as output:
    output.write(image)
PY
}
make_abl "$payload" 1.1.7 target
make_abl "$old" 1.1.6 old
make_abl "$unknown" unknown stock
make_abl "$newer" 1.1.8 newer
make_abl "$same_version" 1.1.7 alternate-build
target_hash=$(sha256sum "$payload" | cut -d' ' -f1)

write_manifest() {
    local auto=$1
    cat > "$PAYLOAD_DIR/manifest" <<EOF
ARMADA_ABL_VERSION=1.1.7
ARMADA_ABL_AUTO=${auto}
ARMADA_ABL_SHA256_SM8550=${target_hash}
EOF
}
write_manifest 1

cat > "$WORK/bin/dd" <<'EOF'
#!/usr/bin/env bash
for arg in "$@"; do case "$arg" in if=*) input=${arg#if=} ;; of=*) output=${arg#of=} ;; esac; done
if [[ "${input:-}" == "${ARMADA_TEST_PAYLOAD}" ]]; then
    printf '%s\n' "$output" >> "$ARMADA_TEST_WRITE_LOG"
    [[ "${ARMADA_TEST_DD_FAIL:-0}" != 1 ]] || exit 1
fi
exec /usr/bin/dd "$@"
EOF
chmod +x "$WORK/bin/dd"
cat > "$WORK/splash" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$ARMADA_TEST_SPLASH_LOG"
EOF
chmod +x "$WORK/splash"

ABL_A="$WORK/abl_a"
ABL_B="$WORK/abl_b"
base_env=(
    ARMADA_ABL_TESTING=1
    ARMADA_ABL_DEVICE_ID=ayn-odin-2
    ARMADA_ABL_SOC=SM8550
    ARMADA_ABL_A="$ABL_A"
    ARMADA_ABL_B="$ABL_B"
    ARMADA_ABL_LOCK="$WORK/lock"
    ARMADA_TEST_PAYLOAD="$payload"
    ARMADA_TEST_WRITE_LOG="$WORK/writes"
    ARMADA_TEST_SPLASH_LOG="$WORK/splash-log"
    ABL_VERSION_TOOL="$VERSION_TOOL"
    SPLASH="$WORK/splash"
    PATH="$WORK/bin:$PATH"
)
run_update() { env "${base_env[@]}" "$UPDATE" "$@" --target-root "$TARGET" 2>&1; }

cp "$old" "$ABL_A"; cp "$old" "$ABL_B"
: > "$WORK/writes"
run_update >/dev/null
cmp -s "$payload" "$ABL_A" || fail "ABL A copy was not updated"
cmp -s "$payload" "$ABL_B" || fail "ABL B copy was not updated"
mapfile -t writes < "$WORK/writes"
[[ "${writes[0]:-}" == "$ABL_A" && "${writes[1]:-}" == "$ABL_B" ]] ||
    fail "expected abl_a-then-abl_b writes, got: ${writes[*]:-none}"

: > "$WORK/writes"
assert_contains "$(run_update)" "already installed"
[[ ! -s "$WORK/writes" ]] || fail "matching ABL copies were rewritten"

cp "$unknown" "$ABL_A"; cp "$unknown" "$ABL_B"
before=$(sha256sum "$ABL_A")
set +e; out=$(run_update); rc=$?; set -e
[[ $rc -eq 7 ]] || fail "unknown ABL returned $rc instead of 7"
assert_contains "$out" "not an identifiable ROCKNIX ABL"
[[ "$(sha256sum "$ABL_A")" == "$before" ]] || fail "unknown ABL was modified"

# notrunc can leave an old image past the ELF load segment; it must be ignored.
stale="$WORK/stale-tail"
python3 - "$stale" "$old" <<'PY'
import struct
import sys

path, old = sys.argv[1:]
image = bytearray(512)
struct.pack_into("<16sHHIIIIIHHHHHH", image, 0,
                 b"\x7fELF\x01\x01\x01" + bytes(9), 2, 40, 1, 0, 52, 0, 0,
                 52, 32, 1, 0, 0, 0)
struct.pack_into("<IIIIIIII", image, 52, 1, 0, 0, 0,
                 len(image), len(image), 7, 4096)
image[128:132] = b"_FVH"
with open(path, "wb") as output, open(old, "rb") as trailing:
    output.write(image)
    output.write(trailing.read())
PY
cp "$stale" "$ABL_A"; cp "$stale" "$ABL_B"
set +e; out=$(run_update); rc=$?; set -e
[[ $rc -eq 7 ]] || fail "stale-tail ABL returned $rc instead of 7"
assert_contains "$out" "not an identifiable ROCKNIX ABL"

cp "$payload" "$ABL_A"; cp "$old" "$ABL_B"
: > "$WORK/writes"
run_update >/dev/null
mapfile -t writes < "$WORK/writes"
[[ "${#writes[@]}" -eq 1 && "${writes[0]}" == "$ABL_B" ]] ||
    fail "mixed-state repair rewrote the wrong copies: ${writes[*]:-none}"

# User-managed newer or divergent same-version images must never be replaced.
for fixture in "$newer" "$same_version"; do
    cp "$fixture" "$ABL_A"; cp "$fixture" "$ABL_B"
    : > "$WORK/writes"
    set +e; out=$(run_update); rc=$?; set -e
    [[ $rc -eq 7 ]] || fail "protected ABL returned $rc instead of 7"
    [[ ! -s "$WORK/writes" ]] || fail "protected ABL was overwritten"
done

cp "$old" "$ABL_A"; cp "$old" "$ABL_B"; : > "$WORK/splash-log"
set +e
out=$(env "${base_env[@]}" ARMADA_TEST_DD_FAIL=1 \
    "$UPDATE" --target-root "$TARGET" 2>&1)
rc=$?
set -e
[[ $rc -ne 0 ]] || fail "injected write failure succeeded"
grep -q '^--error Bootloader update failed' "$WORK/splash-log" ||
    fail "write failure did not replace the splash with an error"

# The privileged settings service persists an explicit preference and falls
# back to the image policy only while the preference is absent.
python3 - "$ROOT" "$WORK" <<'PY'
import importlib.machinery
import importlib.util
import pathlib
import sys

root, work = map(pathlib.Path, sys.argv[1:])
sys.path.insert(0, str(root / "system_files/usr/lib/armada"))
path = root / "system_files/usr/libexec/armada/armada-control"
loader = importlib.machinery.SourceFileLoader("armada_control_service", str(path))
spec = importlib.util.spec_from_loader("armada_control_service", loader)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)

control.ABL_CONFIG = work / "abl.conf"
control.ABL_MANIFEST = work / "abl-manifest"
control.ABL_MANIFEST.write_text("ARMADA_ABL_AUTO=0\n")
assert control.abl_auto_enabled() is False
assert control.action_set_abl_auto_enabled({"enabled": True}) == {"enabled": True}
assert control.ABL_CONFIG.read_text() == "auto_update_enabled=1\n"
control.ABL_MANIFEST.write_text("ARMADA_ABL_AUTO=1\n")
assert control.action_set_abl_auto_enabled({"enabled": False}) == {"enabled": False}
assert control.ABL_CONFIG.read_text() == "auto_update_enabled=0\n"
PY

FROOT="$WORK/finalize"; FBOOT="$FROOT/boot"; FSYS="$FROOT/sysroot"
mkdir -p "$FBOOT/loader/entries" "$FSYS/ostree/deploy/old" \
    "$FSYS/ostree/deploy/target/usr/lib/armada/abl"
cat > "$FBOOT/loader/entries/ostree-1.conf" <<EOF
version 1
options ostree=/ostree/deploy/old
EOF
cat > "$FBOOT/loader/entries/ostree-2.conf" <<EOF
version 2
options quiet ostree=/ostree/deploy/target wildcard=*
EOF
printf 'ARMADA_ABL_AUTO=1\n' > "$FSYS/ostree/deploy/target/usr/lib/armada/abl/manifest"
cat > "$FROOT/updater" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$ARMADA_FINALIZE_LOG"
EOF
chmod +x "$FROOT/updater"
finalize_env=(BOOTROOT="$FBOOT" SYSROOT="$FSYS"
    ARGS_FILE="$ROOT/system_files/usr/lib/armada/bootimg-args"
    UPDATER="$FROOT/updater" ARMADA_FINALIZE_LOG="$FROOT/finalize-log"
    ABL_CONFIG="$FROOT/abl.conf")
env "${finalize_env[@]}" "$FINALIZE"
assert_contains "$(cat "$FROOT/finalize-log")" \
    "--target-root $FSYS/ostree/deploy/target"

# Default deployments remain eligible so bridge releases catch up on shutdown.
ln -s ostree/deploy/target "$FSYS/target-link"
sed -i 's|/ostree/deploy/target|/target-link|' "$FBOOT/loader/entries/ostree-2.conf"
: > "$FROOT/finalize-log"
env "${finalize_env[@]}" "$FINALIZE"
assert_contains "$(cat "$FROOT/finalize-log")" \
    "--target-root $FSYS/ostree/deploy/target"

# AUTO gates the shutdown finalizer, not direct operator invocation.
printf 'ARMADA_ABL_AUTO=0\n' > "$FSYS/ostree/deploy/target/usr/lib/armada/abl/manifest"
: > "$FROOT/finalize-log"
env "${finalize_env[@]}" "$FINALIZE"
[[ ! -s "$FROOT/finalize-log" ]] || fail "disabled automatic target invoked writer"

# A persistent user choice overrides the image default in either direction.
printf 'auto_update_enabled=1\n' > "$FROOT/abl.conf"
env "${finalize_env[@]}" "$FINALIZE"
assert_contains "$(cat "$FROOT/finalize-log")" \
    "--target-root $FSYS/ostree/deploy/target"
printf 'ARMADA_ABL_AUTO=1\n' > "$FSYS/ostree/deploy/target/usr/lib/armada/abl/manifest"
printf 'auto_update_enabled=0\n' > "$FROOT/abl.conf"
: > "$FROOT/finalize-log"
env "${finalize_env[@]}" "$FINALIZE"
[[ ! -s "$FROOT/finalize-log" ]] || fail "user-disabled automatic target invoked writer"

# Deployments predating the vendored ABL payload silently remain ineligible.
rm -f "$FROOT/abl.conf" "$FSYS/ostree/deploy/target/usr/lib/armada/abl/manifest"
: > "$FROOT/finalize-log"
env "${finalize_env[@]}" "$FINALIZE"
[[ ! -s "$FROOT/finalize-log" ]] || fail "manifest-less target invoked writer"
printf 'auto_update_enabled=1\n' > "$FROOT/abl.conf"
env "${finalize_env[@]}" "$FINALIZE"
[[ ! -s "$FROOT/finalize-log" ]] || fail "user-enabled manifest-less target invoked writer"

write_manifest 0
cp "$old" "$ABL_A"; cp "$old" "$ABL_B"
run_update >/dev/null
cmp -s "$payload" "$ABL_A" || fail "explicit AUTO=0 qualification did not update A"
cmp -s "$payload" "$ABL_B" || fail "explicit AUTO=0 qualification did not update B"

grep -q '^ARMADA_ABL_AUTO=0$' "$ROOT/abl/release.env" ||
    fail "release manifest enables automatic flashing"
sync_unit="$ROOT/system_files/usr/lib/systemd/system/armada-bootimg-sync.service"
grep -q '^ExecStop=-/usr/libexec/armada/armada-abl-finalize$' "$sync_unit" ||
    fail "shutdown ABL finalizer is not non-fatal"

printf 'ABL update test passed\n'
