#!/usr/bin/env bash
# Exercise ABL safety policy with file-backed partitions.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PKG="$ROOT/packages/openabl-updater"
UPDATE="$PKG/src/armada-abl-update"
FINALIZE="$PKG/src/armada-abl-finalize"
VERSION_TOOL="$PKG/src/abl-version"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_contains() { [[ "$1" == *"$2"* ]] || fail "expected ${2@Q} in ${1@Q}"; }

TARGET="$WORK/target"
PAYLOAD_DIR="$TARGET/usr/lib/openabl-updater"
mkdir -p "$PAYLOAD_DIR" "$WORK/bin"
payload="$PAYLOAD_DIR/abl_signed-SM8550.elf"
rocknix="$WORK/rocknix"
rocknix_newer_number="$WORK/rocknix-1.2"
old_openabl="$WORK/old-openabl"
unknown="$WORK/unknown"
newer="$WORK/newer"
same_version="$WORK/same-version"
wrong_soc="$WORK/wrong-soc"
short_old="$WORK/short-old"
make_blob() {
    python3 - "$1" "$2" "${3:-8192}" <<'PY'
import sys

path, tag, raw_size = sys.argv[1:]
size = int(raw_size)
pattern = tag.encode() + b"\0"
with open(path, "wb") as output:
    output.write((pattern * (size // len(pattern) + 1))[:size])
PY
}
hash_of() { sha256sum "$1" | cut -d' ' -f1; }
make_blob "$payload" openabl-1.1-sm8550
make_blob "$rocknix" rocknix-1.1.7-sm8550
make_blob "$rocknix_newer_number" rocknix-1.2-sm8550
make_blob "$old_openabl" openabl-1.0-sm8550
make_blob "$unknown" unknown-stock
make_blob "$newer" openabl-1.2-sm8550
make_blob "$same_version" alternate-openabl-1.1-sm8550
make_blob "$wrong_soc" rocknix-1.1.7-sm8650
make_blob "$short_old" rocknix-1.1.6-sm8550 4096
target_hash=$(hash_of "$payload")
target_size=$(stat -c %s "$payload")

cat > "$PAYLOAD_DIR/legacy-releases.tsv" <<EOF
abl	version	soc	size	sha256
ROCKNIX	1.1.6	SM8550	4096	$(hash_of "$short_old")
ROCKNIX	1.1.7	SM8550	8192	$(hash_of "$rocknix")
ROCKNIX	1.1.7	SM8650	8192	$(hash_of "$wrong_soc")
ROCKNIX	1.2	SM8550	8192	$(hash_of "$rocknix_newer_number")
OpenABL	1.0	SM8550	8192	$(hash_of "$old_openabl")
OpenABL	1.1	SM8550	8192	${target_hash}
OpenABL	1.2	SM8550	8192	$(hash_of "$newer")
EOF
catalog="$PAYLOAD_DIR/legacy-releases.tsv"
identify() { ARMADA_ABL_RELEASES="$catalog" python3 "$VERSION_TOOL" "$@"; }
[[ "$(identify --with-soc "$payload")" == "OpenABL 1.1 SM8550" ]] ||
    fail "hash catalog did not identify target payload"
[[ "$(identify "$rocknix")" == "ROCKNIX 1.1.7" ]] ||
    fail "hash catalog did not identify a ROCKNIX payload"
[[ "$(identify --lookup OpenABL 1.1 SM8550)" == "8192 ${target_hash}" ]] ||
    fail "catalog lookup did not return target metadata"
! identify --lookup ROCKNIX 1.1 SM8550 >/dev/null || fail "lookup matched another ABL's version"

cat > "$PAYLOAD_DIR/manifest" <<EOF
ARMADA_ABL_NAME=OpenABL
ARMADA_ABL_VERSION=1.1
ARMADA_ABL_SHA256_SM8550=${target_hash}
EOF

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
EFIVARS="$WORK/efivars"
ESRT="$WORK/esrt"
SOC_ID="$WORK/soc_id"
echo 603 > "$SOC_ID"
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
    ARMADA_EFIVARS="$EFIVARS"
    ARMADA_ESRT="$ESRT"
    ARMADA_ABL_SOC_ID_PATH="$SOC_ID"
    ABL_VERSION_TOOL="$VERSION_TOOL"
    ARMADA_ABL_RELEASES="$catalog"
    SPLASH="$WORK/splash"
    PATH="$WORK/bin:$PATH"
)
run_update() { env "${base_env[@]}" "$UPDATE" "$@" --target-root "$TARGET" 2>&1; }
install_both() { cp "$1" "$ABL_A"; cp "$1" "$ABL_B"; : > "$WORK/writes"; }
expect_updated() {
    local what=$1 out
    out=$(run_update) || fail "$what: update failed: $out"
    cmp -s -n "$target_size" "$payload" "$ABL_A" || fail "$what: ABL A copy was not updated"
    cmp -s -n "$target_size" "$payload" "$ABL_B" || fail "$what: ABL B copy was not updated"
}
expect_refused() {
    local what=$1 message=$2 out rc before
    before=$(cat "$ABL_A" "$ABL_B" | sha256sum)
    set +e; out=$(run_update); rc=$?; set -e
    [[ $rc -eq 7 ]] || fail "$what returned $rc instead of 7"
    assert_contains "$out" "$message"
    [[ ! -s "$WORK/writes" ]] || fail "$what was overwritten"
    [[ "$(cat "$ABL_A" "$ABL_B" | sha256sum)" == "$before" ]] || fail "$what was modified"
}
# efivarfs values start with 4 bytes of attributes.
set_efivar() {
    mkdir -p "$EFIVARS"
    python3 - "$EFIVARS/$1" "$2" <<'PY'
import sys

path, text = sys.argv[1:]
with open(path, "wb") as output:
    output.write(b"\x06\x00\x00\x00" + (text + "\0").encode("utf-16-le"))
PY
}
LOADER_INFO=LoaderInfo-4a67b082-0a4c-41cf-b6c7-440b29bb8c4f
SETTINGS=SettingsSchema-8c5f2b7e-3a41-4d6c-9e2f-5b7a1c0d4e93

# socinfo must confirm the configured SoC before anything is written.
install_both "$rocknix"
echo 682 > "$SOC_ID"
expect_refused "mismatched SoC id" "SoC id '682' does not confirm SM8550"
echo 519 > "$SOC_ID"
expect_refused "unknown SoC id" "SoC id '519' does not confirm SM8550"
rm "$SOC_ID"
expect_refused "missing SoC id" "SoC id 'unknown' does not confirm SM8550"
echo 601 > "$SOC_ID"
# Every approved ROCKNIX release migrates, even one numbered above the target.
expect_updated "ROCKNIX 1.1.7"
mapfile -t writes < "$WORK/writes"
[[ "${writes[0]:-}" == "$ABL_A" && "${writes[1]:-}" == "$ABL_B" ]] ||
    fail "expected abl_a-then-abl_b writes, got: ${writes[*]:-none}"
install_both "$rocknix_newer_number"
expect_updated "ROCKNIX 1.2"
install_both "$old_openabl"
expect_updated "older OpenABL"

: > "$WORK/writes"
assert_contains "$(run_update)" "OpenABL 1.1 already installed"
[[ ! -s "$WORK/writes" ]] || fail "matching ABL copies were rewritten"

install_both "$unknown"
expect_refused "unknown ABL" "not a recognized ROCKNIX or OpenABL image"

# Recognize a historical payload by its own length even with a stale tail.
short_tail="$WORK/short-tail"
cp "$short_old" "$short_tail"
python3 - "$short_tail" <<'PY'
import sys

with open(sys.argv[1], "ab") as output:
    output.write(b"stale partition tail" * 300)
PY
[[ "$(identify --with-soc "$short_tail")" == "ROCKNIX 1.1.6 SM8550" ]] ||
    fail "known historical prefix with stale tail was not identified"
install_both "$short_tail"
expect_updated "short historical payload"

# Known bytes outside an approved prefix must not identify a payload.
stale="$WORK/stale-tail"
python3 - "$stale" "$rocknix" <<'PY'
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
install_both "$stale"
expect_refused "stale-tail ABL" "not a recognized ROCKNIX or OpenABL image"

# Even an approved payload must match the DT-confirmed target SoC.
install_both "$wrong_soc"
expect_refused "wrong-SoC ABL" "is ROCKNIX 1.1.7 for SM8650, expected SM8550; refusing to overwrite"

cp "$payload" "$ABL_A"; cp "$rocknix" "$ABL_B"; : > "$WORK/writes"
run_update >/dev/null
mapfile -t writes < "$WORK/writes"
[[ "${#writes[@]}" -eq 1 && "${writes[0]}" == "$ABL_B" ]] ||
    fail "mixed-state repair rewrote the wrong copies: ${writes[*]:-none}"

# Approved newer and unknown divergent same-version images must never be replaced.
install_both "$newer"
expect_refused "newer OpenABL" "OpenABL 1.2 is newer than target 1.1"
install_both "$same_version"
expect_refused "unknown same-version ABL" "not a recognized ROCKNIX or OpenABL image"

# Unlisted copies are replaced when the booted OpenABL reports an older version.
set_efivar "$SETTINGS" ""
install_both "$unknown"
expect_refused "OpenABL build of unknown version" "not a recognized ROCKNIX or OpenABL image"
[[ "$(env "${base_env[@]}" python3 "$VERSION_TOOL" --firmware)" == "OpenABL" ]] ||
    fail "OpenABL settings variables were not detected"
set_efivar "$LOADER_INFO" "OpenABL 1.0"
[[ "$(env "${base_env[@]}" python3 "$VERSION_TOOL" --firmware)" == "OpenABL 1.0" ]] ||
    fail "LoaderInfo version was not read"
expect_updated "booted OpenABL 1.0 over unknown copies"
cp "$unknown" "$ABL_A"; cp "$same_version" "$ABL_B"; : > "$WORK/writes"
expect_updated "booted OpenABL 1.0 over divergent copies"
cp "$payload" "$ABL_A"; cp "$unknown" "$ABL_B"; : > "$WORK/writes"
run_update >/dev/null
mapfile -t writes < "$WORK/writes"
[[ "${#writes[@]}" -eq 1 && "${writes[0]}" == "$ABL_B" ]] ||
    fail "reported-version repair rewrote the wrong copies: ${writes[*]:-none}"

# Hashes beat the reported version.
install_both "$newer"
expect_refused "listed newer copy under a stale report" "OpenABL 1.2 is newer than target 1.1"
cp "$payload" "$ABL_A"; cp "$wrong_soc" "$ABL_B"; : > "$WORK/writes"
expect_refused "listed wrong-SoC copy under a report" "for SM8650, expected SM8550; refusing to overwrite"
set_efivar "$LOADER_INFO" "OpenABL 1.3"
install_both "$rocknix"
expect_updated "listed ROCKNIX copy under a newer report"
set_efivar "$LOADER_INFO" "OpenABL 1.0"

# Custom builds of the same or a newer version are left alone.
expect_left() {
    local what=$1 out rc before
    before=$(cat "$ABL_A" "$ABL_B" | sha256sum)
    set +e; out=$(run_update); rc=$?; set -e
    [[ $rc -eq 0 ]] || fail "$what returned $rc instead of 0: $out"
    assert_contains "$out" "is not older than 1.1; leaving it"
    [[ ! -s "$WORK/writes" ]] || fail "$what was overwritten"
    [[ "$(cat "$ABL_A" "$ABL_B" | sha256sum)" == "$before" ]] || fail "$what was modified"
}
install_both "$unknown"
set_efivar "$LOADER_INFO" "OpenABL 1.1"
expect_left "CI build of the packaged version"
set_efivar "$LOADER_INFO" "OpenABL 1.3"
expect_left "newer booted OpenABL"
# A version OpenABL could never report is no evidence at all.
set_efivar "$LOADER_INFO" "OpenABL 1.1-ci.42"
expect_refused "malformed reported version" "not a recognized ROCKNIX or OpenABL image"
rm -rf "$EFIVARS"

mkdir -p "$ESRT/entries/entry0"
printf 'c02d2ab2-3223-42be-9608-e28009010000\n' > "$ESRT/entries/entry0/fw_class"
printf '%s\n' $(( (1 << 16) | 0 )) > "$ESRT/entries/entry0/fw_version"
[[ "$(env "${base_env[@]}" python3 "$VERSION_TOOL" --firmware)" == "OpenABL 1.0" ]] ||
    fail "ESRT version was not read"
install_both "$unknown"
expect_updated "OpenABL 1.0 reported through the ESRT"
rm -rf "$ESRT"
! env "${base_env[@]}" python3 "$VERSION_TOOL" --firmware >/dev/null ||
    fail "firmware reported OpenABL without any evidence"

install_both "$rocknix"; : > "$WORK/splash-log"
set +e
out=$(env "${base_env[@]}" ARMADA_TEST_DD_FAIL=1 \
    "$UPDATE" --target-root "$TARGET" 2>&1)
rc=$?
set -e
[[ $rc -ne 0 ]] || fail "injected write failure succeeded"
grep -q '^--error Bootloader update failed' "$WORK/splash-log" ||
    fail "write failure did not replace the splash with an error"

# armada-control has no ABL update toggle.
python3 - "$ROOT" <<'PY'
import importlib.machinery
import importlib.util
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "system_files/usr/lib/armada"))
path = root / "system_files/usr/libexec/armada/armada-control"
loader = importlib.machinery.SourceFileLoader("armada_control_service", str(path))
spec = importlib.util.spec_from_loader("armada_control_service", loader)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
assert not any("abl_auto" in action for action in control.ACTIONS)
PY

