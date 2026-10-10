// Regression harness for armada-splash font selection in load_font().
//
// It #includes the shipping armada-splash.c with main() renamed, so the code
// under test is the real load_font(), utf8_cps() and stb_truetype rasterization
// path -- not a reimplementation. stb_impl.c is linked in separately.
//
// Build:
//   cc -O2 -w -c src/stb_impl.c -o stb_impl.o
//   cc -O2 -Wall -Wextra -I src font-test.c stb_impl.o -ldrm -lm -o font-test
//
// Run one mode per process so each font starts from the pristine static state:
//   font-test cjk     <NotoSansCJK-Regular.ttc>
//   font-test latin   <NotoSansMono-SemiBold.ttf>
//   font-test missing <path-that-does-not-exist>
//
// Every mode prints per-check "ok"/"FAIL" lines and a final "<mode>: PASS|FAIL".

#define main armada_splash_main
#include "../src/armada-splash.c"
#undef main

#include <stdio.h>
#include <string.h>

static int g_fail = 0;

static void chk(int ok, const char *msg) {
    printf("  %s %s\n", ok ? "ok  " : "FAIL", msg);
    if (!ok) g_fail = 1;
}

static unsigned char *slurp(const char *path, long *size) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    long n = ftell(f);
    if (n <= 0 || fseek(f, 0, SEEK_SET) != 0) { fclose(f); return NULL; }
    unsigned char *buf = malloc((size_t)n);
    if (!buf) { fclose(f); return NULL; }
    size_t got = fread(buf, 1, (size_t)n, f);
    fclose(f);
    if (got != (size_t)n) { free(buf); return NULL; }
    *size = n;
    return buf;
}

// stbtt_GetFontNameString returns UTF-16BE for the Microsoft platform; compare
// only the ASCII prefix so a " Regular"-style suffix does not defeat the check.
static int utf16be_prefix(const char *s, int len, const char *want) {
    int wl = (int)strlen(want);
    if (len < wl * 2) return 0;
    for (int i = 0; i < wl; i++)
        if ((unsigned char)s[2 * i] != 0 || (unsigned char)s[2 * i + 1] != (unsigned char)want[i])
            return 0;
    return 1;
}

static int face_is_sc_mono(const stbtt_fontinfo *fi) {
    static const char *want = "Noto Sans Mono CJK SC";
    static const int ids[2] = { 1, 4 };   // family name, full name
    for (int i = 0; i < 2; i++) {
        int len = 0;
        const char *s;
        s = stbtt_GetFontNameString(fi, &len, STBTT_PLATFORM_ID_MICROSOFT,
                                    STBTT_MS_EID_UNICODE_BMP, STBTT_MS_LANG_ENGLISH, ids[i]);
        if (s && len > 0 && utf16be_prefix(s, len, want)) return 1;
        s = stbtt_GetFontNameString(fi, &len, STBTT_PLATFORM_ID_MICROSOFT,
                                    STBTT_MS_EID_UNICODE_FULL, STBTT_MS_LANG_ENGLISH, ids[i]);
        if (s && len > 0 && utf16be_prefix(s, len, want)) return 1;
        s = stbtt_GetFontNameString(fi, &len, STBTT_PLATFORM_ID_MAC, 0, 0, ids[i]);
        if (s && len >= (int)strlen(want) && strncmp(s, want, strlen(want)) == 0) return 1;
    }
    return 0;
}

static void check_common_font_metrics(void) {
    int ascent = 0, descent = 0, linegap = 0;
    stbtt_GetFontVMetrics(&g_ttf, &ascent, &descent, &linegap);
    chk(ascent > descent, "font exposes usable vertical metrics");
    chk(g_ttf_scale > 0.0f, "scale for the requested pixel height is positive");
}

// Renders every codepoint of "正在验证安装" through the real stb_truetype calls:
// each must map to a glyph, produce a nonempty inked bitmap, and the six
// bitmaps must be pairwise distinct.
static void check_status_glyphs(void) {
    static const char *status = "正在验证安装";
    uint32_t cps[64];
    int n = utf8_cps(status, cps, 64);
    chk(n >= 6, "status text decodes to >= 6 codepoints");

    unsigned long long sig[16];
    int nsig = 0, inked = 0, present = 0;
    for (int i = 0; i < n && i < 16; i++) {
        int gi = stbtt_FindGlyphIndex(&g_ttf, (int)cps[i]);
        if (gi != 0) present++;
        int w = 0, h = 0, xo = 0, yo = 0;
        unsigned char *bmp = stbtt_GetCodepointBitmap(&g_ttf, g_ttf_scale, g_ttf_scale,
                                                      (int)cps[i], &w, &h, &xo, &yo);
        if (bmp && w > 0 && h > 0) {
            unsigned long long s = 1469598103934665603ULL;
            long nz = 0;
            for (int k = 0; k < w * h; k++) {
                if (bmp[k]) nz++;
                s = (s ^ bmp[k]) * 1099511628211ULL;
            }
            if (nz > 0) inked++;
            sig[nsig++] = s;
            stbtt_FreeBitmap(bmp, NULL);
        }
    }
    chk(present == n, "every status codepoint maps to a glyph");
    chk(inked == n, "every status glyph bitmap carries ink");

    int distinct = nsig > 1;
    for (int i = 0; i < nsig && distinct; i++)
        for (int j = i + 1; j < nsig; j++)
            if (sig[i] == sig[j]) { distinct = 0; break; }
    chk(distinct, "status glyph bitmaps are pairwise distinct");
}

