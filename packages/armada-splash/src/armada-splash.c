// Boot splash: centers an image with status text below it, from a status file.
// fbdev backend for early boot (never touches the GPU); x11 backend for the
// gamescope phase (gamescope shows it via the fallback-appid patch, yields to
// Steam); drm backend renders the primary connector only (panel-native mode,
// other CRTCs off) and falls back to fbdev. Auto: x11 if DISPLAY, else fbdev.
//
// Image = "ASP1" container: "ASP1" | u32 width LE | u32 height LE | W*H*4 BGRA.
// Status file: one line per row centered below the image; leading '!' = red.

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/kd.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/timerfd.h>
#include <unistd.h>

#include "font8x8_basic.h"
#include "stb_truetype.h"   // declarations only; implementation in stb_impl.c

static volatile sig_atomic_t running = 1;
static void on_signal(int s) { (void)s; running = 0; }
// No SA_RESTART: a TERM must interrupt blocked syscalls, not restart them.
static void install_signal(int sig) {
    struct sigaction sa = { 0 };
    sa.sa_handler = on_signal;
    sigemptyset(&sa.sa_mask);
    sigaction(sig, &sa, NULL);
}

// For fbdev 90/270 rotation, SW/SH are the panel dimensions swapped.
static int SW, SH;
static uint32_t *shadow;      // SW*SH ARGB8888
static uint32_t bg = 0xFF000000;
static const float splash_rgb_gain = 0.5f;

static uint32_t *img;
static int img_w, img_h;

static int text_scale = 2;

static char g_cur[512];
static char g_shown[512];

static void put_shadow(int x, int y, uint32_t c) {
    if (x >= 0 && x < SW && y >= 0 && y < SH) shadow[y * SW + x] = c;
}

static void draw_glyph(int ch, int px, int py, int s, uint32_t color) {
    if (ch < 0 || ch > 127) ch = '?';
    const char *g = font8x8_basic[ch];
    for (int row = 0; row < 8; row++)
        for (int col = 0; col < 8; col++)
            if (g[row] & (1 << col))
                for (int dy = 0; dy < s; dy++)
                    for (int dx = 0; dx < s; dx++)
                        put_shadow(px + col * s + dx, py + row * s + dy, color);
}

// Steam localizes its updater lines: status text is UTF-8, not ASCII, and
// byte-wise rendering draws it as Latin-1 mojibake. Invalid bytes -> U+FFFD.
static int utf8_cps(const char *s, uint32_t *out, int max) {
    const unsigned char *p = (const unsigned char *)s;
    int n = 0;
    while (*p && n < max) {
        uint32_t cp = 0xFFFD;
        if (*p < 0x80) { cp = *p; p += 1; }
        else if ((*p & 0xE0) == 0xC0 && (p[1] & 0xC0) == 0x80) {
            cp = (uint32_t)(*p & 0x1F) << 6 | (p[1] & 0x3F); p += 2;
        } else if ((*p & 0xF0) == 0xE0 && (p[1] & 0xC0) == 0x80 && (p[2] & 0xC0) == 0x80) {
            cp = (uint32_t)(*p & 0x0F) << 12 | (uint32_t)(p[1] & 0x3F) << 6 | (p[2] & 0x3F); p += 3;
        } else if ((*p & 0xF8) == 0xF0 && (p[1] & 0xC0) == 0x80 && (p[2] & 0xC0) == 0x80 && (p[3] & 0xC0) == 0x80) {
            cp = (uint32_t)(*p & 0x07) << 18 | (uint32_t)(p[1] & 0x3F) << 12 |
                 (uint32_t)(p[2] & 0x3F) << 6 | (p[3] & 0x3F); p += 4;
        } else p += 1;
        out[n++] = cp;
    }
    return n;
}

static void draw_text_centered(const char *s, int y, int scale, uint32_t color) {
    uint32_t cps[512];
    int n = utf8_cps(s, cps, 512);
    int x = (SW - n * 8 * scale) / 2;
    if (x < 0) x = 0;
    for (int i = 0; i < n; i++) {
        draw_glyph((int)cps[i], x, y, scale, color);
        x += 8 * scale;
    }
}

static stbtt_fontinfo g_ttf;
static unsigned char *g_ttf_buf;
static int g_ttf_ok = 0;
static float g_ttf_scale;
static int g_ttf_ascent, g_ttf_descent, g_ttf_linegap;
static int g_text_px = 32;
static int g_text_px_req = 0; // --text-height (0 = auto from short axis)
static int g_gap = -1;   // px between image and text; <0 = auto (1.6x text height)
static int g_layout = 0; // 0 = centered group, 1 = logo centered + text bottom
static int g_logo_dx = 0;     // --logo-offset-x, negative = left
static uint32_t g_appid = 0x41524D41u; // STEAM_GAME appid; match GAMESCOPE_FALLBACK_APPID

// Layout is authored against a 1080px short axis and scales from it.
static int auto_text_px(int ref) { return ref * 55 / 1080; }
// 377 = the asset's own height, i.e. the logo at design scale.
static int auto_logo_px(int ref) { return ref * 377 / 1080; }
// Box to box, not ink to ink: the logo and the text line both carry padding.
static int auto_gap_px(int ref) { return ref * 50 / 1080; }

static inline void blend_shadow(int x, int y, uint32_t color, int cov) {
    if (cov <= 0 || x < 0 || x >= SW || y < 0 || y >= SH) return;
    if (cov > 255) cov = 255;
    uint32_t d = shadow[y * SW + x];
    int sr = (color >> 16) & 255, sg = (color >> 8) & 255, sb = color & 255;
    int dr = (d >> 16) & 255, dg = (d >> 8) & 255, db = d & 255;
    shadow[y * SW + x] = 0xFF000000 |
        (((sr * cov + dr * (255 - cov)) / 255) << 16) |
        (((sg * cov + dg * (255 - cov)) / 255) << 8) |
        ((sb * cov + db * (255 - cov)) / 255);
}