FROOT="$WORK/finalize"; FBOOT="$FROOT/boot"; FSYS="$FROOT/sysroot"
mkdir -p "$FBOOT/loader/entries" "$FSYS/ostree/deploy/old" \
    "$FSYS/ostree/deploy/target/usr/lib/openabl-updater"
cat > "$FBOOT/loader/entries/ostree-1.conf" <<EOF
version 1
options ostree=/ostree/deploy/old
EOF
cat > "$FBOOT/loader/entries/ostree-2.conf" <<EOF
version 2
options quiet ostree=/ostree/deploy/target wildcard=*
EOF
printf 'ARMADA_ABL_NAME=OpenABL\n' > "$FSYS/ostree/deploy/target/usr/lib/openabl-updater/manifest"
cat > "$FROOT/updater" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$ARMADA_FINALIZE_LOG"
EOF
chmod +x "$FROOT/updater"
finalize_env=(BOOTROOT="$FBOOT" SYSROOT="$FSYS"
    ARGS_FILE="$ROOT/system_files/usr/lib/armada/bootimg-args"
    UPDATER="$FROOT/updater" ARMADA_FINALIZE_LOG="$FROOT/finalize-log")
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

# A stale ARMADA_ABL_AUTO=0 is ignored.
printf 'ARMADA_ABL_AUTO=0\n' >> "$FSYS/ostree/deploy/target/usr/lib/openabl-updater/manifest"
: > "$FROOT/finalize-log"
printf 'auto_update_enabled=0\n' > "$FROOT/abl.conf"
env "${finalize_env[@]}" ABL_CONFIG="$FROOT/abl.conf" "$FINALIZE"
assert_contains "$(cat "$FROOT/finalize-log")" \
    "--target-root $FSYS/ostree/deploy/target"

