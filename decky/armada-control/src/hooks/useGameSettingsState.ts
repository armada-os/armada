import { useCallback } from "react";
import { waitForPendingSaves } from "../lib/configSaveQueue";
import type { RefObject } from "react";
import { getAppCompatTools, getProtonTools, resolveCompatState } from "../lib/steamCompat";
import type { CompatTool } from "../lib/steamCompat";
import { getGameResolution } from "../lib/steamSettings";
import type { Config } from "../types";
import { useBackendState } from "./useBackendState";

export interface InitialGameSettings {
  compatTools: CompatTool[];
  policy: {
    resolution: string;
    tools: CompatTool[];
    state: Awaited<ReturnType<typeof resolveCompatState>>;
    selection?: string;
  } | null;
}

export function useGameSettingsState(config: Config | null, host: RefObject<HTMLDivElement | null>, active: boolean) {
  const game = config?.selectedGame === undefined ? config?.game : config.selectedGame;
  const appid = game?.appid;
  const read = useCallback(async (): Promise<InitialGameSettings> => {
    await waitForPendingSaves();
    const [compatTools, policy] = await Promise.all([
      getProtonTools(),
      appid ? Promise.all([
        getGameResolution(appid),
        getAppCompatTools(appid),
        resolveCompatState(appid),
      ]).then(([resolution, tools, state]) => ({ resolution: resolution || "Default", tools, state })) : Promise.resolve(null),
    ]);
    return { compatTools, policy };
  }, [appid]);
  return useBackendState(read, 0, !config, host, active);
}