static int load_font(const char *path, int px) {
    if (!path || !*path) return 0;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return 0;
    struct stat st;
    if (fstat(fd, &st) != 0 || st.st_size <= 0) { close(fd); return 0; }
    g_ttf_buf = malloc(st.st_size);
    if (!g_ttf_buf) { close(fd); return 0; }
    size_t off = 0; ssize_t r;
    while (off < (size_t)st.st_size && (r = read(fd, g_ttf_buf + off, st.st_size - off)) > 0) off += r;
    close(fd);
    if (off != (size_t)st.st_size ||
        !stbtt_InitFont(&g_ttf, g_ttf_buf, stbtt_GetFontOffsetForIndex(g_ttf_buf, 0))) {
        free(g_ttf_buf); g_ttf_buf = NULL; return 0;
    }
    g_ttf_scale = stbtt_ScaleForPixelHeight(&g_ttf, (float)px);
    stbtt_GetFontVMetrics(&g_ttf, &g_ttf_ascent, &g_ttf_descent, &g_ttf_linegap);
    g_text_px = px;
    return (g_ttf_ok = 1);
}

static int tt_text_w(const uint32_t *cp, int n) {
    float w = 0;
    for (int i = 0; i < n; i++) {
        int adv, lsb;
        stbtt_GetCodepointHMetrics(&g_ttf, (int)cp[i], &adv, &lsb);
        w += adv * g_ttf_scale;
        if (i + 1 < n) w += stbtt_GetCodepointKernAdvance(&g_ttf, (int)cp[i], (int)cp[i + 1]) * g_ttf_scale;
    }
    return (int)(w + 0.5f);
}

static void tt_blit(const uint32_t *cp, int n, float x, int baseline, uint32_t color, int num, int den) {
    for (int k = 0; k < n; k++) {
        int c = (int)cp[k], ix0, iy0, ix1, iy1;
        stbtt_GetCodepointBitmapBox(&g_ttf, c, g_ttf_scale, g_ttf_scale, &ix0, &iy0, &ix1, &iy1);
        int gw = ix1 - ix0, gh = iy1 - iy0;
        if (gw > 0 && gh > 0) {
            unsigned char *bmp = malloc((size_t)gw * gh);
            if (bmp) {
                stbtt_MakeCodepointBitmap(&g_ttf, bmp, gw, gh, gw, g_ttf_scale, g_ttf_scale, c);
                int gx = (int)(x + 0.5f) + ix0, gy = baseline + iy0;
                for (int j = 0; j < gh; j++)
                    for (int i = 0; i < gw; i++)
                        blend_shadow(gx + i, gy + j, color, bmp[j * gw + i] * num / den);
                free(bmp);
            }
        }
        int adv, lsb;
        stbtt_GetCodepointHMetrics(&g_ttf, c, &adv, &lsb);
        x += adv * g_ttf_scale;
        if (k + 1 < n) x += stbtt_GetCodepointKernAdvance(&g_ttf, c, (int)cp[k + 1]) * g_ttf_scale;
    }
}

static void tt_draw_centered(const char *s, int baseline, uint32_t color) {
    uint32_t cps[512];
    int n = utf8_cps(s, cps, 512);
    int x = (SW - tt_text_w(cps, n)) / 2; if (x < 0) x = 0;
    int sh = g_text_px / 20; if (sh < 1) sh = 1;
    tt_blit(cps, n, x + sh, baseline + sh, 0xFF000000, 150, 255);   // soft drop shadow
    tt_blit(cps, n, x, baseline, color, 255, 255);                  // text
}

#define MAX_LINES 8

static char g_lines[MAX_LINES][256];
static uint32_t g_linecol[MAX_LINES];

static int measure(const char *s, int len) {
    char tmp[256];
    if (len > (int)sizeof tmp - 1) len = (int)sizeof tmp - 1;
    memcpy(tmp, s, len); tmp[len] = 0;
    uint32_t cps[256];
    int n = utf8_cps(tmp, cps, 256);
    return g_ttf_ok ? tt_text_w(cps, n) : n * 8 * text_scale;
}

static int emit(int n, const char *s, int len, uint32_t col) {
    if (n >= MAX_LINES) return n;
    snprintf(g_lines[n], sizeof g_lines[n], "%.*s", len, s);
    g_linecol[n] = col;
    return n + 1;
}

// Unwrapped, an overlong line draws from a clamped x=0 and runs off both edges.
static int wrap(char *p, uint32_t col, int maxw, int n) {
    while (*p && n < MAX_LINES) {
        int len = (int)strlen(p);
        if (measure(p, len) <= maxw) return emit(n, p, len, col);
        int brk = -1;
        for (int i = 0; p[i]; i++)
            if (p[i] == ' ') {
                if (measure(p, i) <= maxw) brk = i;
                else break;
            }
        if (brk < 0) {
            // No break point fits: split mid-word, on a codepoint boundary.
            int i = 1;
            while (p[i] && measure(p, i + 1) <= maxw) i++;
            while (i > 1 && ((unsigned char)p[i] & 0xC0) == 0x80) i--;
            n = emit(n, p, i, col);
            p += i;
        } else {
            n = emit(n, p, brk, col);
            p += brk + 1;          // the break space is not drawn
        }
    }
    return n;
}

