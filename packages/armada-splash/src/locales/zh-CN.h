// Simplified Chinese status catalog for armada-splash.
//
// Keys are independent and stable; they match SPLASH_EN_CATALOG key for key so
// a lookup by key never silently misses. Entries containing a "{...}"
// placeholder preserve that placeholder verbatim and are filled from the
// matched source. File is UTF-8 with LF line endings.
#ifndef ARMADA_SPLASH_LOCALES_ZH_CN_H
#define ARMADA_SPLASH_LOCALES_ZH_CN_H

static const SplashMsg SPLASH_ZH_CN_CATALOG[] = {
    { "boot.preparing",          "正在准备 Armada" },
    { "boot.startingDesktop",    "正在启动桌面" },
    { "steam.starting",          "正在启动 Steam" },
    { "steam.restarting",        "正在重启 Steam" },
    { "steam.installing",        "正在安装 Steam" },
    { "steam.stillStarting",
      "正在启动。首次启动需要安装 Steam，可能耗时几分钟。" },
    { "steam.waitingUnit",       "正在等待 {unit}" },
    { "steam.launchFailed",      "Steam 启动失败（退出码 {code}）" },
    { "shutdown.shuttingDown",   "正在关机" },
    { "shutdown.restarting",     "正在重启" },
    { "shutdown.applyingUpdate", "正在应用更新，请勿断电。" },
};

#endif // ARMADA_SPLASH_LOCALES_ZH_CN_H
