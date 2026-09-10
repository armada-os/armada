import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

import * as protonPolicy from "../src/lib/protonPolicy.ts";
import * as compatTools from "../src/lib/compatTools.ts";

const experimental = "proton-experimental-arm64";
const stable = "proton_11-arm64";
const source = readFileSync(new URL("../src/lib/steamCompat.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

function setup(tools = [experimental, stable]) {
  const details = new Map<number, any>();
  const types = new Map<number, number>();
  const listeners = new Map<number, Set<(value: any) => void>>();
  const writes: Array<[number, string]> = [];
  const launchWrites: number[] = [];
  const exports: any = {};
  runInNewContext(compiled, {
    exports,
    require: (id: string) => {
      if (id === "./protonPolicy") return protonPolicy;
      if (id === "./compatTools") return compatTools;
      if (id === "./compatManager") return {
        getCompatManagerTools: async () => { throw new Error("Discovery unavailable"); },
      };
      throw new Error(`Unexpected import: ${id}`);
    },
    window: {
      setTimeout, clearTimeout, setInterval, clearInterval,
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
            const current = details.get(appid);
            current.strCompatToolName = name || stable;
            current.nCompatToolPriority = name ? 250 : 0;
            for (const callback of listeners.get(appid) || []) callback(current);
          },
          SetAppLaunchOptions: async (appid: number) => { launchWrites.push(appid); },
        },
      },
    },
  });
  function game(appid: number, tool = stable, priority = 0, type = 1) {
    types.set(appid, type);
    details.set(appid, { strCompatToolName: tool, nCompatToolPriority: priority });
    return { appid: String(appid) };
  }
  return { api: exports as typeof import("../src/lib/steamCompat.ts"), game, writes, launchWrites };
}

test("global Follow Steam leaves new games and existing overrides alone, while adding the launch wrapper", async () => {
  const { api, game, writes, launchWrites } = setup();
  api.configureCompatPolicy(api.FOLLOW_STEAM_COMPAT, true, [], [experimental]);
  await api.sweepInstalledGames([game(1), game(2, experimental, 250), game(3, "steamlinuxruntime")]);
  assert.deepEqual(writes, []);
  assert.deepEqual(launchWrites.sort(), [1, 2, 3]);
  assert.deepEqual(Array.from(api.handledGameAppids()), ["1", "2", "3"]);
  assert.equal(protonPolicy.factoryDefaultTransition(api.FOLLOW_STEAM_COMPAT, true, stable, experimental), null);
});

test("changing a named default to Follow Steam clears only matching game pins", async () => {
  const { api, game, writes } = setup();
  game(1, experimental, 250);
  game(2, stable, 250);
  game(3, experimental, 0);
  game(4, experimental, 250, 4);
  api.configureCompatPolicy(experimental, true, [], [experimental]);
  await api.migrateWindowsCompatTool(["1", "2", "3", "4"], experimental, api.FOLLOW_STEAM_COMPAT);
  assert.deepEqual(writes, [[1, ""]]);
});

test("Follow Steam can clear known pins to a missing default without tool discovery", async () => {
  const { api, game, writes } = setup([]);
  game(1, "", 0);
  game(2, stable, 250);
  game(3, "", 0);
  await api.migrateWindowsCompatTool(["1", "2", "3"], "removed-proton", api.FOLLOW_STEAM_COMPAT, ["1", "2"]);
  assert.deepEqual(writes, [[1, ""]]);
});

test("Use Default clears the mapping when the global choice is Follow Steam", async () => {
  const { api, game, writes } = setup();
  game(1, experimental, 250);
  await api.specifyCompatTool("1", api.FOLLOW_STEAM_COMPAT);
  assert.deepEqual(writes, [[1, ""]]);
  assert.equal(api.compatSelection({ tool: stable, priority: 0 }, api.FOLLOW_STEAM_COMPAT), api.FOLLOW_STEAM_COMPAT);
});

test("resetting a game under Follow Steam clears its pin without discovery or a known pin state", async () => {
  const { api, game, writes } = setup([]);
  game(1, experimental, 250);
  api.configureCompatPolicy(api.FOLLOW_STEAM_COMPAT, true, [], [experimental]);
  assert.equal(await api.resetCompatToolToDefault("1", null), "");
  assert.deepEqual(writes, [[1, ""]]);
});

test("reset all under Follow Steam clears game pins and preserves tool apps", async () => {
  const { api, game, writes, launchWrites } = setup([]);
  game(1, experimental, 250);
  game(2, stable, 250);
  game(3, experimental, 250, 4);
  api.configureCompatPolicy(api.FOLLOW_STEAM_COMPAT, true, [], [experimental]);
  await api.resetAllGamePolicies(["1", "2", "3"], null);
  assert.deepEqual(writes, [[1, ""], [2, ""]]);
  assert.deepEqual(launchWrites.sort(), [1, 2]);
});

test("switching away from Follow Steam migrates handled Windows games and preserves pins and Linux routes", async () => {
  const { api, game, writes } = setup();
  const games = [game(1), game(2, stable, 250), game(3, "steamlinuxruntime"), game(4, ""), game(5, stable, 0, 4)];
  api.configureCompatPolicy(api.FOLLOW_STEAM_COMPAT, false, games.map(g => g.appid), [experimental]);
  await api.migrateWindowsCompatTool(games.map(g => g.appid), api.FOLLOW_STEAM_COMPAT, experimental);
  assert.deepEqual(writes, [[1, experimental]]);
  api.setAutoApplyCompat(true);
  await api.sweepInstalledGames([...games, game(6)]);
  assert.deepEqual(writes, [[1, experimental], [6, experimental]]);
});

test("a named default round trip through Follow Steam restores its game pins", async () => {
  const { api, game, writes } = setup();
  const games = [game(1, experimental, 250), game(2, stable, 250)];
  api.configureCompatPolicy(experimental, true, games.map(g => g.appid), [experimental]);
  await api.migrateWindowsCompatTool(["1", "2"], experimental, api.FOLLOW_STEAM_COMPAT);
  await api.migrateWindowsCompatTool(["1", "2"], api.FOLLOW_STEAM_COMPAT, experimental);
  assert.deepEqual(writes, [[1, ""], [1, experimental]]);
});

test("named defaults still migrate matching pins and honor Apply to New Games", async () => {
  const { api, game, writes } = setup();
  game(1, stable, 250);
  api.configureCompatPolicy(stable, false, [], [experimental]);
  await api.migrateWindowsCompatTool(["1"], stable, experimental);
  await api.sweepInstalledGames([game(2)]);
  assert.deepEqual(writes, [[1, experimental]]);
});