static void compose(const char *status) {
    for (int i = 0; i < SW * SH; i++) shadow[i] = bg;

    char buf[512];
    snprintf(buf, sizeof buf, "%s", status ? status : "");
    // SW is post-rotation width; full width reads as a paragraph.
    int maxw = SW / 2;
    int n = 0;
    for (char *p = buf; *p && n < MAX_LINES; ) {
        char *nl = strchr(p, '\n');
        if (nl) *nl = 0;
        if (*p) {
            uint32_t col = 0xFFFFFFFF;
            if (*p == '!') { col = 0xFFFF4040; p++; }
            n = wrap(p, col, maxw, n);
        }
        if (!nl) break;
        p = nl + 1;
    }

    int line_h, ascent_px = 0;
    if (g_ttf_ok) {
        line_h = (int)((g_ttf_ascent - g_ttf_descent + g_ttf_linegap) * g_ttf_scale + 0.5f);
        ascent_px = (int)(g_ttf_ascent * g_ttf_scale + 0.5f);
    } else {
        line_h = 8 * text_scale + text_scale;
    }
    int text_block_h = n * line_h;
    int ref = SW < SH ? SW : SH;
    int logo_x = (SW - img_w) / 2 + g_logo_dx;
    int logo_y, text_top;

    if (g_layout == 1) {
        // split layout: --gap is the bottom margin.
        logo_y = (SH - img_h) / 2;
        int margin = g_gap >= 0 ? g_gap : g_text_px;
        text_top = SH - margin - text_block_h;
    } else {
        int gap = img_h ? (g_gap >= 0 ? g_gap : (g_ttf_ok ? auto_gap_px(ref) : 13 * text_scale)) : 0;
        // Reserve one line always: sizing to the live count jumps the logo.
        int group_h = (img_h ? img_h + gap : 0) + line_h;
        logo_y = (SH - group_h) / 2;
        text_top = logo_y + (img_h ? img_h + gap : 0);
    }
    if (logo_y < 0) logo_y = 0;
    if (text_top < 0) text_top = 0;

    if (img && img_w && img_h)
        for (int y = 0; y < img_h; y++)
            for (int x = 0; x < img_w; x++)
                put_shadow(logo_x + x, logo_y + y, img[y * img_w + x]);

    int ty = text_top;
    for (int i = 0; i < n; i++) {
        if (g_ttf_ok) tt_draw_centered(g_lines[i], ty + ascent_px, g_linecol[i]);
        else draw_text_centered(g_lines[i], ty, text_scale, g_linecol[i]);
        ty += line_h;
    }

    for (int i = 0; i < SW * SH; i++) {
        uint32_t pixel = shadow[i];
        uint32_t r = ((pixel >> 16) & 255) * splash_rgb_gain + 0.5f;
        uint32_t g = ((pixel >> 8) & 255) * splash_rgb_gain + 0.5f;
        uint32_t b = (pixel & 255) * splash_rgb_gain + 0.5f;
        shadow[i] = (pixel & 0xFF000000) | (r << 16) | (g << 8) | b;
    }
}

static int load_image(const char *path) {
    if (!path || !*path) return 0;
    int fd = open(path, O_RDONLY);
    if (fd < 0) { fprintf(stderr, "armada-splash: cannot open %s\n", path); return 0; }
    uint8_t hdr[12];
    if (read(fd, hdr, 12) != 12 || memcmp(hdr, "ASP1", 4) != 0) {
        fprintf(stderr, "armada-splash: %s is not an ASP1 image\n", path);
        close(fd); return 0;
    }
    img_w = hdr[4] | hdr[5] << 8 | hdr[6] << 16 | (uint32_t)hdr[7] << 24;
    img_h = hdr[8] | hdr[9] << 8 | hdr[10] << 16 | (uint32_t)hdr[11] << 24;
    if (img_w <= 0 || img_h <= 0 || img_w > 8192 || img_h > 8192) {
        fprintf(stderr, "armada-splash: bad image dims %dx%d\n", img_w, img_h);
        img_w = img_h = 0; close(fd); return 0;
    }
    size_t sz = (size_t)img_w * img_h * 4;
    img = malloc(sz);
    if (!img) { img_w = img_h = 0; close(fd); return 0; }
    size_t off = 0; ssize_t r;
    while (off < sz && (r = read(fd, (uint8_t *)img + off, sz - off)) > 0) off += r;
    close(fd);
    if (off != sz) {
        fprintf(stderr, "armada-splash: short image\n");
        free(img); img = NULL; img_w = img_h = 0; return 0;
    }
    return 1;
}

// Bilinear-scale the logo from the untouched original so a compositor resize
// re-derives the size without compounding quality loss.
static uint32_t *img_src;
static int img_src_w, img_src_h;
static int g_logo_px_req = 0;   // --logo-height (0 = auto from short axis)

static void scale_logo(int th) {
    if (!img_src || th <= 0 || (img && th == img_h)) return;
    if (th == img_src_h) {
        if (img != img_src) free(img);
        img = img_src; img_w = img_src_w; img_h = img_src_h;
        return;
    }
    int tw = (int)((long long)img_src_w * th / img_src_h); if (tw < 1) tw = 1;
    uint32_t *ni = malloc((size_t)tw * th * 4);
    if (!ni) return;
    for (int y = 0; y < th; y++) {
        float sy = (y + 0.5f) * img_src_h / th - 0.5f;
        int y0 = (int)floorf(sy); float fy = sy - y0;
        int y1 = y0 + 1;
        if (y0 < 0) y0 = 0;
        if (y1 >= img_src_h) y1 = img_src_h - 1;
        for (int x = 0; x < tw; x++) {
            float sx = (x + 0.5f) * img_src_w / tw - 0.5f;
            int x0 = (int)floorf(sx); float fx = sx - x0;
            int x1 = x0 + 1;
            if (x0 < 0) x0 = 0;
            if (x1 >= img_src_w) x1 = img_src_w - 1;
            uint32_t c00 = img_src[y0 * img_src_w + x0], c01 = img_src[y0 * img_src_w + x1];
            uint32_t c10 = img_src[y1 * img_src_w + x0], c11 = img_src[y1 * img_src_w + x1];
            uint32_t out = 0xFF000000;
            for (int s = 0; s < 24; s += 8) {
                float v = ((c00 >> s & 255) * (1 - fx) + (c01 >> s & 255) * fx) * (1 - fy)
                        + ((c10 >> s & 255) * (1 - fx) + (c11 >> s & 255) * fx) * fy;
                out |= (uint32_t)(v + 0.5f) << s;
            }
            ni[y * tw + x] = out;
        }
    }
    if (img != img_src) free(img);
    img = ni; img_w = tw; img_h = th;
}

