// Display-boundary i18n for armada-splash status lines.
//
// Known English status text is resolved through typed locale catalogs: the
// English table maps a stable key to the source text and the target table maps
// that key to the translation. Unknown diagnostics and text that is already
// translated pass through unchanged. POSIX/C standard library only.
#define _GNU_SOURCE
#include <ctype.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>

#include "splash-i18n.h"

// One typed catalog entry: an independent stable key and its display text.
// A template entry carries a single "{...}" placeholder.
typedef struct { const char *key; const char *text; } SplashMsg;

#include "locales/en.h"
#include "locales/zh-CN.h"

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

static void trim_copy(const char *s, char *dst, size_t cap)
{
    if (cap == 0) return;
    if (!s) { dst[0] = '\0'; return; }
    while (*s && isspace((unsigned char)*s)) s++;
    size_t n = strlen(s);
    while (n > 0 && isspace((unsigned char)s[n - 1])) n--;
    if (n >= cap) n = cap - 1;
    memcpy(dst, s, n);
    dst[n] = '\0';
}

// Copy the next double-quoted token, advancing *pp. Returns 0 at end of input.
static int next_quoted(const char **pp, char *dst, size_t cap)
{
    const char *p = *pp;
    while (*p && *p != '"') p++;
    if (*p != '"') { *pp = p; return 0; }
    p++;
    size_t n = 0;
    while (*p && *p != '"' && *p != '\n' && n < cap - 1) dst[n++] = *p++;
    while (*p && *p != '"' && *p != '\n') p++;   // drain an overlong token
    if (*p == '"') p++;
    dst[n] = '\0';
    *pp = p;
    return 1;
}

// Last non-blank value of an exact quoted "language" key. "gamelanguage" is a
// different token and never matches.
static void registry_language(const char *data, char *out, size_t cap)
{
    out[0] = '\0';
    const char *p = data;
    char tok[128], prev[128];
    prev[0] = '\0';
    int have_prev = 0;
    while (next_quoted(&p, tok, sizeof tok)) {
        if (have_prev && strcasecmp(prev, "language") == 0 && tok[0])
            snprintf(out, cap, "%s", tok);   // last non-blank wins
        snprintf(prev, sizeof prev, "%s", tok);
        have_prev = 1;
    }
}

// Regular files only; the registry lives in a user-writable directory while
// this can run as root, so a bounded non-blocking read is used.
static int read_registry(const char *path, char *buf, size_t cap)
{
    if (!path || !*path) return 0;
    int fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return 0;
    struct stat st;
    if (fstat(fd, &st) != 0 || !S_ISREG(st.st_mode)) { close(fd); return 0; }
    ssize_t r = read(fd, buf, cap - 1);
    close(fd);
    if (r < 0) return 0;
    buf[r] = '\0';
    return 1;
}

SplashLocale splash_resolve_locale(const char *override,
                                   const char *steam_registry,
                                   const char *system_language)
{
    char ov[64], buf[8192], lang[128];
    trim_copy(override, ov, sizeof ov);
    if (ov[0] && strcasecmp(ov, "auto") != 0)
        return splash_locale_from_language(ov);
    if (read_registry(steam_registry, buf, sizeof buf)) {
        registry_language(buf, lang, sizeof lang);
        // A non-empty Steam value decides, even when unsupported (-> EN).
        if (lang[0]) return splash_locale_from_language(lang);
    }
    return splash_locale_from_language(system_language);
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

// Match a single-placeholder template and report the captured argument.
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

// Resolve one source line into the zh-CN catalog, or copy it through verbatim.
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
