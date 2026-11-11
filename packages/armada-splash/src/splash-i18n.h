#ifndef ARMADA_SPLASH_I18N_H
#define ARMADA_SPLASH_I18N_H

#include <stddef.h>

typedef enum {
    SPLASH_LOCALE_EN,
    SPLASH_LOCALE_ZH_CN
} SplashLocale;

SplashLocale splash_locale_from_language(const char *language);

// True for null/empty/whitespace or exactly "auto" (case-insensitive,
// surrounding whitespace ignored).
int splash_language_is_auto(const char *s);

SplashLocale splash_resolve_locale(const char *override,
                                   const char *steam_registry,
                                   const char *system_language);

void splash_translate_line(SplashLocale locale, const char *source,
                           char *out, size_t out_size);

// Strict canonical locale cache reader/writer (en or zh-CN plus optional
// terminal newline). Returns 1 on success, 0 otherwise. Never follows a final
// symlink into user filesystem; rejects nonregular, oversized, truncated.
int splash_read_locale_file(const char *path, SplashLocale *locale);

// Write "en\n" or "zh-CN\n" atomically via mkstemp sibling + rename. The
// caller is an ordinary user; /run siblings must already exist.
int splash_write_locale_file(const char *path, SplashLocale locale);

#endif // ARMADA_SPLASH_I18N_H