// Poll the whole file each call (not mtime) so same-second updates are caught.
// The dir is user-writable and this can run as root: regular files only.
static void read_status(const char *path, char *out, size_t n) {
    out[0] = 0;
    if (!path) return;
    int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return;
    struct stat st;
    if (fstat(fd, &st) != 0 || !S_ISREG(st.st_mode)) { close(fd); return; }
    ssize_t r = read(fd, out, n - 1);
    close(fd);
    out[r < 0 ? 0 : r] = 0;
}

// ================= fbdev backend =================

struct fbdev {
    int fd;
    int fbw, fbh, bpp, stride, angle;
    int roff, rlen, goff, glen, boff, blen;
};
static struct fbdev fbd;
static int keep_vt = 0;   // hand off KD_GRAPHICS to the next instance instead of restoring
static int g_ttyfd = -1, g_prev_kd;

static void vt_restore(void) {
    if (g_ttyfd < 0) return;
    // On handoff, leave KD_GRAPHICS so fbcon does not repaint before the next owner.
    if (!keep_vt) ioctl(g_ttyfd, KDSETMODE, g_prev_kd);
    close(g_ttyfd); g_ttyfd = -1;
}

// KD_GRAPHICS suppresses fbcon: in KD_TEXT a console write (kernel error
// printk passes loglevel=3) hands the scanout to kernel fbdev whenever no
// DRM master holds it. Arm the restore only if both ioctls succeed.
static void vt_graphics(void) {
    g_ttyfd = open("/dev/tty0", O_RDWR);
    if (g_ttyfd < 0) return;
    if (ioctl(g_ttyfd, KDGETMODE, &g_prev_kd) == 0 &&
        ioctl(g_ttyfd, KDSETMODE, KD_GRAPHICS) == 0) {
        atexit(vt_restore);
    } else {
        close(g_ttyfd); g_ttyfd = -1;
    }
}

static int fb_open(const char *dev, int angle) {
    fbd.fd = open(dev, O_RDWR);
    if (fbd.fd < 0) { fprintf(stderr, "armada-splash: open %s: %s\n", dev, strerror(errno)); return 0; }
    struct fb_var_screeninfo v; struct fb_fix_screeninfo f;
    if (ioctl(fbd.fd, FBIOGET_VSCREENINFO, &v) || ioctl(fbd.fd, FBIOGET_FSCREENINFO, &f)) {
        fprintf(stderr, "armada-splash: FBIOGET_*SCREENINFO failed\n"); return 0;
    }
    fbd.fbw = v.xres; fbd.fbh = v.yres; fbd.bpp = v.bits_per_pixel;
    fbd.stride = f.line_length;              // NEVER xres*bpp/8
    fbd.roff = v.red.offset;   fbd.rlen = v.red.length;
    fbd.goff = v.green.offset; fbd.glen = v.green.length;
    fbd.boff = v.blue.offset;  fbd.blen = v.blue.length;
    fbd.angle = angle;
    if (fbd.rlen == 0) { fbd.roff = 16; fbd.rlen = 8; fbd.goff = 8; fbd.glen = 8; fbd.boff = 0; fbd.blen = 8; }

    if (fbd.bpp < 16 || fbd.bpp > 32 || fbd.bpp % 8 != 0) {
        fprintf(stderr, "armada-splash: unsupported bpp %d (need byte-aligned 16..32)\n", fbd.bpp);
        return 0;
    }
    if (fbd.stride < fbd.fbw * (fbd.bpp / 8) ||
        (size_t)fbd.stride * fbd.fbh > (size_t)f.smem_len) {
        fprintf(stderr, "armada-splash: fb geometry exceeds smem_len\n"); return 0;
    }

    // After a compositor exits the fbdev may be FB_BLANK_POWERDOWN; unblank or
    // writes land in memory that is not scanned out.
    ioctl(fbd.fd, FBIOBLANK, FB_BLANK_UNBLANK);

    vt_graphics();

    if (angle == 90 || angle == 270) { SW = fbd.fbh; SH = fbd.fbw; }
    else { SW = fbd.fbw; SH = fbd.fbh; }
    return 1;
}

// Shift left for len > 8; `c >> (8 - len)` would be UB there.
static inline uint32_t fb_chan(uint32_t c8, int len, int off) {
    if (len <= 0) return 0;
    uint32_t v = len >= 8 ? (c8 << (len - 8)) : (c8 >> (8 - len));
    return v << off;
}
static inline uint32_t fb_pack(uint32_t argb) {
    return fb_chan((argb >> 16) & 0xff, fbd.rlen, fbd.roff) |
           fb_chan((argb >> 8) & 0xff, fbd.glen, fbd.goff) |
           fb_chan(argb & 0xff, fbd.blen, fbd.boff);
}

