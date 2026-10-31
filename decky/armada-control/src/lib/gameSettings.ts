import type { GameTweak } from "../types";
import { FOLLOW_STEAM_COMPAT, USE_DEFAULT_COMPAT, compatSelection, type CompatState } from "./steamCompat";

export function gameCompatSelection(settings: GameTweak, state: CompatState | null, defaultTool: string, cached?: string): string {
  return settings.steamCompatTool ?? cached ?? compatSelection(state, defaultTool);
}

export function gameProfileEnabled(settings: GameTweak, tool: string, resolution: string): boolean {
  if (typeof settings.enabled === "boolean") return settings.enabled;
  if (Object.keys(settings).some((key) => key !== "name")) return true;
  return resolution !== "Default" || !!tool && tool !== USE_DEFAULT_COMPAT && tool !== FOLLOW_STEAM_COMPAT;
}

interface SteamGameSettings {
  readCompat: () => Promise<CompatState | null>;
  readResolution: () => Promise<string>;
  selectCompat: (selection: string) => Promise<void>;
  restoreCompat: (state: CompatState) => Promise<void>;
  writeResolution: (resolution: string) => Promise<void>;
  compatSelection: (state: CompatState) => string;
  persist?: (patch: Pick<GameTweak, "enabled" | "steamCompatTool" | "steamResolution">) => Promise<void>;
}

export async function changeGameProfile(
  settings: GameTweak,
  enabled: boolean,
  steam: SteamGameSettings,
): Promise<Pick<GameTweak, "enabled" | "steamCompatTool" | "steamResolution">> {
  const [compat, resolution] = await Promise.all([steam.readCompat(), steam.readResolution()]);
  if (!compat) throw new Error("Steam compatibility settings are unavailable");
  const patch = {
    enabled,
    steamCompatTool: settings.steamCompatTool ?? (enabled ? USE_DEFAULT_COMPAT : steam.compatSelection(compat)),
    steamResolution: settings.steamResolution ?? (enabled ? "Default" : resolution || "Default"),
  };
  try {
    await steam.selectCompat(enabled ? patch.steamCompatTool : USE_DEFAULT_COMPAT);
    await steam.writeResolution(enabled ? patch.steamResolution : "Default");
    await steam.persist?.(patch);
  } catch (error) {
    const restored = await Promise.allSettled([
      steam.restoreCompat(compat),
      steam.writeResolution(resolution || "Default"),
    ]);
    if (restored.some((result) => result.status === "rejected")) {
      throw new Error(`${String(error)}; Steam settings could not be restored`);
    }
    throw error;
  }
  return patch;
}
