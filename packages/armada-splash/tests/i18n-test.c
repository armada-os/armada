/*
 * i18n-test.c - behavior tests for the armada-splash i18n production module.
 *
 * This test includes the real production header (splash-i18n.h) and is linked
 * against the real production implementation (splash-i18n.c). There is no mock
 * implementation in this file.
 *
 * Usage:
 *     i18n-test <writable-output-dir>
 *
 * argv[1] must be a writable directory. Every fixture this test creates is
 * written inside that directory.
 *
 * Exit status: 0 when every check passes, non-zero on the first failed check.
 */

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "splash-i18n.h"

/* ------------------------------------------------------------------ */
/* Labeled assertions                                                  */
/* ------------------------------------------------------------------ */

#define LABEL(cond, label)                                                    \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "ASSERT FAILED: %s (%s:%d)\n", (label), __FILE__, \
                    __LINE__);                                                \
        }                                                                     \
        assert(cond);                                                         \
    } while (0)

#define CHECK_LOCALE(label, got, want)                                        \
    do {                                                                      \
        SplashLocale got_ = (got);                                            \
        SplashLocale want_ = (want);                                          \
        if (got_ != want_) {                                                  \
            fprintf(stderr,                                                   \
                    "ASSERT FAILED: %s (got %d, want %d) (%s:%d)\n",          \
                    (label), (int)got_, (int)want_, __FILE__, __LINE__);      \
        }                                                                     \
        assert(got_ == want_);                                                \
    } while (0)

#define CHECK_STR(label, got, want)                                           \
    do {                                                                      \
        const char *got_ = (got);                                             \
        const char *want_ = (want);                                           \
        if (strcmp(got_, want_) != 0) {                                       \
            fprintf(stderr,                                                   \
                    "ASSERT FAILED: %s (%s:%d)\n"                             \
                    "  expected: \"%s\"\n"                                    \
                    "  actual:   \"%s\"\n",                                   \
                    (label), __FILE__, __LINE__, want_, got_);                \
        }                                                                     \
        assert(strcmp(got_, want_) == 0);                                     \
    } while (0)

/* ------------------------------------------------------------------ */
/* Small filesystem helpers (all fixtures live under argv[1])          */
/* ------------------------------------------------------------------ */

static char *path_join(const char *dir, const char *name)
{
    size_t dir_len = strlen(dir);
    size_t name_len = strlen(name);
    char *p = (char *)malloc(dir_len + 1 + name_len + 1);
    if (p == NULL) {
        return NULL;
    }
    memcpy(p, dir, dir_len);
    p[dir_len] = '/';
    memcpy(p + dir_len + 1, name, name_len);
    p[dir_len + 1 + name_len] = '\0';
    return p;
}

static int write_text_file(const char *path, const char *data)
{
    FILE *f = fopen(path, "wb");
    if (f == NULL) {
        return -1;
    }
    size_t len = strlen(data);
    size_t wrote = fwrite(data, 1, len, f);
    int rc = (wrote == len) ? 0 : -1;
    if (fclose(f) != 0) {
        rc = -1;
    }
    return rc;
}

static int file_exists(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (f == NULL) {
        return 0;
    }
    fclose(f);
    return 1;
}

/* ------------------------------------------------------------------ */
/* Steam registry.vdf-style fixtures (CRLF + tab indentation, no PII)  */
/* ------------------------------------------------------------------ */

static const char REG_ZH_CRLF[] =
    "\"Registry\"\r\n"
    "{\r\n"
    "\t\"HKCU\"\r\n"
    "\t{\r\n"
    "\t\t\"Software\"\r\n"
    "\t\t{\r\n"
    "\t\t\t\"Valve\"\r\n"
    "\t\t\t{\r\n"
    "\t\t\t\t\"Steam\"\r\n"
    "\t\t\t\t{\r\n"
    "\t\t\t\t\t\"language\"\t\t\"schinese\"\r\n"
    "\t\t\t\t}\r\n"
    "\t\t\t}\r\n"
    "\t\t}\r\n"
    "\t}\r\n"
    "}\r\n";