// drm/msm fbdev emulation backs an mmap with a shadow buffer whose damage
// never reaches scanout; pwrite always flushes.
static void fb_present(void) {
    int Bpp = fbd.bpp >> 3;
    uint8_t *row = malloc((size_t)fbd.fbw * Bpp);
    if (!row) return;
    for (int py = 0; py < fbd.fbh; py++) {
        for (int px = 0; px < fbd.fbw; px++) {
            int lx, ly;
            switch (fbd.angle) {
                case 90:  ly = fbd.fbw - 1 - px; lx = py; break;
                case 180: lx = fbd.fbw - 1 - px; ly = fbd.fbh - 1 - py; break;
                case 270: ly = px; lx = fbd.fbh - 1 - py; break;
                default:  lx = px; ly = py; break;
            }
            uint32_t v = (lx >= 0 && lx < SW && ly >= 0 && ly < SH)
                       ? fb_pack(shadow[ly * SW + lx]) : fb_pack(0xFF000000);
            for (int k = 0; k < Bpp; k++) row[px * Bpp + k] = (v >> (k * 8)) & 0xff;
        }
        if (pwrite(fbd.fd, row, (size_t)fbd.fbw * Bpp, (off_t)py * fbd.stride) < 0) break;
    }
    free(row);
}

// ================= drm backend =================
// Per-connector KMS: a dumb buffer sized to the primary panel's own mode,
// other CRTCs off -- no fbdev clone, no first-bind geometry race.
#include <xf86drm.h>
#include <xf86drmMode.h>

struct drmb {
    int fd, angle, crtc_on, dirty_ok, setcrtc_logged;
    uint32_t crtc_id, conn_id, fb_id;
    uint32_t pitch, w, h;
    uint8_t *map;
    size_t map_sz;
    drmModeModeInfo mode;
    drmModeRes *res;
};
static struct drmb db;

static const char *conn_type_name(uint32_t t) {
    switch (t) {
        case DRM_MODE_CONNECTOR_DSI: return "DSI";
        case DRM_MODE_CONNECTOR_eDP: return "eDP";
        case DRM_MODE_CONNECTOR_DisplayPort: return "DP";
        case DRM_MODE_CONNECTOR_HDMIA: return "HDMI-A";
        default: return "OUT";
    }
}

static int drm_open(const char *want, int angle) {
    char dev[32];
    db.fd = -1;
    drmModeRes *res = NULL;
    for (int card = 0; card < 3; card++) {
        snprintf(dev, sizeof dev, "/dev/dri/card%d", card);
        db.fd = open(dev, O_RDWR | O_CLOEXEC);
        if (db.fd < 0) continue;
        if ((res = drmModeGetResources(db.fd))) break;
        close(db.fd); db.fd = -1;
    }
    if (!res) { fprintf(stderr, "armada-splash: no KMS device\n"); return 0; }

    drmModeConnector *conn = NULL;
    for (int i = 0; i < res->count_connectors; i++) {
        drmModeConnector *c = drmModeGetConnector(db.fd, res->connectors[i]);
        if (!c) continue;
        char name[32];
        snprintf(name, sizeof name, "%s-%u", conn_type_name(c->connector_type), c->connector_type_id);
        if (c->connection == DRM_MODE_CONNECTED && c->count_modes > 0 &&
            (!want || !*want || !strcmp(name, want))) { conn = c; break; }
        drmModeFreeConnector(c);
    }
    if (!conn) { fprintf(stderr, "armada-splash: connector %s not found\n", want ? want : "(any)"); return 0; }
    db.conn_id = conn->connector_id;
    db.mode = conn->modes[0];
    for (int i = 0; i < conn->count_modes; i++)
        if (conn->modes[i].type & DRM_MODE_TYPE_PREFERRED) { db.mode = conn->modes[i]; break; }

    uint32_t possible = 0;
    if (conn->count_encoders > 0) {
        drmModeEncoder *e = drmModeGetEncoder(db.fd, conn->encoders[0]);
        if (e) { possible = e->possible_crtcs; drmModeFreeEncoder(e); }
    }
    db.crtc_id = 0;
    for (int i = 0; i < res->count_crtcs; i++)
        if (!possible || (possible & (1u << i))) { db.crtc_id = res->crtcs[i]; break; }
    drmModeFreeConnector(conn);
    if (!db.crtc_id) { fprintf(stderr, "armada-splash: no CRTC\n"); return 0; }

    db.w = db.mode.hdisplay; db.h = db.mode.vdisplay;
    struct drm_mode_create_dumb cd = { .width = db.w, .height = db.h, .bpp = 32 };
    if (drmIoctl(db.fd, DRM_IOCTL_MODE_CREATE_DUMB, &cd)) {
        fprintf(stderr, "armada-splash: CREATE_DUMB failed\n"); return 0;
    }
    db.pitch = cd.pitch; db.map_sz = cd.size;
    if (drmModeAddFB(db.fd, db.w, db.h, 24, 32, db.pitch, cd.handle, &db.fb_id)) {
        fprintf(stderr, "armada-splash: AddFB failed\n"); return 0;
    }
    struct drm_mode_map_dumb md = { .handle = cd.handle };
    if (drmIoctl(db.fd, DRM_IOCTL_MODE_MAP_DUMB, &md)) return 0;
    db.map = mmap(NULL, db.map_sz, PROT_READ | PROT_WRITE, MAP_SHARED, db.fd, md.offset);
    if (db.map == MAP_FAILED) { db.map = NULL; return 0; }
    memset(db.map, 0, db.map_sz);
    // The modeset happens in the first present: command-mode panels push one
    // frame per commit, and it must not be this still-black buffer.
    db.res = res;
    db.dirty_ok = 1;

    db.angle = angle;
    if (angle == 90 || angle == 270) { SW = db.h; SH = db.w; }
    else { SW = db.w; SH = db.h; }
    return 1;
}

