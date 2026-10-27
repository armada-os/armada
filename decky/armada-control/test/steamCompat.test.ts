import assert from "node:assert/strict";
import test from "node:test";
import * as protonPolicy from "../src/lib/protonPolicy.ts";
import * as settingsQueue from "../src/lib/gameSettingsQueue.ts";
import { createSteamFixture as setup, experimental, stable } from "./helpers/steam.ts";

test("failed history reads cannot replace unknown saved IDs", async () => {
  const { api } = setup();
  let writes = 0;
  api.markCompatHandled("1");
  const pending = api.persistHandledGames(async () => { writes++; });
  api.initializeHandledGames(null);
  await pending;
  await api.persistHandledGames(async () => { writes++; });
  assert.equal(writes, 0);
});

test("handled history saves finish in order and snapshot IDs when their turn starts", async () => {
  const { api } = setup();
  api.initializeHandledGames([]);
  api.markCompatHandled("1");
  const { promise: pending, resolve: release } = Promise.withResolvers<void>();
  const writes: string[][] = [];
  const first = api.persistHandledGames(async (appids) => {
    await pending;
    writes.push([...appids]);
  });
  await new Promise<void>((resolve) => { setImmediate(resolve); });
  const latest = api.persistHandledGames(async (appids) => { writes.push([...appids]); });
  api.markCompatHandled("2");
  await new Promise<void>((resolve) => { setImmediate(resolve); });
  assert.deepEqual(writes, []);
  release();
  await Promise.all([first, latest]);
  assert.deepEqual(writes, [["1"], ["1", "2"]]);
});

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

test("current profile policy protects restored explicit choices from queued global migrations", async () => {
  const { api, game, writes } = setup();
  game(1, stable, 250);
  api.configureCompatPolicy(stable, true, ["1"], [stable], { "1": { enabled: false, steamCompatTool: stable } });
  const { promise: pending, resolve: release } = Promise.withResolvers<void>();
  const restoring = settingsQueue.runGameSettingsMutation(async () => {
    await pending;
    await api.specifyCompatTool("1", stable);
    api.setGameCompatProfiles({ "1": { enabled: true, steamCompatTool: stable } });
  });
  const migration = settingsQueue.runGameSettingsMutation(() => api.migrateWindowsCompatTool(["1"], stable, experimental));
  release();
  await Promise.all([restoring, migration]);
  assert.deepEqual(writes, [[1, stable]]);
});

test("resetting a game under Follow Steam clears its pin without discovery or a known pin state", async () => {
  const { api, game, writes } = setup([]);
  game(1, experimental, 250);
  api.configureCompatPolicy(api.FOLLOW_STEAM_COMPAT, true, [], [experimental]);
  assert.equal(await api.resetCompatToolToDefault("1", null), "");
  assert.deepEqual(writes, [[1, ""]]);
  api.setWindowsCompatTool(experimental);
  await assert.rejects(api.resetCompatToolToDefault("1", null), /Steam compatibility settings are unavailable/);
  assert.deepEqual(writes, [[1, ""]]);
});

test("reset all under Follow Steam clears game pins and preserves tool apps", async () => {
  const { api, game, writes, launchWrites, failedWrites } = setup([]);
  game(1, experimental, 250);
  game(2, stable, 250);
  game(3, experimental, 250, 4);
  api.configureCompatPolicy(api.FOLLOW_STEAM_COMPAT, true, [], [experimental]);
  const appids = await api.resolveProfileAppids(["1", "2", "3"]);
  await api.resetAllGamePolicies(appids, null);
  assert.deepEqual(writes, [[1, ""], [2, ""]]);
  assert.deepEqual(launchWrites.sort(), [1, 2]);
  failedWrites.add(1);
  failedWrites.add(2);
  await assert.rejects(api.resetAllGamePolicies(appids, null), (error) => {
    assert.match(String(error), /1: Error: native write failed/);
    assert.match(String(error), /2: Error: native write failed/);
    return true;
  });
  await assert.rejects(api.resetCompatToolToDefault("3"), /Steam game details are unavailable/);
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

test("failed global propagation reports errors and retrying the same choice repairs only unchanged failed titles", async () => {
  const app = setup([stable, experimental, "external-proton"]);
  for (const appid of [1, 2, 3, 4]) app.game(appid, stable, 250);
  app.api.configureCompatPolicy(stable, true, [], [stable]);
  for (const appid of [2, 3, 4]) app.failedWrites.add(appid);
  await assert.rejects(app.api.migrateWindowsCompatTool(["1", "2", "3", "4"], stable, experimental), /Could not apply/);
  app.failedWrites.clear();
  app.publish(3, "external-proton", 250);
  app.api.updateGameCompatProfile("4", { enabled: true, steamCompatTool: stable });
  const before = app.writes.length;
  await app.api.migrateWindowsCompatTool(["1", "2", "3", "4"], experimental, experimental);
  assert.deepEqual(app.writes.slice(before), [[2, experimental]]);
});

test("partial cached app details wait for the field being read rather than fabricating defaults", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "setInterval"] });
  const app = setup();
  app.game(1);
  app.details.get(1).strCompatToolName = undefined;
  const compatibility = app.api.resolveCompatState("1");
  await new Promise((resolve) => setImmediate(resolve));
  app.publish(1, experimental, 250);
  assert.equal((await compatibility)?.tool, experimental);
  app.details.get(1).strLaunchOptions = undefined;
  const wrapping = app.api.applyLaunchWrapperToGame("1");
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(app.launchWrites, []);
  app.details.get(1).strLaunchOptions = "--user-option";
  app.publish(1, experimental, 250);
  assert.equal(await wrapping, true);
  assert.ok(app.launchOptionsWrites[0].endsWith("--user-option"));
  app.game(2);
  app.details.get(2).strLaunchOptions = undefined;
  const unavailable = app.api.applyLaunchWrapperToGame("2");
  await new Promise((resolve) => setImmediate(resolve));
  t.mock.timers.tick(1500);
  assert.equal(await unavailable, false);
  assert.deepEqual(app.launchWrites, [1]);
});

test("late native snapshots cannot resurrect a cleared Proton pin and closed subscriptions stay silent", async () => {
  const app = setup();
  app.game(1, stable, 250);
  const seen: Array<{ tool: string; priority: number }> = [];
  const unsubscribe = app.api.subscribeCompatState("1", (state) => { if (state) seen.push(state); });
  await Promise.resolve();
  const stale = { ...app.details.get(1) };
  await app.api.specifyCompatTool("1", "");
  await app.api.resolveCompatState("1");
  seen.length = 0;
  app.notifySnapshot(1, stale);
  await Promise.resolve();
  assert.equal(seen.at(-1)?.priority, 0);
  const updated = { ...stale, strCompatToolName: experimental };
  app.notifySnapshot(1, updated);
  app.details.set(1, updated);
  await Promise.resolve();
  assert.equal(seen.at(-1)?.tool, experimental);
  const count = seen.length;
  app.notifySnapshot(1, stale);
  unsubscribe();
  await Promise.resolve();
  assert.equal(seen.length, count);
});
