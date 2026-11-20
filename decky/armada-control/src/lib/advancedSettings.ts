import { clone } from "./util";
import type { Tweaks } from "../types";

const keys = ["nice", "gamescopeCores", "gamescopeNice", "scheduler", "thunks", "turnipDriver"];

export function advancedSettings(settings: Record<string, any>, defaults: boolean): Record<string, any> {
  const names = defaults ? [...keys, "gamescopeVulkanRealtime"] : keys;
  return clone(Object.fromEntries(names.filter((key) => settings[key] !== undefined).map((key) => [key, settings[key]])));
}

export function advancedChanges(initial: Record<string, any>, draft: Record<string, any>) {
  return Object.fromEntries([...new Set([...Object.keys(initial), ...Object.keys(draft)])]
    .filter((key) => JSON.stringify(initial[key]) !== JSON.stringify(draft[key]))
    .map((key) => [key, draft[key]]));
}

export function patchGameSettings(tweaks: Tweaks, game: { appid: string; name: string } | null, patch: Record<string, any>): Tweaks {
  const next = clone(tweaks);
  const target = game
    ? next.games[game.appid] = { ...next.games[game.appid], name: game.name }
    : next.global;
  for (const [key, value] of Object.entries(patch)) {
    if (value === undefined) delete target[key];
    else target[key] = clone(value);
  }
  return next;
}