static void drm_present(void) {
    if (!db.map) return;
    for (uint32_t py = 0; py < db.h; py++) {
        uint32_t *row = (uint32_t *)(db.map + (size_t)py * db.pitch);
        for (uint32_t px = 0; px < db.w; px++) {
            int lx, ly;
            switch (db.angle) {
                case 90:  ly = (int)db.w - 1 - (int)px; lx = (int)py; break;
                case 180: lx = (int)db.w - 1 - (int)px; ly = (int)db.h - 1 - (int)py; break;
                case 270: ly = (int)px; lx = (int)db.h - 1 - (int)py; break;
                default:  lx = (int)px; ly = (int)py; break;
            }
            row[px] = (lx >= 0 && lx < SW && ly >= 0 && ly < SH)
                    ? shadow[ly * SW + lx] : 0xFF000000u;
        }
    }
    // Command-mode panels show one frame per commit; buffer writes alone
    // never reach glass. The master is HELD while this drawer owns the
    // screen: masterless, kernel fbdev steals the scanout on any fb0 write.
    if (!db.crtc_on) {
        drmSetMaster(db.fd);   // explicit: a predecessor may just have yielded
        if (drmModeSetCrtc(db.fd, db.crtc_id, db.fb_id, 0, 0, &db.conn_id, 1, &db.mode)) {
            if (!db.setcrtc_logged) {
                db.setcrtc_logged = 1;
                fprintf(stderr, "armada-splash: SetCrtc: %s (retrying)\n", strerror(errno));
            }
            return;            // predecessor still holds; retried next tick
        }
        fprintf(stderr, "armada-splash: drm modeset ok %ux%u conn=%u crtc=%u pid=%d\n",
                db.w, db.h, db.conn_id, db.crtc_id, (int)getpid());
        for (int i = 0; i < db.res->count_crtcs; i++)
            if (db.res->crtcs[i] != db.crtc_id)
                drmModeSetCrtc(db.fd, db.res->crtcs[i], 0, 0, 0, NULL, 0, NULL);
        db.crtc_on = 1;
        return;
    }
    if (db.dirty_ok && drmModeDirtyFB(db.fd, db.fb_id, NULL, 0) != 0) {
        db.dirty_ok = 0;
        fprintf(stderr, "armada-splash: DirtyFB unsupported; re-modesetting per update\n");
    }
    if (!db.dirty_ok)
        drmModeSetCrtc(db.fd, db.crtc_id, db.fb_id, 0, 0, &db.conn_id, 1, &db.mode);
}

// ================= x11 backend (Xwayland under gamescope) =================
// gamescope's steam mode shows only X11 windows via its appid focus machinery.
// STEAM_GAME = g_appid opts this window into the fallback-appid patch; set
// GAMESCOPE_FALLBACK_APPID to the same value.
#ifdef HAVE_X11
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/Xutil.h>

static Display *x_dpy;
static Window x_win;
static GC x_gc;
static XImage *x_img;
static Atom a_focused_win;
static int g_was_shown;

// g_was_shown guards the startup ordering where the focus atom names this
// window before it is mapped, so a later focus change means real displacement.
static void x11_check_focus(void) {
    Atom type; int fmt; unsigned long n, after; unsigned char *data = NULL;
    unsigned long val = 0;
    if (XGetWindowProperty(x_dpy, DefaultRootWindow(x_dpy), a_focused_win, 0, 1,
                           False, AnyPropertyType, &type, &fmt, &n, &after,
                           &data) == Success && data) {
        if (n && fmt == 32) val = *(unsigned long *)data;
        XFree(data);
    }
    if (val == (unsigned long)x_win) g_was_shown = 1;
    // Zero/absent = transient focus clear, not displacement.
    else if (g_was_shown && val != 0) { fprintf(stderr, "armada-splash: displaced; exiting\n"); running = 0; }
}

static int x11_init(void) {
    if (!x_dpy) x_dpy = XOpenDisplay(NULL);   // may already be open (sized in main)
    if (!x_dpy) { fprintf(stderr, "armada-splash: cannot open X display\n"); return 0; }
    int scr = DefaultScreen(x_dpy);
    XSetWindowAttributes a = { 0 };
    a.background_pixel = BlackPixel(x_dpy, scr);
    x_win = XCreateWindow(x_dpy, RootWindow(x_dpy, scr), 0, 0, SW, SH, 0,
                          DefaultDepth(x_dpy, scr), InputOutput,
                          DefaultVisual(x_dpy, scr), CWBackPixel, &a);
    // Xlib format-32 properties marshal from an array of long, not uint32_t.
    unsigned long appid_l = g_appid;
    XChangeProperty(x_dpy, x_win, XInternAtom(x_dpy, "STEAM_GAME", False),
                    XA_CARDINAL, 32, PropModeReplace, (unsigned char *)&appid_l, 1);
    XStoreName(x_dpy, x_win, "armada-splash");
    XSelectInput(x_dpy, x_win, ExposureMask | StructureNotifyMask);
    // Keep controller mouse emulation invisible until Steam takes over.
    static const char blank_bits[] = { 0 };
    Pixmap blank = XCreateBitmapFromData(x_dpy, x_win, blank_bits, 1, 1);
    if (blank) {
        XColor color = { 0 };
        Cursor cursor = XCreatePixmapCursor(x_dpy, blank, blank, &color, &color, 0, 0);
        if (cursor) {
            XDefineCursor(x_dpy, x_win, cursor);
            XFreeCursor(x_dpy, cursor);
        }
        XFreePixmap(x_dpy, blank);
    }
    // gamescope's DISPLAY focus; X input focus ping-pongs to Steam's invisible
    // windows during bring-up and is useless for takeover detection.
    a_focused_win = XInternAtom(x_dpy, "GAMESCOPE_FOCUSED_WINDOW", False);
    XSelectInput(x_dpy, RootWindow(x_dpy, scr), PropertyChangeMask);
    XMapWindow(x_dpy, x_win);
    x_gc = XCreateGC(x_dpy, x_win, 0, NULL);
    // shadow is ARGB8888, i.e. X 24/32-bit TrueColor LSBFirst; use it directly.
    x_img = XCreateImage(x_dpy, DefaultVisual(x_dpy, scr), DefaultDepth(x_dpy, scr),
                         ZPixmap, 0, (char *)shadow, SW, SH, 32, SW * 4);
    if (!x_img) { fprintf(stderr, "armada-splash: XCreateImage failed\n"); return 0; }
    x_img->byte_order = LSBFirst;
    XFlush(x_dpy);
    x11_check_focus();
    return 1;
}

