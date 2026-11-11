#define _GNU_SOURCE
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include "splash-i18n.h"

// One typed catalog entry: an independent stable key and its display text.
// A template entry carries a single "{...}" placeholder.
typedef struct { const char *key; const char *text; } SplashMsg;

#include "locales/en.h"
#include "locales/zh-CN.h"

#define KEY_CAP   64
#define MAX_DEPTH 32
#define LANG_CAP  128

// Aliases copied from the armada-control i18n language list.
static int is_zh_cn_alias(const char *tag)
{
    static const char *const aliases[] = {
        "schinese", "steamchina-schinese", "zh", "zh-cn", "zh-hans", "zh-sg",
    };
    for (size_t i = 0; i < sizeof aliases / sizeof aliases[0]; i++)
        if (strcmp(tag, aliases[i]) == 0) return 1;
    return 0;
}

int splash_language_is_auto(const char *s)
{
    if (!s) return 1;
    while (*s && isspace((unsigned char)*s)) s++;
    const char *e = s + strlen(s);
    while (e > s && isspace((unsigned char)e[-1])) e--;
    size_t n = (size_t)(e - s);
    if (n == 0) return 1;
    return n == 4 && strncasecmp(s, "auto", 4) == 0;
}

SplashLocale splash_locale_from_language(const char *language)
{
    char tag[64];
    size_t n = 0;
    const char *p = language ? language : "";
    while (*p && isspace((unsigned char)*p)) p++;
    for (; *p && n < sizeof tag - 1; p++) {
        unsigned char c = (unsigned char)*p;
        if (c == '.' || c == '@') break;   // POSIX .encoding / @modifier
        if (c == '_') c = '-';
        tag[n++] = (char)tolower(c);
    }
    while (n > 0 && isspace((unsigned char)tag[n - 1])) n--;
    tag[n] = '\0';
    return is_zh_cn_alias(tag) ? SPLASH_LOCALE_ZH_CN : SPLASH_LOCALE_EN;
}

enum tok_kind { T_STRING, T_OBRACE, T_CBRACE, T_END, T_ERR };

// Skip whitespace and // comments (end-of-input ends a comment normally).
static int skip_ws(const char **pp)
{
    const char *p = *pp;
    for (;;) {
        while (*p && isspace((unsigned char)*p)) p++;
        if (p[0] == '/' && p[1] == '/') {
            p += 2;
            while (*p && *p != '\n') p++;
            continue;
        }
        break;
    }
    *pp = p;
    return 1;
}

// Read a whole quoted token. Oversized tokens consume to the closing quote
// but store "?" so they cannot truncate-match; only bad quoting fails.
static int read_string(const char **pp, char *dst, size_t cap)
{
    const char *p = *pp;
    if (*p != '"') return 0;
    p++;
    size_t n = 0;
    int over = 0;
    while (*p && *p != '"') {
        unsigned char c = (unsigned char)*p;
        if (c == '\\' && (p[1] == '"' || p[1] == '\\')) {
            c = (unsigned char)p[1];
            p += 2;
        } else {
            p++;
        }
        if (c == '\n') return 0;
        if (n + 1 >= cap) { over = 1; continue; }
        if (!over) dst[n++] = (char)c;
    }
    if (*p != '"') return 0;
    p++;
    if (over) { dst[0] = '?'; dst[1] = '\0'; }
    else dst[n] = '\0';
    *pp = p;
    return 1;
}

static enum tok_kind next_tok(const char **pp, char *dst, size_t cap)
{
    if (!skip_ws(pp)) return T_ERR;
    const char *p = *pp;
    if (!*p) { return T_END; }
    if (*p == '{') { (*pp)++; return T_OBRACE; }
    if (*p == '}') { (*pp)++; return T_CBRACE; }
    if (*p == '"') {
        if (!read_string(pp, dst, cap)) return T_ERR;
        return T_STRING;
    }
    return T_ERR;
}

