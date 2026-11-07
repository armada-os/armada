import { loadModule } from "./loadModule.ts";
import * as protonPolicy from "../../src/lib/protonPolicy.ts";
import * as compatTools from "../../src/lib/compatTools.ts";
import * as settingsQueue from "../../src/lib/gameSettingsQueue.ts";

export const experimental = "proton-experimental-arm64";
export const stable = "proton_11-arm64";

export function createSteamFixture(tools = [experimental, stable]) {
  const details = new Map<number, any>();
  const types = new Map<number, number>();
  const listeners = new Map<number, Set<(value: any) => void>>();
  const writes: Array<[number, string]> = [];
  const launchWrites: number[] = [];
  const launchOptionsWrites: string[] = [];
  let staleWrites = false;
  const failedWrites = new Set<number>();
  const exports = loadModule("lib/steamCompat.ts", (id: string) => {
    if (id === "./protonPolicy") return protonPolicy;
    if (id === "./compatTools") return compatTools;
    if (id === "./gameSettingsQueue") return settingsQueue;
    if (id === "./compatManager") return {
      getCompatManagerTools: async () => { throw new Error("Discovery unavailable"); },
    };
  }, { window: {
    setTimeout, clearTimeout, setInterval, clearInterval,
    appDetailsStore: { GetAppDetails: (appid: number) => details.get(appid) },
    appStore: { GetAppOverviewByAppID: (appid: number) => ({ app_type: types.get(appid) ?? 1 }) },
    SteamClient: {
      Settings: { GetGlobalCompatTools: async () => tools.map((name) => ({ name })) },
      Apps: {
        RegisterForAppDetails: (appid: number, callback: (value: any) => void) => {
          const callbacks = listeners.get(appid) || new Set();
          listeners.set(appid, callbacks);
          callbacks.add(callback);
          callback(details.get(appid));
          return { unregister: () => callbacks.delete(callback) };
        },
        SpecifyCompatTool: async (appid: number, name: string) => {
          writes.push([appid, name]);
          if (failedWrites.has(appid)) throw new Error("native write failed");
          if (staleWrites) return;
          const current = details.get(appid);
          current.strCompatToolName = name || stable;
          current.nCompatToolPriority = name ? 250 : 0;
          for (const callback of listeners.get(appid) || []) callback(current);
        },
        SetAppLaunchOptions: async (appid: number, value: string) => { launchWrites.push(appid); launchOptionsWrites.push(value); },
      },
    },
  } });
  function game(appid: number, tool = stable, priority = 0, type = 1) {
    types.set(appid, type);
    details.set(appid, { strCompatToolName: tool, nCompatToolPriority: priority, strLaunchOptions: "" });
    return { appid: String(appid) };
  }
  return { api: exports as typeof import("../../src/lib/steamCompat.ts"), game, writes, launchWrites, launchOptionsWrites, details,
    failedWrites,
    notifySnapshot: (appid: number, value: any) => { for (const callback of listeners.get(appid) || []) callback(value); },
    lagWrites: () => { staleWrites = true; },
    publish: (appid: number, tool: string, priority: number) => {
      const current = { ...details.get(appid), strCompatToolName: tool, nCompatToolPriority: priority };
      details.set(appid, current);
      for (const callback of listeners.get(appid) || []) callback(current);
    },
  };
}
