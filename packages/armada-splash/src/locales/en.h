// English status catalog for armada-splash.
//
// The English table is a full catalog: every stable key used by any locale is
// present here, so a source line is always resolved through a real key rather
// than falling back to an untranslated string. Keys are shared with the other
// locale tables. Entries containing a "{...}" placeholder are matched by their
// literal prefix/suffix; all other entries match exactly.
#ifndef ARMADA_SPLASH_LOCALES_EN_H
#define ARMADA_SPLASH_LOCALES_EN_H

static const SplashMsg SPLASH_EN_CATALOG[] = {
    { "boot.preparing",          "Preparing Armada" },
    { "boot.startingDesktop",    "Starting Desktop" },
    { "steam.starting",          "Starting Steam" },
    { "steam.restarting",        "Restarting Steam" },
    { "steam.installing",        "Installing Steam" },
    { "steam.stillStarting",
      "Still starting. First boot installs Steam and can take a few minutes." },
    { "steam.waitingUnit",       "Waiting for {unit}" },
    { "steam.launchFailed",      "Steam launch failed (exit {code})" },
    { "shutdown.shuttingDown",   "Shutting down" },
    { "shutdown.restarting",     "Restarting" },
    { "shutdown.applyingUpdate", "Applying update. Do not power off." },
};

#endif // ARMADA_SPLASH_LOCALES_EN_H