// One-pass parser: alternating key/value states. Any brace mismatch or
// trailing garbage rejects the document. Only language values at the exact
// Registry/HKCU/Software/Valve/(Steam|Steamsteamglobal) stack are captured.
// Returns 1 with the chosen language (empty = unsupported); 0 on error.
static int parse_registry(const char *data, char *out, size_t out_cap)
{
    out[0] = '\0';
    char stack[MAX_DEPTH][KEY_CAP];
    int depth = 0;
    char key[KEY_CAP];
    int pending = 0;
    char lang_sg[LANG_CAP];
    char lang_st[LANG_CAP];
    lang_sg[0] = lang_st[0] = '\0';

    const char *p = data;
    for (;;) {
        char tok[KEY_CAP];
        enum tok_kind k = next_tok(&p, tok, sizeof tok);
        if (k == T_ERR) return 0;
        if (k == T_END) {
            if (depth != 0 || pending) return 0;
            break;
        }
        if (k == T_CBRACE) {
            if (depth == 0 || pending) return 0;
            depth--;
            continue;
        }
        if (k == T_OBRACE) {
            if (!pending) return 0;   // value was expected, brace is not
            if (depth >= MAX_DEPTH) return 0;
            snprintf(stack[depth], KEY_CAP, "%s", key);
            depth++;
            pending = 0;
            continue;
        }
        // k == T_STRING
        if (!pending) {
            snprintf(key, sizeof key, "%s", tok);
            pending = 1;
            continue;
        }
        // Value: a string completes the pair.
        int match = depth == 5 &&
                    strcasecmp(stack[0], "Registry") == 0 &&
                    strcasecmp(stack[1], "HKCU") == 0 &&
                    strcasecmp(stack[2], "Software") == 0 &&
                    strcasecmp(stack[3], "Valve") == 0 &&
                    (strcasecmp(stack[4], "Steam") == 0 ||
                     strcasecmp(stack[4], "Steamsteamglobal") == 0) &&
                    strcasecmp(key, "language") == 0;
        if (match) {
            char *dst = strcasecmp(stack[4], "Steamsteamglobal") == 0
                        ? lang_sg : lang_st;
            if (tok[0]) snprintf(dst, LANG_CAP, "%s", tok);
        }
        pending = 0;
    }
    if (lang_sg[0]) snprintf(out, out_cap, "%s", lang_sg);
    else if (lang_st[0]) snprintf(out, out_cap, "%s", lang_st);
    return 1;
}

static int read_registry(const char *path, char *buf, size_t cap)
{
    if (!path || !*path) return 0;
    int fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return 0;
    struct stat st;
    if (fstat(fd, &st) != 0 || !S_ISREG(st.st_mode)) { close(fd); return 0; }
    if (st.st_size < 0 || (unsigned long long)st.st_size >= cap) { close(fd); return 0; }
    ssize_t r = read(fd, buf, cap - 1);
    close(fd);
    if (r < 0 || (off_t)r != st.st_size) return 0;
    if (memchr(buf, '\0', (size_t)r)) return 0;
    buf[r] = '\0';
    return 1;
}

SplashLocale splash_resolve_locale(const char *override,
                                   const char *steam_registry,
                                   const char *system_language)
{
    char buf[16384], lang[LANG_CAP];
    if (!splash_language_is_auto(override))
        return splash_locale_from_language(override);
    if (read_registry(steam_registry, buf, sizeof buf)) {
        if (!parse_registry(buf, lang, sizeof lang)) {
            return splash_locale_from_language(system_language);
        }
        if (lang[0]) return splash_locale_from_language(lang);
    }
    return splash_locale_from_language(system_language);
}

// Strict cache read: O_NOFOLLOW|O_NONBLOCK; only "en"/"zh-CN" plus one
// optional newline. Anything else leaves *out untouched.
int splash_read_locale_file(const char *path, SplashLocale *out)
{
    if (!path || !*path || !out) return 0;
    int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return 0;
    struct stat st;
    if (fstat(fd, &st) != 0 || !S_ISREG(st.st_mode)) { close(fd); return 0; }
    if (st.st_size <= 0 || st.st_size > 16) { close(fd); return 0; }
    char b[17];
    ssize_t r = read(fd, b, sizeof b - 1);
    close(fd);
    if (r < 0 || (off_t)r != st.st_size) return 0;
    b[r] = '\0';
    size_t n = (size_t)r;
    if (n > 0 && b[n - 1] == '\n') {
        n--;
        if (n > 0 && b[n - 1] == '\r') n--;
    }
    if (n == 2 && memcmp(b, "en", 2) == 0) { *out = SPLASH_LOCALE_EN; return 1; }
    if (n == 5 && memcmp(b, "zh-CN", 5) == 0) { *out = SPLASH_LOCALE_ZH_CN; return 1; }
    return 0;
}