static const char REG_EN[] =
    "\"Registry\"\r\n"
    "{\r\n"
    "\t\"HKCU\"\r\n"
    "\t{\r\n"
    "\t\t\"language\"\t\t\"english\"\r\n"
    "\t}\r\n"
    "}\r\n";

static const char REG_FR[] =
    "\"Registry\"\r\n"
    "{\r\n"
    "\t\"HKCU\"\r\n"
    "\t{\r\n"
    "\t\t\"language\"\t\t\"french\"\r\n"
    "\t}\r\n"
    "}\r\n";

/* "language" is english while the decoy "gamelanguage" is schinese. */
static const char REG_LANG_EN_GAMELANG_ZH[] =
    "\"Registry\"\r\n"
    "{\r\n"
    "\t\"HKCU\"\r\n"
    "\t{\r\n"
    "\t\t\"language\"\t\t\"english\"\r\n"
    "\t\t\"gamelanguage\"\t\t\"schinese\"\r\n"
    "\t}\r\n"
    "}\r\n";

/* Only the decoy key is present; there is no "language" key at all. */
static const char REG_GAMELANG_ONLY[] =
    "\"Registry\"\r\n"
    "{\r\n"
    "\t\"HKCU\"\r\n"
    "\t{\r\n"
    "\t\t\"gamelanguage\"\t\t\"schinese\"\r\n"
    "\t}\r\n"
    "}\r\n";

/* ------------------------------------------------------------------ */
/* Locale selection                                                    */
/* ------------------------------------------------------------------ */

static void test_locale_from_language(void)
{
    static const struct {
        const char *name;
        const char *lang;
        SplashLocale want;
    } cases[] = {
        { "en lower",           "en",                  SPLASH_LOCALE_EN },
        { "en upper",           "EN",                  SPLASH_LOCALE_EN },
        { "english",            "English",             SPLASH_LOCALE_EN },
        { "empty",              "",                    SPLASH_LOCALE_EN },
        { "null",               NULL,                  SPLASH_LOCALE_EN },
        { "unsupported fr",     "fr",                  SPLASH_LOCALE_EN },
        { "unsupported de-DE",  "de-DE",               SPLASH_LOCALE_EN },
        { "tchinese",           "tchinese",            SPLASH_LOCALE_EN },
        { "tchinese upper",     "TChinese",            SPLASH_LOCALE_EN },
        { "schinese",           "schinese",            SPLASH_LOCALE_ZH_CN },
        { "schinese mixed",     "SChinese",            SPLASH_LOCALE_ZH_CN },
        { "steamchina",         "SteamChina_SChinese", SPLASH_LOCALE_ZH_CN },
        { "zh",                 "zh",                  SPLASH_LOCALE_ZH_CN },
        { "zh-CN",              "zh-CN",               SPLASH_LOCALE_ZH_CN },
        { "zh_Hans",            "zh_Hans",             SPLASH_LOCALE_ZH_CN },
        { "zh-SG",              "zh-SG",               SPLASH_LOCALE_ZH_CN },
        { "zh_CN posix",        "zh_CN.UTF-8",         SPLASH_LOCALE_ZH_CN },
        { "zh trimmed+case",    "  ZH_cn.utf8  ",      SPLASH_LOCALE_ZH_CN },
        { "schinese padded",    "schinese ",           SPLASH_LOCALE_ZH_CN },
        { "english padded",     " English ",           SPLASH_LOCALE_EN },
    };

    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        CHECK_LOCALE(cases[i].name,
                     splash_locale_from_language(cases[i].lang),
                     cases[i].want);
    }
}

