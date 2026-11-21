#!/usr/bin/env bash
set -u

BIN="${1:-}"; FONT="${2:-}"
if [ -z "$BIN" ] || [ -z "$FONT" ]; then
  echo "SKIP: usage: $0 <built-binary> <CJK-font>"
  exit 0
fi
if [ ! -x "$BIN" ]; then echo "FAIL: binary not executable: $BIN" >&2; exit 1; fi
if [ ! -f "$FONT" ]; then echo "FAIL: font missing: $FONT" >&2; exit 1; fi

OUT="${SPLASH_EARLY_LOCALE_TEST_OUT:-}"
made_out=0
if [ -z "$OUT" ]; then OUT="$(mktemp -d)"; made_out=1; fi
mkdir -p "$OUT"
fail=0
fail_msg() { echo "FAIL: $*" >&2; fail=1; }

W=480; H=320
STATUS_FILE="$OUT/status.txt"
printf 'Preparing Armada' > "$STATUS_FILE"

reg_fixture() { # $1=dir $2=locale
  local d="$1/.steam" l="$2"
  mkdir -p "$d"
  cat > "$d/registry.vdf" <<EOF
"Registry"
{
  "HKCU"
  {
    "Software"
    {
      "Valve"
      {
        "Steam"
        {
          "Language" "$l"
        }
      }
    }
  }
}
EOF
}

rpc() { # $1=regdir $2... args -> stdout
  local r="$1"; shift
  HOME="$r" XDG_CONFIG_HOME="$r/cfg" ARMADA_SPLASH_STEAM_REGISTRY="$r/.steam/registry.vdf" timeout 5 "$BIN" "$@" 2>"$OUT/err.log"
}

export LC_ALL=C
export LANG=C.UTF-8
mkdir -p "$OUT/reg_zh" "$OUT/reg_en"
reg_fixture "$OUT/reg_zh" schinese
reg_fixture "$OUT/reg_en" english

out=$(rpc "$OUT/reg_zh" --print-language --language auto)
[ "$out" = "zh-CN" ] || fail_msg "print-language auto zh: got '$out'"
out=$(rpc "$OUT/reg_zh" --print-language --language en)
[ "$out" = "en" ] || fail_msg "print-language forced en: got '$out'"

for want in en zh-CN; do
  lf="$OUT/cache_$want"
  rpc "$OUT/reg_en" --write-language-file "$lf" --language "$( [ "$want" = en ] && echo en || echo zh-CN )" >/dev/null || fail_msg "write-language-file $want failed"
  got=$(cat "$lf" 2>/dev/null)
  [ "$got" = "$want" ] || fail_msg "write-language-file $want content '$got'"
  perm=$(stat -c '%a' "$lf" 2>/dev/null)
  [ "$perm" = "644" ] || fail_msg "write-language-file $want perm '$perm'"
done

ref_en="$OUT/ref_en.ppm"; ref_zh="$OUT/ref_zh.ppm"
timeout 5 "$BIN" --backend ppm --font "$FONT" --status "$STATUS_FILE" --width $W --height $H --language en --out "$ref_en" >/dev/null 2>>"$OUT/err.log" || fail_msg "gen ref en"
timeout 5 "$BIN" --backend ppm --font "$FONT" --status "$STATUS_FILE" --width $W --height $H --language zh-CN --out "$ref_zh" >/dev/null 2>>"$OUT/err.log" || fail_msg "gen ref zh"
[ -s "$ref_en" ] || fail_msg "ref_en empty"
[ -s "$ref_zh" ] || fail_msg "ref_zh empty"
cmp -s "$ref_en" "$ref_zh" && fail_msg "ref_en and ref_zh are identical (blank output?) or reference PPMs do not differ"

cache_en="$OUT/cache_en"; cache_zh="$OUT/cache_zh"
printf 'en' > "$cache_en"; printf 'zh-CN' > "$cache_zh"
chmod 644 "$cache_en" "$cache_zh"

run_render() { # $1=regdir $2...args
  local r="$1"; shift
  HOME="$r" XDG_CONFIG_HOME="$r/cfg" ARMADA_SPLASH_STEAM_REGISTRY="$r/.steam/registry.vdf" timeout 5 "$BIN" --backend ppm --font "$FONT" --status "$STATUS_FILE" --width $W --height $H "$@" 2>>"$OUT/err.log"
}

cmpref() { # $1=label $2=got $3=want-ref
  if cmp -s "$2" "$3"; then :; else fail_msg "$1: PPM mismatch vs $(basename "$3")"; fi
}

# cache selects output under opposite registry
run_render "$OUT/reg_en" --language auto --language-file "$cache_zh" --out "$OUT/r1.ppm" || fail_msg "render cache zh"
cmpref "cache zh under en reg" "$OUT/r1.ppm" "$ref_zh"

run_render "$OUT/reg_zh" --language auto --language-file "$cache_en" --out "$OUT/r2.ppm" || fail_msg "render cache en"
cmpref "cache en under zh reg" "$OUT/r2.ppm" "$ref_en"

# forced override over opposite cache
run_render "$OUT/reg_zh" --language zh-CN --language-file "$cache_en" --out "$OUT/r3.ppm" || fail_msg "render forced zh"
cmpref "forced zh over en cache" "$OUT/r3.ppm" "$ref_zh"