// Atomic publish: sibling mkstemp, write-all, chmod, rename; clean temp on error.
int splash_write_locale_file(const char *path, SplashLocale locale)
{
    if (!path || !*path) return 0;
    const char *dot = strrchr(path, '/');
    size_t dlen = dot ? (size_t)(dot - path) + 1 : 0;
    char tmpl[1024];
    if (dlen + 16 >= sizeof tmpl) return 0;
    if (dlen) memcpy(tmpl, path, dlen);
    memcpy(tmpl + dlen, ".splash-XXXXXX", sizeof ".splash-XXXXXX");
    int fd = mkstemp(tmpl);
    if (fd < 0) return 0;
    const char *text = locale == SPLASH_LOCALE_ZH_CN ? "zh-CN\n" : "en\n";
    size_t len = strlen(text);
    size_t off = 0;
    int ok = 1;
    while (off < len) {
        ssize_t w = write(fd, text + off, len - off);
        if (w <= 0) { if (errno == EINTR) continue; ok = 0; break; }
        off += (size_t)w;
    }
    if (ok && fchmod(fd, 0644) != 0) ok = 0;
    if (close(fd) != 0) ok = 0;
    if (ok && rename(tmpl, path) != 0) ok = 0;
    if (!ok) unlink(tmpl);
    return ok;
}

static const char *catalog_text(const SplashMsg *cat, size_t n, const char *key)
{
    for (size_t i = 0; i < n; i++)
        if (strcmp(cat[i].key, key) == 0) return cat[i].text;
    return NULL;
}

// Steam exit codes are numeric and may be negative; anything else is a raw
// diagnostic and must not be rewritten.
static int is_numeric_code(const char *s, size_t len)
{
    size_t i = 0;
    if (len == 0) return 0;
    if (s[0] == '-') i = 1;
    if (i >= len) return 0;
    for (; i < len; i++)
        if (s[i] < '0' || s[i] > '9') return 0;
    return 1;
}

static int match_template(const char *tpl, const char *src,
                          const char **arg, size_t *arg_len)
{
    const char *open = strchr(tpl, '{');
    const char *close = open ? strchr(open, '}') : NULL;
    if (!open || !close) return 0;
    size_t pre = (size_t)(open - tpl);
    size_t suf = strlen(close + 1);
    size_t len = strlen(src);
    if (len < pre + suf || strncmp(src, tpl, pre) != 0) return 0;
    if (suf && strcmp(src + len - suf, close + 1) != 0) return 0;
    size_t mid = len - pre - suf;
    if (mid == 0) return 0;
    if (close - open == 5 && strncmp(open, "{code}", 6) == 0 &&
        !is_numeric_code(src + pre, mid)) return 0;
    *arg = src + pre;
    *arg_len = mid;
    return 1;
}

static void translate_into(const char *src, char *out, size_t out_size)
{
    const size_t n_en = sizeof SPLASH_EN_CATALOG / sizeof SPLASH_EN_CATALOG[0];
    const size_t n_zh = sizeof SPLASH_ZH_CN_CATALOG /
                        sizeof SPLASH_ZH_CN_CATALOG[0];
    const char *key = NULL, *arg = NULL;
    size_t arg_len = 0;

    for (size_t i = 0; i < n_en && !key; i++) {
        const SplashMsg *e = &SPLASH_EN_CATALOG[i];
        if (!strchr(e->text, '{') && strcmp(e->text, src) == 0) key = e->key;
    }
    for (size_t i = 0; i < n_en && !key; i++) {
        const SplashMsg *e = &SPLASH_EN_CATALOG[i];
        if (strchr(e->text, '{') && match_template(e->text, src, &arg, &arg_len))
            key = e->key;
    }

    const char *zh = key ? catalog_text(SPLASH_ZH_CN_CATALOG, n_zh, key) : NULL;
    const char *open = zh ? strchr(zh, '{') : NULL;
    const char *close = open ? strchr(open, '}') : NULL;
    if (!zh || !open || !close || !arg) {
        snprintf(out, out_size, "%s", zh ? zh : src);
        return;
    }
    snprintf(out, out_size, "%.*s%.*s%s",
             (int)(open - zh), zh, (int)arg_len, arg, close + 1);
}

void splash_translate_line(SplashLocale locale, const char *source,
                           char *out, size_t out_size)
{
    if (out_size == 0) return;
    if (!source) source = "";
    if (locale == SPLASH_LOCALE_EN) {
        snprintf(out, out_size, "%s", source);
        return;
    }
    const char *prefix = "";
    if (*source == '!') { prefix = "!"; source++; }
    char core[512];
    translate_into(source, core, sizeof core);
    snprintf(out, out_size, "%s%s", prefix, core);
}