static void check_ascii_metrics(void) {
    static const char *sample = "Ag0";
    int all_adv = 1;
    for (const char *p = sample; *p; p++) {
        int adv = 0, lsb = 0;
        stbtt_GetCodepointHMetrics(&g_ttf, *p, &adv, &lsb);
        if (adv <= 0) all_adv = 0;
    }
    chk(all_adv, "ASCII codepoints have positive advances");

    uint32_t cp = 'A';
    chk(tt_text_w(&cp, 1) > 0, "production tt_text_w() measures ASCII text");
}

// End-to-end: drive the shipping tt_draw_centered()/tt_blit() path into a
// shadow buffer and confirm Chinese ink actually lands.
static void check_rasterizes_into_shadow(void) {
    SW = 720; SH = 220;
    shadow = malloc((size_t)SW * SH * 4);
    if (!shadow) { chk(0, "shadow buffer allocated"); return; }
    for (int i = 0; i < SW * SH; i++) shadow[i] = bg;
    tt_draw_centered("正在验证安装", 140, 0xFFFFFFFF);
    long painted = 0;
    for (int i = 0; i < SW * SH; i++)
        if (shadow[i] != bg) painted++;
    chk(painted > 0, "production tt_draw_centered() paints Chinese ink");
    printf("  info %ld pixels painted\n", painted);
    free(shadow); shadow = NULL;
}

static int run_cjk(const char *path) {
    long sz = 0;
    unsigned char *buf = slurp(path, &sz);
    chk(buf != NULL, "read the CJK collection");
    if (!buf) return g_fail;

    int faces = stbtt_GetNumberOfFonts(buf);
    int off0 = stbtt_GetFontOffsetForIndex(buf, 0);
    int off7 = stbtt_GetFontOffsetForIndex(buf, 7);
    printf("  info %s: %d faces, face0=%d face7=%d\n", path, faces, off0, off7);
    chk(faces > 7, "collection exposes at least 8 faces (index 7 exists)");
    chk(off0 >= 0 && off7 >= 0 && off0 != off7, "face 0 and face 7 have distinct offsets");

    chk(load_font(path, 32) == 1, "load_font() loads the collection");
    chk(g_ttf_ok == 1, "g_ttf_ok is set after a successful load");
    if (!g_ttf_ok) { free(buf); return g_fail; }

    printf("  info selected fontstart=%d (want face7=%d)\n", g_ttf.fontstart, off7);
    chk(g_ttf.fontstart == off7, "load_font() selects collection face 7, not face 0");
    chk(face_is_sc_mono(&g_ttf), "face 7 is named Noto Sans Mono CJK SC");

    check_common_font_metrics();
    check_status_glyphs();
    check_ascii_metrics();
    check_rasterizes_into_shadow();

    free(buf);
    return g_fail;
}

static int run_latin(const char *path) {
    long sz = 0;
    unsigned char *buf = slurp(path, &sz);
    chk(buf != NULL, "read the Latin font");
    if (!buf) return g_fail;

    int faces = stbtt_GetNumberOfFonts(buf);
    int off0 = stbtt_GetFontOffsetForIndex(buf, 0);
    printf("  info %s: %d faces, face0=%d\n", path, faces, off0);
    chk(faces == 1, "single-face .ttf reports one face");
    chk(off0 == 0, "single-face .ttf has its face at offset 0");

    chk(load_font(path, 32) == 1, "load_font() loads the Latin font");
    chk(g_ttf_ok == 1, "g_ttf_ok is set after a successful load");
    if (!g_ttf_ok) { free(buf); return g_fail; }
    chk(g_ttf.fontstart == off0, "load_font() uses face 0 for a single-face file");

    uint32_t cps[64];
    int n = utf8_cps("正在验证安装", cps, 64);
    int any = 0;
    for (int i = 0; i < n; i++)
        if (stbtt_FindGlyphIndex(&g_ttf, (int)cps[i]) != 0) any = 1;
    chk(!any, "Latin font has no glyphs for the Chinese status text");

    int ai = 0, al = 0, aw = 0, awl = 0;
    stbtt_GetCodepointHMetrics(&g_ttf, 'i', &ai, &al);
    stbtt_GetCodepointHMetrics(&g_ttf, 'W', &aw, &awl);
    chk(ai > 0 && ai == aw, "Latin mono font advances i and W equally");

    check_common_font_metrics();
    check_ascii_metrics();

    free(buf);
    return g_fail;
}

// Fresh process: nothing has loaded, so a missing font must leave the renderer
// in its "no font" state exactly as it does today.
static int run_missing(const char *path) {
    chk(load_font(path, 32) == 0, "load_font() returns 0 for a missing font");
    chk(g_ttf_ok == 0, "g_ttf_ok stays 0 after a missing font");
    chk(g_ttf_buf == NULL, "no font buffer is retained on failure");
    chk(load_font(NULL, 32) == 0, "load_font(NULL) returns 0");
    chk(load_font("", 32) == 0, "load_font(\"\") returns 0");
    return g_fail;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s {cjk|latin|missing} <font-path>\n", argv[0]);
        return 2;
    }
    int rc;
    if (!strcmp(argv[1], "cjk")) rc = run_cjk(argv[2]);
    else if (!strcmp(argv[1], "latin")) rc = run_latin(argv[2]);
    else if (!strcmp(argv[1], "missing")) rc = run_missing(argv[2]);
    else { fprintf(stderr, "unknown mode %s\n", argv[1]); return 2; }

    printf("%s: %s\n", argv[1], rc == 0 ? "PASS" : "FAIL");
    return rc;
}