static void x11_present(void) {
    if (!x_img) return;
    XPutImage(x_dpy, x_win, x_gc, x_img, 0, 0, 0, 0, SW, SH);
    XFlush(x_dpy);
}

// Adapt to gamescope resizing the window (per-panel resolution/orientation).
static void x11_resize(int w, int h) {
    if (w <= 0 || h <= 0 || (w == SW && h == SH)) return;
    uint32_t *ns = realloc(shadow, (size_t)w * h * 4);
    if (!ns) return;
    shadow = ns; SW = w; SH = h;
    // Same short-axis sizing as startup, or text changes size on rotation.
    int ref = SW < SH ? SW : SH;
    text_scale = ref / 540; if (text_scale < 2) text_scale = 2;
    g_text_px = g_text_px_req > 0 ? g_text_px_req : auto_text_px(ref);
    if (g_text_px < 14) g_text_px = 14;
    if (g_ttf_ok) g_ttf_scale = stbtt_ScaleForPixelHeight(&g_ttf, (float)g_text_px);
    scale_logo(g_logo_px_req > 0 ? g_logo_px_req : auto_logo_px(ref));
    if (x_img) { x_img->data = NULL; XDestroyImage(x_img); }   // don't free shadow (aliased)
    int scr = DefaultScreen(x_dpy);
    x_img = XCreateImage(x_dpy, DefaultVisual(x_dpy, scr), DefaultDepth(x_dpy, scr),
                         ZPixmap, 0, (char *)shadow, SW, SH, 32, SW * 4);
    if (x_img) x_img->byte_order = LSBFirst;
    compose(g_cur);
    x11_present();
}
#endif // HAVE_X11

// ================= ppm debug backend =================
// Debug backend: write one composed frame as a PPM (no fb/compositor needed).
static void write_ppm(const char *path) {
    FILE *f = fopen(path, "wb");
    if (!f) { fprintf(stderr, "armada-splash: cannot write %s\n", path); return; }
    fprintf(f, "P6\n%d %d\n255\n", SW, SH);
    for (int i = 0; i < SW * SH; i++) {
        uint32_t p = shadow[i];
        uint8_t rgb[3] = { (p >> 16) & 0xff, (p >> 8) & 0xff, p & 0xff };
        fwrite(rgb, 1, 3, f);
    }
    fclose(f);
    fprintf(stderr, "armada-splash: wrote %s (%dx%d)\n", path, SW, SH);
}

// ================= main =================

static const char *arg(int argc, char **argv, const char *k, const char *def) {
    for (int i = 1; i < argc - 1; i++) if (!strcmp(argv[i], k)) return argv[i + 1];
    return def;
}

