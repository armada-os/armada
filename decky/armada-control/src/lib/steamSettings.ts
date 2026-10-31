const GLOBAL_RESOLUTION_KEY = "gamescope_game_resolution_global";
let globalResolutionWrite: string | undefined;

export function getGlobalResolution(): string {
  const native = window.settingsStore?.GetClientSetting?.(GLOBAL_RESOLUTION_KEY)?.[0] || "Default";
  const written = globalResolutionWrite;
  if (written === undefined) return native;
  if (native === written) globalResolutionWrite = undefined;
  return written;
}

export async function setGlobalResolution(value: string): Promise<string> {
  const setting = window.settingsStore?.GetClientSetting?.(GLOBAL_RESOLUTION_KEY);
  const setter = setting?.[1];
  if (!setter) throw new Error("Steam settings are unavailable");
  await Promise.resolve(setter(value));
  globalResolutionWrite = value;
  return value;
}

const resolutionWrites = new Map<string, string>();

export async function getGameResolution(appid: string): Promise<string> {
  const native = await window.SteamClient?.Apps?.GetResolutionOverrideForApp?.(Number(appid)) || "Default";
  const written = resolutionWrites.get(appid);
  if (written === undefined) return native;
  if (native === written) resolutionWrites.delete(appid);
  return written;
}

export async function setGameResolution(appid: string, value: string): Promise<void> {
  const apps = window.SteamClient?.Apps;
  if (!apps?.SetAppResolutionOverride) throw new Error("Steam resolution settings are unavailable");
  await apps.SetAppResolutionOverride(Number(appid), value);
  resolutionWrites.set(appid, value);
}
