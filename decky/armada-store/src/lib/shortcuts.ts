import { t } from "../i18n";
import type { LaunchSpec } from "../types";

const apps = () => window.SteamClient?.Apps;

export async function addToSteam(launch: LaunchSpec | null, existing?: number, onCreated?: (appid: number) => void): Promise<number> {
  const client = apps();
  if (!client?.AddShortcut) throw new Error(t("errors.shortcutApiUnavailable"));
  if (!launch) throw new Error(t("errors.noLaunchCommand"));
  const { name, exe, startDir, launchOptions } = launch;
  const appid = existing ?? Number(await client.AddShortcut(name, exe, startDir, launchOptions));
  if (!appid) throw new Error(t("errors.shortcutNotCreated"));
  onCreated?.(appid);
  // New shortcuts come up named after the executable; apply the real name after.
  try {
    client.SetShortcutName?.(appid, name);
  } catch (error) {
  }
  try {
    if (launchOptions) client.SetShortcutLaunchOptions?.(appid, launchOptions);
  } catch (error) {
  }
  if (launch.compatTool) {
    if (!client.SpecifyCompatTool) throw new Error(t("errors.compatibilitySettingsUnavailable"));
    await client.SpecifyCompatTool(appid, launch.compatTool);
  }
  if (launch.controllerTemplate) {
    try {
      await selectControllerTemplate(appid, launch.controllerTemplate);
    } catch (error) {
    }
  }
  return appid;
}

// Steam's layout browser lists nothing for the built-in controls, which take the Steam Deck's templates.
const STEAM_INPUT_SLOTS = 16;
const DECK_TEMPLATE_TYPES = [4, 100];

async function selectControllerTemplate(appid: number, template: string): Promise<void> {
  const input = window.SteamClient?.Input;
  if (!input?.GetConfigForAppAndController || !input.SetSelectedConfigForApp) return;
  const url = `template://controller_neptune_${template}.vdf`;
  for (let index = 0; index < STEAM_INPUT_SLOTS; index++) {
    const config = await input.GetConfigForAppAndController(appid, index);
    if (!config?.bConfigurationEnabled || !DECK_TEMPLATE_TYPES.includes(config.nControllerType)) continue;
    input.SetSelectedConfigForApp(appid, index, url, false, 0);
  }
}

export function removeFromSteam(appid: number): void {
  const client = apps();
  if (!client?.RemoveShortcut) throw new Error(t("errors.shortcutApiUnavailable"));
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
  throw new Error(t("errors.launchApiUnavailable"));
}
