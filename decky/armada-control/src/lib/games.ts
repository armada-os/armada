import { Router } from "@decky/ui";
import { isGameApp, isNonSteamApp } from "./steamCompat";
import { t } from "../i18n";
import type { Config, DropdownChoice, GameRef } from "../types";

export function gameDisplayName(game: GameRef | null | undefined): string {
  if (!game?.appid) return "";
  return game.name || t("App {id}", { id: game.appid });
}

export function availableGames(config: Config): GameRef[] {
  const games = new Map<string, GameRef>();
  for (const game of config.installedGames || []) {
    if (game?.appid && (game.nonSteam || isGameApp(game.appid))) {
      games.set(String(game.appid), {
        appid: String(game.appid),
        name: game.name || t("App {id}", { id: game.appid }),
        nonSteam: Boolean(game.nonSteam),
      });
    }
  }
  return Array.from(games.values()).sort((a, b) => gameDisplayName(a).localeCompare(gameDisplayName(b)));
}

export function editTargetOptions(config: Config): DropdownChoice[] {
  return [
    { data: "", label: t("Default") },
    ...availableGames(config).map((game) => ({ data: game.appid, label: gameDisplayName(game) })),
  ];
}

export function currentGame(): GameRef | null {
  const running = (Router as any)?.MainRunningApp || window.Router?.MainRunningApp;
  const appid = running?.appid;
  if (!appid) return null;
  const id = String(appid);
  let name = running?.display_name || running?.displayName || "";
  try {
    const details: any = window.appDetailsStore?.GetAppDetails?.(Number(id));
    name = details?.strDisplayName || details?.strName || details?.name || name;
  } catch (error) {
  }
  return { appid: id, name: name || t("App {id}", { id }), nonSteam: isNonSteamApp(id) };
}
