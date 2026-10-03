#!/usr/bin/env bash
# CJK face-selection regression for armada-splash's load_font().
#
# Optional fixture-based test: it compiles a C harness against the shipping
# armada-splash.c, so it needs a compiler and a fixture directory. With no
# fixture directory argument it prints SKIP and exits 0, so nothing is built
# or run.
#
# Usage:
#   tests/splash-font-test.sh <fixture-dir>
#
# <fixture-dir> must hold the verified fonts:
#   NotoSansCJK-Regular.ttc      10 faces; index 7 is Noto Sans Mono CJK SC
#   NotoSansMono-SemiBold.ttf    ordinary single-face Latin mono
#
# Every object file, binary and log lands under a task-controlled output
# directory: $SPLASH_FONT_TEST_OUT, defaulting to packages/armada-splash/tests/
# build inside this checkout.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/packages/armada-splash/src"
HARNESS="$ROOT/packages/armada-splash/tests/font-test.c"

fixture_dir="${1:-}"
if [[ -z "$fixture_dir" ]]; then
    echo "SKIP: no fixture directory; pass one to run the splash font test"
    exit 0
fi

cjk_font="$fixture_dir/NotoSansCJK-Regular.ttc"
latin_font="$fixture_dir/NotoSansMono-SemiBold.ttf"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

[[ -f "$cjk_font" ]] || fail "fixture not found: $cjk_font"
[[ -f "$latin_font" ]] || fail "fixture not found: $latin_font"
[[ -f "$HARNESS" ]] || fail "harness not found: $HARNESS"
[[ -f "$SRC/stb_impl.c" ]] || fail "missing $SRC/stb_impl.c"

OUT="${SPLASH_FONT_TEST_OUT:-$ROOT/packages/armada-splash/tests/build}"
mkdir -p "$OUT"

CC="${CC:-cc}"
command -v "$CC" >/dev/null 2>&1 || fail "no C compiler ($CC)"

# armada-splash.c compiles its DRM backend unconditionally even though this
# harness never reaches it, so the link needs libdrm.
drm_flags=(-ldrm)
if command -v pkg-config >/dev/null 2>&1 && pkg-config --exists libdrm 2>/dev/null; then
    read -r -a drm_flags <<<"$(pkg-config --cflags --libs libdrm)"
fi

"$CC" -O2 -w -c "$SRC/stb_impl.c" -o "$OUT/stb_impl.o" \
    || fail "stb_impl.c failed to compile"
"$CC" -O2 -Wall -Wextra -I"$SRC" "$HARNESS" "$SRC/splash-i18n.c" "$OUT/stb_impl.o" \
    "${drm_flags[@]}" -lm \
    -o "$OUT/font-test" || fail "font-test.c failed to compile or link"

missing_font="$OUT/does-not-exist.ttf"
rm -f "$missing_font"

status=0
run_mode() { # <mode> <font> <label>
    if "$OUT/font-test" "$1" "$2" >"$OUT/$1.log" 2>&1; then
        printf 'PASS: %s\n' "$3"
    else
        printf 'FAIL: %s\n' "$3"
        sed 's/^/    /' "$OUT/$1.log" >&2
        status=1
    fi
}

run_mode cjk     "$cjk_font"     "CJK collection selects Simplified-Chinese mono face 7"
run_mode latin   "$latin_font"   "single-face Latin font still loads as face 0"
run_mode missing "$missing_font" "missing font keeps the existing failure behaviour"

[[ "$status" -eq 0 ]] || { printf 'splash font test FAILED\n'; exit 1; }
printf 'splash font test passed\n'
