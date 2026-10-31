import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./helpers/loadModule.ts";

test("resolution writes stay authoritative through stale getters, then release to external updates without accepting failures", async () => {

  let global = "Default";
  let game = "Native";
  let fail = false;
  const write = () => { if (fail) throw Error("unavailable"); };
  const api = loadModule("lib/steamSettings.ts", {}, { window: {
    settingsStore: { GetClientSetting: () => [global, write] },
    SteamClient: { Apps: { GetResolutionOverrideForApp: async () => game, SetAppResolutionOverride: write } },
  } });
  await api.setGlobalResolution("Native");
  await api.setGameResolution("1", "Default");
  assert.equal(api.getGlobalResolution(), "Native");
  assert.equal(await api.getGameResolution("1"), "Default");
  global = "Native";
  game = "Default";
  assert.equal(api.getGlobalResolution(), "Native");
  assert.equal(await api.getGameResolution("1"), "Default");
  global = game = "960x540";
  assert.equal(api.getGlobalResolution(), "960x540");
  assert.equal(await api.getGameResolution("1"), "960x540");
  fail = true;
  await assert.rejects(api.setGlobalResolution("Native"), /unavailable/);
  await assert.rejects(api.setGameResolution("1", "Default"), /unavailable/);
  assert.equal(api.getGlobalResolution(), "960x540");
  assert.equal(await api.getGameResolution("1"), "960x540");
});