static void test_resolve_locale(const char *out_dir)
{
    /* The registry argument is a PATH to registry.vdf, never its contents.
       Every fixture is written to disk inside the output directory and only
       its path is handed to the API. */
    char *reg_zh_path = path_join(out_dir, "steam-registry-zh.vdf");
    char *reg_en_path = path_join(out_dir, "steam-registry-en.vdf");
    char *reg_fr_path = path_join(out_dir, "steam-registry-fr.vdf");
    char *reg_lang_en_gamelang_zh_path =
        path_join(out_dir, "steam-registry-lang-en-gamelang-zh.vdf");
    char *reg_gamelang_only_path =
        path_join(out_dir, "steam-registry-gamelang-only.vdf");
    char *missing_path = path_join(out_dir, "steam-registry-absent.vdf");

    LABEL(reg_zh_path != NULL, "allocate registry fixture path (zh)");
    LABEL(reg_en_path != NULL, "allocate registry fixture path (en)");
    LABEL(reg_fr_path != NULL, "allocate registry fixture path (fr)");
    LABEL(reg_lang_en_gamelang_zh_path != NULL,
          "allocate registry fixture path (lang/gamelang)");
    LABEL(reg_gamelang_only_path != NULL,
          "allocate registry fixture path (gamelang only)");
    LABEL(missing_path != NULL, "allocate missing fixture path");

    LABEL(write_text_file(reg_zh_path, REG_ZH_CRLF) == 0,
          "write registry fixture (zh)");
    LABEL(write_text_file(reg_en_path, REG_EN) == 0,
          "write registry fixture (en)");
    LABEL(write_text_file(reg_fr_path, REG_FR) == 0,
          "write registry fixture (fr)");
    LABEL(write_text_file(reg_lang_en_gamelang_zh_path,
                          REG_LANG_EN_GAMELANG_ZH) == 0,
          "write registry fixture (lang/gamelang)");
    LABEL(write_text_file(reg_gamelang_only_path, REG_GAMELANG_ONLY) == 0,
          "write registry fixture (gamelang only)");

    /* An explicit override wins over Steam and over the system language. */
    CHECK_LOCALE("override en beats chinese steam",
                 splash_resolve_locale("en", reg_zh_path, "zh"),
                 SPLASH_LOCALE_EN);
    CHECK_LOCALE("override en beats chinese system",
                 splash_resolve_locale("en", reg_zh_path, "schinese"),
                 SPLASH_LOCALE_EN);
    CHECK_LOCALE("override zh-CN beats english steam",
                 splash_resolve_locale("zh-CN", reg_en_path, "en"),
                 SPLASH_LOCALE_ZH_CN);

    /* auto / empty / null override falls through to the Steam language. */
    CHECK_LOCALE("auto falls through to steam chinese",
                 splash_resolve_locale("auto", reg_zh_path, "en"),
                 SPLASH_LOCALE_ZH_CN);
    CHECK_LOCALE("empty override falls through to steam chinese",
                 splash_resolve_locale("", reg_zh_path, "en"),
                 SPLASH_LOCALE_ZH_CN);
    CHECK_LOCALE("null override falls through to steam chinese",
                 splash_resolve_locale(NULL, reg_zh_path, "en"),
                 SPLASH_LOCALE_ZH_CN);
    CHECK_LOCALE("null override falls through to steam english",
                 splash_resolve_locale(NULL, reg_en_path, "zh"),
                 SPLASH_LOCALE_EN);

    /* Only the "language" key counts; "gamelanguage" must never match. */
    CHECK_LOCALE("language key only, ignore gamelanguage",
                 splash_resolve_locale("auto", reg_lang_en_gamelang_zh_path,
                                       "zh"),
                 SPLASH_LOCALE_EN);
    CHECK_LOCALE("gamelanguage-only registry falls to system",
                 splash_resolve_locale("auto", reg_gamelang_only_path, "en"),
                 SPLASH_LOCALE_EN);

    /* Steam english / unsupported nonempty beats system zh. */
    CHECK_LOCALE("steam english beats system zh",
                 splash_resolve_locale("auto", reg_en_path, "zh"),
                 SPLASH_LOCALE_EN);
    CHECK_LOCALE("steam unsupported beats system zh",
                 splash_resolve_locale("auto", reg_fr_path, "zh"),
                 SPLASH_LOCALE_EN);

    /* Empty or NULL registry path falls to the system language. */
    CHECK_LOCALE("empty registry path falls to system zh",
                 splash_resolve_locale("auto", "", "zh"), SPLASH_LOCALE_ZH_CN);
    CHECK_LOCALE("null registry path falls to system chinese",
                 splash_resolve_locale("auto", NULL, "schinese"),
                 SPLASH_LOCALE_ZH_CN);
    CHECK_LOCALE("system trimmed with posix",
                 splash_resolve_locale(NULL, NULL, "  zh_CN.UTF-8  "),
                 SPLASH_LOCALE_ZH_CN);

    /* A registry path that does not exist on disk behaves like no registry. */
    LABEL(!file_exists(missing_path), "absent registry path does not exist");
    CHECK_LOCALE("missing registry path falls to system zh",
                 splash_resolve_locale("auto", missing_path, "zh"),
                 SPLASH_LOCALE_ZH_CN);

    /* Nothing provided at all falls back to EN. */
    CHECK_LOCALE("all null falls to en",
                 splash_resolve_locale(NULL, NULL, NULL), SPLASH_LOCALE_EN);
    CHECK_LOCALE("all empty falls to en",
                 splash_resolve_locale("", "", ""), SPLASH_LOCALE_EN);

    free(reg_zh_path);
    free(reg_en_path);
    free(reg_fr_path);
    free(reg_lang_en_gamelang_zh_path);
    free(reg_gamelang_only_path);
    free(missing_path);
}

