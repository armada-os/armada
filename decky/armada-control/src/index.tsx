import { definePlugin } from "@decky/api";
import { getCompatApplied, getConfig, getInstalledGames, saveCompatApplied } from "./backend";
import { Content } from "./Content";
import {
  applyControllerGlyphTheme,
  clearControllerGlyphTheme,
  normalizeControllerGlyphStyle,
} from "./lib/controllerGlyphs";
import {
  configureCompatPolicy,
  handledGameAppids,
  registerDownloadWatcher,
  sweepInstalledGames,
} from "./lib/steamCompat";

export default definePlugin(() => {
  let unregisterDownloadWatcher = () => {};
  const persistHandledGames = () => {
    saveCompatApplied(handledGameAppids()).catch(() => {});
  };
  let cancelled = false;
  const configPromise = getConfig();
  configPromise
    .then((config) => {
      if (cancelled) return;
      applyControllerGlyphTheme(
        config.controllerGlyphVariant,
        normalizeControllerGlyphStyle(
          config.tweaks?.global?.controllerGlyphStyle,
        ),
      );
    })
    .catch(() => {});
  const handledRequest = getCompatApplied()
    .then((appids) => ({ appids, loaded: true }))
    .catch(() => ({ appids: [] as string[], loaded: false }));
  Promise.all([configPromise, getInstalledGames(), handledRequest])
    .then(([config, games, handled]) => {
      if (cancelled) return;
      configureCompatPolicy(
        config.tweaks?.global?.windowsCompatTool,
        handled.loaded && config.tweaks?.global?.autoApplyCompat !== false,
        handled.appids,
      );
      const persist = handled.loaded ? persistHandledGames : () => {};
      unregisterDownloadWatcher = registerDownloadWatcher(persist);
      window.setTimeout(() => {
        if (cancelled) return;
        sweepInstalledGames(games.map((game) => game.appid))
          .then(persist)
          .catch(() => {});
      }, 3000);
    })
    .catch(() => {});
  return {
    name: "Armada Control",
    content: <Content />,
    onDismount() {
      cancelled = true;
      clearControllerGlyphTheme();
      unregisterDownloadWatcher();
    },
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M14 17H5" />
        <path d="M19 7h-9" />
        <circle cx="17" cy="17" r="3" />
        <circle cx="7" cy="7" r="3" />
      </svg>
    ),
    alwaysRender: true,
  };
});