# Deployments predating the packaged ABL payload silently remain ineligible.
rm -f "$FSYS/ostree/deploy/target/usr/lib/openabl-updater/manifest"
: > "$FROOT/finalize-log"
env "${finalize_env[@]}" "$FINALIZE"
[[ ! -s "$FROOT/finalize-log" ]] || fail "manifest-less target invoked writer"

sync_unit="$ROOT/system_files/usr/lib/systemd/system/armada-bootimg-sync.service"
! grep -q 'armada-abl-finalize' "$sync_unit" ||
    fail "the base unit still runs the ABL finalizer; openabl-updater owns that hook"
grep -q '^ExecStop=-/usr/libexec/openabl-updater/armada-abl-finalize$' "$PKG/src/armada-bootimg-sync-openabl-updater.conf" ||
    fail "shutdown ABL finalizer is not non-fatal"

# Every chipset's image is checksummed and the legacy catalog loads.
spec="$PKG/openabl-updater.spec"
for soc in $(sed -n 's/^%global openabl_socs //p' "$spec"); do
    grep -q "/abl_signed-${soc}.elf$" "$spec" || fail "spec does not download $soc"
    grep -q "/abl_signed-${soc}.elf.sha256$" "$spec" || fail "spec does not download the $soc checksum"
done
ARMADA_ABL_RELEASES="$PKG/legacy-releases.tsv" python3 "$VERSION_TOOL" \
    --lookup ROCKNIX 1.2 SM8550 >/dev/null || fail "legacy catalog does not load"

printf 'ABL update test passed\n'
