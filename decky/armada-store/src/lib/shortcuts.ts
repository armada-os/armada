import type { LaunchSpec } from "../types";

const apps = () => window.SteamClient?.Apps;

export async function addToSteam(launch: LaunchSpec | null): Promise<number> {
  const client = apps();
  if (!client?.AddShortcut) throw new Error("Steam shortcut API unavailable");
  if (!launch) throw new Error("App has no launch command");
  const { name, exe, startDir, launchOptions } = launch;
  const appid = Number(await client.AddShortcut(name, exe, startDir, launchOptions));
  if (!appid) throw new Error("Steam did not create the shortcut");
  // New shortcuts come up named after the executable; apply the real name after.
  try {
    client.SetShortcutName?.(appid, name);
  } catch (error) {
  }
  try {
    if (launchOptions) client.SetShortcutLaunchOptions?.(appid, launchOptions);
  } catch (error) {
  }
  return appid;
}

export function removeFromSteam(appid: number): void {
  const client = apps();
  if (!client?.RemoveShortcut) throw new Error("Steam shortcut API unavailable");
  client.RemoveShortcut(appid);
}

// Non-Steam shortcuts launch by 64-bit gameid: (appid << 32) | 0x02000000.
export function shortcutGameId(appid: number): string {
  return ((BigInt(appid >>> 0) << 32n) | 0x02000000n).toString();
}

export function launchShortcut(appid: number): void {
  const gameid = shortcutGameId(appid);
  const client = apps();
  if (client?.RunGame) {
    client.RunGame(gameid, "", -1, 100);
    return;
  }
  const url = window.SteamClient?.URL;
  if (url?.ExecuteSteamURL) {
    url.ExecuteSteamURL("steam://rungameid/" + gameid);
    return;
  }
  throw new Error("Steam launch API unavailable");
}
