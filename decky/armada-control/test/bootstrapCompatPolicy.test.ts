import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./helpers/loadModule.ts";
import * as protonPolicy from "../src/lib/protonPolicy.ts";
import * as settingsQueue from "../src/lib/gameSettingsQueue.ts";
import { createSteamFixture as setup, experimental, stable } from "./helpers/steam.ts";

function bootstrap(api: ReturnType<typeof setup>["api"], installed: Promise<any[]>, config: any, previousTool = experimental) {
  const ready = Promise.withResolvers<void>(), finished = Promise.withResolvers<void>();
  const saved: Array<string | undefined> = [];
  // Run the delayed startup task without waiting on a real timer.
  let start!: () => void;
  loadModule("index.tsx", (id: string) => {
    if (id === "@decky/api") return { definePlugin: (create: () => any) => create() };
    if (id === "./Content") return { Content: "Content" };
    if (id === "./backend") return {
      getStartupConfig: async () => config, getStartupInstalledGames: () => installed,
      getCompatApplied: async () => ({ appids: [], protonDefault: previousTool }),
      saveCompatApplied: async (_appids: string[], defaultTool?: string) => { saved.push(defaultTool); finished.resolve(); },
    };
    if (id === "./lib/steamCompat") return api;
    if (id === "./lib/lockWatcher") return { registerLockWatcher: () => () => {} };
    if (id === "./lib/lowPowerDownloads") return { registerLowPowerDownloadEntry: () => () => {} };
    if (id === "./lib/protonPolicy") return protonPolicy;
    if (id === "./lib/gameSettingsQueue") return settingsQueue;
  }, { window: {
    App: { WaitForServicesInitialized: async () => {} },
    setTimeout: (callback: () => void) => { start = callback; ready.resolve(); },
  } });
  return { ready: ready.promise, finished: finished.promise, saved, start: async () => { await ready.promise; start(); } };
}

test("delayed startup preserves a new Follow Steam choice and untouched saved policies", async () => {
  const { api, game, writes } = setup();
  const games = [game(1), game(2), game(3)];
  const installed = Promise.withResolvers<any[]>();
  const startup = bootstrap(api, installed.promise, {
    tweaks: {
      global: { windowsCompatTool: experimental },
      games: { "2": { enabled: true, steamCompatTool: api.FOLLOW_STEAM_COMPAT } },
    },
    protonDefaults: [experimental],
  });
  await settingsQueue.runGameSettingsMutation(async () => {
    await api.specifyCompatTool("1", api.FOLLOW_STEAM_COMPAT);
    api.updateGameCompatProfile("1", { enabled: true, steamCompatTool: api.FOLLOW_STEAM_COMPAT });
    api.markCompatHandled("1");
  });
  installed.resolve(games);
  await startup.start();
  await startup.finished;
  assert.deepEqual(writes, [[1, ""], [3, experimental]]);
  assert.deepEqual(Array.from(api.handledGameAppids()), ["1", "2", "3"]);
});

test("bootstrap factory migration still runs when the global policy is unchanged", async () => {
  const { api, game, writes } = setup();
  const startup = bootstrap(api, Promise.resolve([game(1, stable, 250)]), {
    tweaks: { global: {}, games: {} }, protonDefaults: [experimental],
  }, stable);
  await startup.start();
  await startup.finished;
  assert.deepEqual(writes, [[1, experimental]]);
  assert.deepEqual(startup.saved, [experimental]);
});

test("bootstrap checks the revision inside its queue even when a choice changes away and back", async () => {
  const { api } = setup();
  const startup = bootstrap(api, Promise.resolve([]), {
    tweaks: { global: {}, games: {} }, protonDefaults: [experimental],
  }, stable);
  await startup.ready;
  const gate = Promise.withResolvers<void>();
  const blocked = settingsQueue.runGameSettingsMutation(() => gate.promise);
  await startup.start();
  await new Promise((resolve) => setImmediate(resolve));
  api.setWindowsCompatTool(stable);
  api.setWindowsCompatTool(undefined);
  gate.resolve();
  await blocked;
  await startup.finished;
  assert.deepEqual(startup.saved, [undefined]);
});