/* ------------------------------------------------------------------ */
/* Translation                                                         */
/* ------------------------------------------------------------------ */

static void expect_translate(SplashLocale loc, const char *src,
                             const char *want, const char *label)
{
    char out[512];
    memset(out, 0, sizeof out);
    splash_translate_line(loc, src, out, sizeof out);
    CHECK_STR(label, out, want);
}

static void test_translations(void)
{
    static const struct {
        const char *name;
        const char *src;
        const char *zh;
    } pairs[] = {
        { "preparing armada",
          "Preparing Armada",
          "正在准备 Armada" },
        { "starting steam",
          "Starting Steam",
          "正在启动 Steam" },
        { "restarting steam",
          "Restarting Steam",
          "正在重启 Steam" },
        { "installing steam",
          "Installing Steam",
          "正在安装 Steam" },
        { "still starting",
          "Still starting. First boot installs Steam and can take a few minutes.",
          "正在启动。首次启动需要安装 Steam，可能耗时几分钟。" },
        { "shutting down",
          "Shutting down",
          "正在关机" },
        { "restarting",
          "Restarting",
          "正在重启" },
        { "applying update",
          "Applying update. Do not power off.",
          "正在应用更新，请勿断电。" },
        { "starting desktop",
          "Starting Desktop",
          "正在启动桌面" },
        { "udev settle",
          "Waiting for systemd-udev-settle.service",
          "正在等待 systemd-udev-settle.service" },
        { "steam launch failed",
          "Steam launch failed (exit 7)",
          "Steam 启动失败（退出码 7）" },
        { "steam launch failed exit 9",
          "Steam launch failed (exit 9)",
          "Steam 启动失败（退出码 9）" },
        { "steam launch failed exit -1",
          "Steam launch failed (exit -1)",
          "Steam 启动失败（退出码 -1）" },
    };

    for (size_t i = 0; i < sizeof pairs / sizeof pairs[0]; ++i) {
        expect_translate(SPLASH_LOCALE_EN, pairs[i].src, pairs[i].src,
                         pairs[i].name);
        expect_translate(SPLASH_LOCALE_ZH_CN, pairs[i].src, pairs[i].zh,
                         pairs[i].name);
    }
}

