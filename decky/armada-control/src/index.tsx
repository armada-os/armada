import { definePlugin } from "@decky/api";
import { getCompatApplied, getStartupConfig, getStartupInstalledGames, saveCompatApplied } from "./backend";
import { Content } from "./Content";
import {
  configureCompatPolicy,
  defaultWindowsCompatTool,
  getProtonTools,
  getCompatPolicyRevision,
  initializeHandledGames,
  migrateWindowsCompatTool,
  persistHandledGames as persistCompatHandledGames,
  registerDownloadWatcher,
  sweepInstalledGames,
} from "./lib/steamCompat";
import { factoryDefaultTransition } from "./lib/protonPolicy";
import { registerLockWatcher } from "./lib/lockWatcher";
import { registerLowPowerDownloadEntry } from "./lib/lowPowerDownloads";
import { runGameSettingsMutation } from "./lib/gameSettingsQueue";

export default definePlugin(() => {
  let unregisterDownloadWatcher = () => {};
  const unregisterLockWatcher = registerLockWatcher();
  const unregisterLowPowerDownloadEntry = registerLowPowerDownloadEntry();
  const persistHandledGames = () => {
    persistCompatHandledGames(saveCompatApplied).catch(() => {});
  };
  let cancelled = false;
  const startupPolicyRevision = getCompatPolicyRevision();
  const handledRequest = getCompatApplied()
    .then((state) => {
      initializeHandledGames(state.appids);
      return { state, loaded: true };
    })
    .catch(() => {
      initializeHandledGames(null);
      return { state: { appids: [] as string[], protonDefault: "" }, loaded: false };
    });
  Promise.all([getStartupConfig(), getStartupInstalledGames(), handledRequest])
    .then(async ([config, games, handled]) => {
      await (window as any).App.WaitForServicesInitialized();
      if (cancelled) return;
      const explicitTool = config.tweaks?.global?.windowsCompatTool;
      const startupPolicyUnchanged = getCompatPolicyRevision() === startupPolicyRevision;
      configureCompatPolicy(
        explicitTool,
        handled.loaded && config.tweaks?.global?.autoApplyCompat !== false,
        [...handled.state.appids, ...Object.entries(config.tweaks.games)
          .filter(([, game]) => game.enabled !== false && !!game.steamCompatTool)
          .map(([appid]) => appid)],
        config.protonDefaults,
        config.tweaks.games,
      );
      const initialPolicyRevision = getCompatPolicyRevision();
      const persist = handled.loaded ? persistHandledGames : () => {};
      unregisterDownloadWatcher = registerDownloadWatcher(persist);
      window.setTimeout(() => {
        void (async () => {
          if (cancelled) return;
          await sweepInstalledGames(games);
          if (cancelled) return;
          if (handled.loaded && !explicitTool && startupPolicyUnchanged) {
            const tools = await getProtonTools();
            if (cancelled) return;
            const nextTool = defaultWindowsCompatTool(tools, config.protonDefaults);
            const transition = factoryDefaultTransition(
              explicitTool, handled.loaded, handled.state.protonDefault, nextTool,
            );
            if (transition) {
              try {
                const applied = await runGameSettingsMutation(async () => {
                  // Recheck after queued edits, including a choice changed away and back.
                  if (cancelled || getCompatPolicyRevision() !== initialPolicyRevision) return false;
                  if (transition.oldTool !== transition.newTool) {
                    await migrateWindowsCompatTool(
                      games.filter((game) => !game.nonSteam).map((game) => game.appid),
                      transition.oldTool,
                      transition.newTool,
                    );
                  }
                  if (cancelled) return false;
                  await persistCompatHandledGames((appids) => saveCompatApplied(appids, transition.newTool));
                  return true;
                });
                if (applied) return;
              } catch (error) {
              }
            }
          }
          persist();
        })().catch(() => {});
      }, 3000);
    })
    .catch(() => {});
  return {
    name: "Armada Control",
    content: <Content />,
    onDismount() {
      cancelled = true;
      unregisterDownloadWatcher();
      unregisterLockWatcher();
      unregisterLowPowerDownloadEntry();
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