run_render "$OUT/reg_en" --language en --language-file "$cache_zh" --out "$OUT/r4.ppm" || fail_msg "render forced en"
cmpref "forced en over zh cache" "$OUT/r4.ppm" "$ref_en"

# missing / invalid / fifo / symlink cache -> English, complete <3s
for kind in missing invalid invalid_newline fifo symlink; do
  lf="$OUT/c_$kind"
  case "$kind" in
    missing) rm -f "$lf" ;;
    invalid) printf 'xx' > "$lf" ;;
    invalid_newline) printf 'zh-CN\n\n' > "$lf" ;;
    fifo) rm -f "$lf"; mkfifo "$lf" ;;
    symlink) printf 'zh-CN' > "$OUT/target_$kind"; ln -sf "$OUT/target_$kind" "$lf" ;;
  esac
  t0=$(date +%s%N)
  HOME="$OUT/reg_zh" XDG_CONFIG_HOME="$OUT/reg_zh/cfg" ARMADA_SPLASH_STEAM_REGISTRY="$OUT/reg_zh/.steam/registry.vdf" timeout 3 "$BIN" --backend ppm --font "$FONT" --status "$STATUS_FILE" --width $W --height $H --language auto --language-file "$lf" --out "$OUT/rk_$kind.ppm" >/dev/null 2>>"$OUT/err.log"
  rc=$?
  t1=$(date +%s%N)
  ms=$(( (t1 - t0) / 1000000 ))
  if [ $rc -ne 0 ]; then fail_msg "cache $kind render rc=$rc"; fi
  if [ $ms -ge 3000 ]; then fail_msg "cache $kind took ${ms}ms"; fi
  cmpref "cache $kind -> en" "$OUT/rk_$kind.ppm" "$ref_en"
done

# no-registry-access: LD_PRELOAD open() blocker
BLOCKED="$OUT/reg_zh"
marker="$OUT/block_marker"
cat > "$OUT/block_open.c" <<'CEOF'
#define _GNU_SOURCE
#include <stdlib.h>
#include <dlfcn.h>
#include <stdarg.h>
#include <fcntl.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include <errno.h>
static int (*real_open)(const char*, int, ...) = 0;
static int (*real_openat)(int, const char*, int, ...) = 0;
int open(const char *p, int fl, ...) {
  mode_t m = 0;
  if (fl & O_CREAT) { va_list a; va_start(a, fl); m = va_arg(a, mode_t); va_end(a); }
  if (!real_open) real_open = dlsym(RTLD_NEXT, "open");
  const char *b = getenv("TEST_BLOCKED_REGISTRY");
  const char *mk = getenv("TEST_BLOCK_MARKER");
  if (b && strstr(p, b)) {
    if (mk) { FILE *f = fopen(mk, "a"); if (f) { fputs("hit\n", f); fclose(f); } }
    sleep(10); errno = EIO; return -1;
  }
  return real_open(p, fl, m);
}
int openat(int dfd, const char *p, int fl, ...) {
  mode_t m = 0;
  if (fl & O_CREAT) { va_list a; va_start(a, fl); m = va_arg(a, mode_t); va_end(a); }
  if (!real_openat) real_openat = dlsym(RTLD_NEXT, "openat");
  const char *b = getenv("TEST_BLOCKED_REGISTRY");
  const char *mk = getenv("TEST_BLOCK_MARKER");
  if (b && strstr(p, b)) {
    if (mk) { FILE *f = fopen(mk, "a"); if (f) { fputs("hit\n", f); fclose(f); } }
    sleep(10); errno = EIO; return -1;
  }
  return real_openat(dfd, p, fl, m);
}
CEOF

so="$OUT/block_open.so"
if cc -shared -fPIC -Wall -Wextra -Werror -o "$so" "$OUT/block_open.c" -ldl 2>"$OUT/cc.log"; then
  rm -f "$marker"
  HOME="$BLOCKED" XDG_CONFIG_HOME="$BLOCKED/cfg" ARMADA_SPLASH_STEAM_REGISTRY="$BLOCKED/.steam/registry.vdf" \
    TEST_BLOCKED_REGISTRY="$BLOCKED" TEST_BLOCK_MARKER="$marker" \
    LD_PRELOAD="$so" \
    timeout 3 "$BIN" --backend ppm --font "$FONT" --status "$STATUS_FILE" --width $W --height $H \
      --language auto --language-file "$cache_en" --out "$OUT/r_preload.ppm" \
      >/dev/null 2>>"$OUT/err.log"
  rc=$?
  [ $rc -eq 0 ] || fail_msg "preload render rc=$rc (possible registry access)"
  [ -f "$marker" ] && fail_msg "preload: registry was accessed ($(wc -l < "$marker") hits)"
  cmpref "preload en" "$OUT/r_preload.ppm" "$ref_en"
else
  fail_msg "preload compile failed; see $OUT/cc.log"
fi

if [ $fail -ne 0 ]; then echo "RESULT: FAIL (see $OUT)"; [ "$made_out" = 1 ] && rm -rf "$OUT"; exit 1; fi
echo "RESULT: PASS ($OUT)"
[ "$made_out" = 1 ] && rm -rf "$OUT"
exit 0