static void test_translation_passthrough(void)
{
    /* EN always preserves the raw input, including whitespace. */
    expect_translate(SPLASH_LOCALE_EN, "  weird diagnostic  ",
                     "  weird diagnostic  ", "en raw whitespace");
    expect_translate(SPLASH_LOCALE_EN, "", "", "en empty");

    /* ZH passes through unknown diagnostics and existing Chinese unchanged.
       Only "Steam launch failed (exit <number>)" is rewritten; arbitrary
       diagnostics, including non-numeric exit text, stay raw. */
    expect_translate(SPLASH_LOCALE_ZH_CN, "Kernel panic - not syncing",
                     "Kernel panic - not syncing", "zh unknown diagnostic");
    expect_translate(SPLASH_LOCALE_ZH_CN, "Steam launch failed (exit abc)",
                     "Steam launch failed (exit abc)", "zh non-numeric exit raw");
    expect_translate(SPLASH_LOCALE_ZH_CN, "正在准备 Armada",
                     "正在准备 Armada", "zh already chinese");
    expect_translate(SPLASH_LOCALE_ZH_CN, "你好，世界",
                     "你好，世界", "zh arbitrary chinese");
    expect_translate(SPLASH_LOCALE_ZH_CN, "", "", "zh empty");

    /* A leading '!' stays in the translated line. */
    expect_translate(SPLASH_LOCALE_ZH_CN, "!Shutting down",
                     "!正在关机", "zh leading bang translated");
    expect_translate(SPLASH_LOCALE_EN, "!Shutting down",
                     "!Shutting down", "en leading bang preserved");
}

static void test_translation_buffer_guards(void)
{
    unsigned char guard = 0x7F;

    /* out_size == 0 must write nothing at all. */
    char zero[8];
    memset(zero, guard, sizeof zero);
    splash_translate_line(SPLASH_LOCALE_ZH_CN, "Shutting down", zero, 0);
    for (size_t i = 0; i < sizeof zero; ++i) {
        LABEL((unsigned char)zero[i] == guard, "out_size==0 writes nothing (zh)");
    }

    memset(zero, guard, sizeof zero);
    splash_translate_line(SPLASH_LOCALE_EN, "Preparing Armada", zero, 0);
    for (size_t i = 0; i < sizeof zero; ++i) {
        LABEL((unsigned char)zero[i] == guard, "out_size==0 writes nothing (en)");
    }

    /* out_size == 1 must leave only the terminator. */
    char one[8];
    memset(one, guard, sizeof one);
    splash_translate_line(SPLASH_LOCALE_ZH_CN, "Shutting down", one, 1);
    LABEL(one[0] == '\0', "out_size==1 writes only NUL");
    for (size_t i = 1; i < sizeof one; ++i) {
        LABEL((unsigned char)one[i] == guard, "out_size==1 does not overflow");
    }

    /* A small buffer is bounded and NUL terminated, with no overflow. */
    char small[16];
    memset(small, guard, sizeof small);
    splash_translate_line(SPLASH_LOCALE_ZH_CN,
                          "Applying update. Do not power off.", small, 5);
    LABEL(memchr(small, '\0', 5) != NULL, "small buffer NUL terminated (zh)");
    for (size_t i = 5; i < sizeof small; ++i) {
        LABEL((unsigned char)small[i] == guard, "small buffer no overflow (zh)");
    }

    memset(small, guard, sizeof small);
    splash_translate_line(SPLASH_LOCALE_EN, "Preparing Armada", small, 5);
    LABEL(memchr(small, '\0', 5) != NULL, "small buffer NUL terminated (en)");
    for (size_t i = 5; i < sizeof small; ++i) {
        LABEL((unsigned char)small[i] == guard, "small buffer no overflow (en)");
    }
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "i18n-test: usage: %s <writable-output-dir>\n",
                argv[0]);
        return 2;
    }

    test_locale_from_language();
    test_resolve_locale(argv[1]);
    test_translations();
    test_translation_passthrough();
    test_translation_buffer_guards();

    printf("i18n-test: all behavior checks passed\n");
    return 0;
}