int main(int argc, char **argv) {
    const char *image = arg(argc, argv, "--image", NULL);
    const char *status = arg(argc, argv, "--status", NULL);
    const char *backend = arg(argc, argv, "--backend", "auto");
    const char *fbdev = arg(argc, argv, "--fbdev", "/dev/fb0");
    int angle = atoi(arg(argc, argv, "--rotate", "0"));
    if (angle != 0 && angle != 90 && angle != 180 && angle != 270) {
        fprintf(stderr, "armada-splash: invalid --rotate %d\n", angle); return 1;
    }
    for (int i = 1; i < argc; i++) if (!strcmp(argv[i], "--keep-vt")) keep_vt = 1;
    const char *bgs = arg(argc, argv, "--bg", NULL);
    if (bgs) bg = 0xFF000000 | (strtoul(bgs, NULL, 0) & 0xFFFFFF);
    int req_w = atoi(arg(argc, argv, "--width", "0"));
    int req_h = atoi(arg(argc, argv, "--height", "0"));

    install_signal(SIGINT);
    install_signal(SIGTERM);

    // auto: x11 when an X display is present, else fbdev.
    int use_x11 = !strcmp(backend, "x11");
    if (!strcmp(backend, "auto")) use_x11 = getenv("DISPLAY") != NULL;

#ifndef HAVE_X11
    if (use_x11) { fprintf(stderr, "armada-splash: built without x11\n"); return 1; }
#endif

    int use_ppm = !strcmp(backend, "ppm");
    int use_drm = !strcmp(backend, "drm");
#ifdef HAVE_X11
    if (use_x11) {
        x_dpy = XOpenDisplay(NULL);
        if (!x_dpy) { fprintf(stderr, "armada-splash: cannot open X display\n"); return 1; }
        int scr = DefaultScreen(x_dpy);
        SW = req_w > 0 ? req_w : DisplayWidth(x_dpy, scr);   // gamescope's logical output
        SH = req_h > 0 ? req_h : DisplayHeight(x_dpy, scr);
    } else
#endif
    if (use_ppm) {
        SW = req_w > 0 ? req_w : 1080;
        SH = req_h > 0 ? req_h : 1920;
    } else if (use_drm) {
        if (drm_open(arg(argc, argv, "--connector", NULL), angle)) {
            vt_graphics();
        } else {
            fprintf(stderr, "armada-splash: drm unavailable; using fbdev\n");
            if (db.fd >= 0) { close(db.fd); db.fd = -1; }
            use_drm = 0;
            if (!fb_open(fbdev, angle)) return 1;
        }
    } else {
        if (!fb_open(fbdev, angle)) return 1;
    }

    shadow = malloc((size_t)SW * SH * 4);
    if (!shadow) { fprintf(stderr, "armada-splash: OOM\n"); return 1; }
    g_text_px_req = atoi(arg(argc, argv, "--text-height", "0"));
    // Short-axis sizing keeps text height equal in portrait and landscape modes.
    int text_ref = SW < SH ? SW : SH;
    text_scale = text_ref / 540; if (text_scale < 2) text_scale = 2;
    g_text_px = g_text_px_req > 0 ? g_text_px_req : auto_text_px(text_ref);
    if (g_text_px < 14) g_text_px = 14;
    g_gap = atoi(arg(argc, argv, "--gap", "-1"));
    for (int i = 1; i < argc - 1; i++)
        if (!strcmp(argv[i], "--logo-offset-x")) { g_logo_dx = atoi(argv[i + 1]); }
    if (!strcmp(arg(argc, argv, "--layout", "group"), "split")) g_layout = 1;
    g_appid = (uint32_t)strtoul(arg(argc, argv, "--appid", "0x41524d41"), NULL, 0);
    load_font(arg(argc, argv, "--font", "/usr/share/armada/splash/font.ttf"), g_text_px);
    load_image(image);
    img_src = img; img_src_w = img_w; img_src_h = img_h;
    g_logo_px_req = atoi(arg(argc, argv, "--logo-height", "0"));
    scale_logo(g_logo_px_req > 0 ? g_logo_px_req : auto_logo_px(text_ref));

    read_status(status, g_cur, sizeof g_cur);
    compose(g_cur);
    strcpy(g_shown, g_cur);

    if (use_ppm) { write_ppm(arg(argc, argv, "--out", "/tmp/armada-splash.ppm")); return 0; }

#ifdef HAVE_X11
    if (use_x11) {
        if (!x11_init()) return 1;
        x11_present();
        int tfd = timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC);
        struct itimerspec its = { {0, 250000000}, {0, 250000000} };
        timerfd_settime(tfd, 0, &its, NULL);
        int xfd = ConnectionNumber(x_dpy);
        while (running) {
            struct pollfd fds[2] = { { xfd, POLLIN, 0 }, { tfd, POLLIN, 0 } };
            if (poll(fds, 2, -1) < 0 && errno == EINTR) continue;
            if (fds[0].revents & POLLIN)
                while (XPending(x_dpy)) {
                    XEvent ev; XNextEvent(x_dpy, &ev);
                    if (ev.type == Expose) x11_present();
                    else if (ev.type == ConfigureNotify) x11_resize(ev.xconfigure.width, ev.xconfigure.height);
                    else if (ev.type == PropertyNotify && ev.xproperty.atom == a_focused_win)
                        x11_check_focus();
                }
            if (fds[1].revents & POLLIN) {
                uint64_t x; ssize_t rr = read(tfd, &x, sizeof x); (void)rr;
                read_status(status, g_cur, sizeof g_cur);
                if (strcmp(g_cur, g_shown)) { compose(g_cur); strcpy(g_shown, g_cur); x11_present(); }
            }
        }
        return 0;
    }
#endif

    void (*present)(void) = use_drm ? drm_present : fb_present;
    present();
    int tfd = timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC);
    struct itimerspec its = { {0, 250000000}, {0, 250000000} };
    timerfd_settime(tfd, 0, &its, NULL);
    // Deactivate handshake: a successor (next drawer, or sddm for the
    // session) writes the takeover file; the incumbent yields and exits.
    int yielded = 0;
    const char *tkpath = "/run/armada/takeover";
    char mytk[32], tk[32];
    snprintf(mytk, sizeof mytk, "%d\n", (int)getpid());
    if (use_drm) {
        FILE *tf = fopen(tkpath, "w");
        if (tf) { fputs(mytk, tf); fclose(tf); }
    }
    while (running) {
        struct pollfd pfd = { tfd, POLLIN, 0 };
        if (poll(&pfd, 1, -1) < 0 && errno == EINTR) continue;
        uint64_t x; ssize_t rr = read(tfd, &x, sizeof x); (void)rr;
        if (use_drm) {
            if (!db.crtc_on) { present(); }   // keep retrying the first modeset
            read_status(tkpath, tk, sizeof tk);
            if (tk[0] && strcmp(tk, mytk)) {
                fprintf(stderr, "armada-splash: yielding display\n");
                yielded = 1;
                break;
            }
        }
        read_status(status, g_cur, sizeof g_cur);
        if (strcmp(g_cur, g_shown)) { compose(g_cur); strcpy(g_shown, g_cur); present(); }
    }
    // TERM can land between takeover polls; the successor's announce precedes
    // the stop, so a final read decides. No announce (shutdown) = no linger.
    if (use_drm && !yielded) {
        read_status(tkpath, tk, sizeof tk);
        yielded = tk[0] && strcmp(tk, mytk);
    }
    // Yield the master, then hold the fd until the scanout provably moves
    // off this drawer's framebuffer: closing earlier destroys the fb mid-scan
    // (black), and GetCrtc needs no master. Bounded as a crash backstop.
    if (use_drm && db.crtc_on && yielded) {
        drmDropMaster(db.fd);
        for (int i = 0; i < 240; i++) {
            drmModeCrtc *c = drmModeGetCrtc(db.fd, db.crtc_id);
            // A failed query says nothing about the scanout; only a readable
            // CRTC naming another framebuffer proves the handoff happened.
            int moved = c && c->buffer_id != db.fb_id;
            if (c) drmModeFreeCrtc(c);
            if (moved) break;
            usleep(250000);
        }
    }
    return 0;
}
