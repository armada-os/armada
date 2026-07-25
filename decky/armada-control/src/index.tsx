import { definePlugin } from "@decky/api";
import { getCompatApplied, getConfig, getInstalledGames, saveCompatApplied } from "./backend";
import { Content } from "./Content";
import { registerDisplayHdrRoutePatch } from "./lib/displayHdrRoutePatch";
import {
  configureCompatPolicy,
  handledGameAppids,
  registerDownloadWatcher,
  sweepInstalledGames,
} from "./lib/steamCompat";

export default definePlugin(() => {
  let unregisterDownloadWatcher = () => {};
  let unregisterDisplayHdrRoutePatch = () => {};
  const persistHandledGames = () => {
    saveCompatApplied(handledGameAppids()).catch(() => {});
  };
  let cancelled = false;
  const configPromise = getConfig();
  const discoverHdrCapability = async () => {
    const retryDelaysMs = [0, 250, 500, 1000, 2000, 4000, 8000];
    for (let attempt = 0; attempt < retryDelaysMs.length && !cancelled; attempt += 1) {
      const delayMs = retryDelaysMs[attempt];
      if (delayMs > 0) {
        await new Promise<void>((resolve) => window.setTimeout(resolve, delayMs));
      }
      if (cancelled) return;
      try {
        const config = attempt === 0 ? await configPromise : await getConfig();
        if (cancelled) return;
        if (!config.hdrCapable) continue;
        unregisterDisplayHdrRoutePatch = registerDisplayHdrRoutePatch();
        return;
      } catch (error) {
        console.warn("[Armada Control] HDR capability discovery retry", error);
      }
    }
    if (!cancelled) {
      console.warn("[Armada Control] HDR controls unavailable after bounded capability discovery");
    }
  };
  void discoverHdrCapability();
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
      unregisterDisplayHdrRoutePatch();
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
