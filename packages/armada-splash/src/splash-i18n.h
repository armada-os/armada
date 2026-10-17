// Display-boundary i18n for armada-splash status lines.
//
// Caller scripts keep writing their English status text unchanged; this module
// only translates at draw time. It is self-contained (C stdlib / POSIX, no
// dependencies) and never mutates the caller's string or state.
#ifndef ARMADA_SPLASH_I18N_H
#define ARMADA_SPLASH_I18N_H

#include <stddef.h>

typedef enum {
    SPLASH_LOCALE_EN,
    SPLASH_LOCALE_ZH_CN
} SplashLocale;

// Normalize a language tag (trim, lowercase, '_' -> '-', strip POSIX
// .encoding / @modifier) and map it onto a supported locale. Missing or
// unrecognized input maps to English; Traditional Chinese stays English.
SplashLocale splash_locale_from_language(const char *language);

// Choose the display locale. A non-blank override other than "auto" wins;
// otherwise the exact quoted "language" value from the Steam registry at
// steam_registry (a FILE PATH, not VDF content) is used; otherwise
// system_language. The last non-blank language in the registry wins, and a
// non-empty but unsupported Steam value maps to English without consulting
// system_language.
SplashLocale splash_resolve_locale(const char *override,
                                   const char *steam_registry,
                                   const char *system_language);

// Translate one status line. English is returned verbatim; zh-CN maps known
// English sources through the locale catalogs and passes unknown diagnostics
// and already-translated text through unchanged. A leading '!' is preserved
// and does not gate translation. At most out_size bytes are written and the
// result is always NUL terminated when out_size > 0; out_size == 0 writes
// nothing at all.
void splash_translate_line(SplashLocale locale, const char *source,
                           char *out, size_t out_size);

#endif // ARMADA_SPLASH_I18N_H
