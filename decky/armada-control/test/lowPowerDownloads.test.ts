import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./helpers/loadModule.ts";

function setup() {
  const settings: Record<string, boolean> = {
    system_enable_low_power_downloads: false,
    system_allow_battery_low_power_downloads: false,
  };
  const listeners = new Set<() => void>();
  const writes: Array<[string, boolean]> = [];
  let cleanups = 0;
  let response = Promise.resolve();

  const nativeSettings = {
    RegisterForSettingsArrayChanges: (callback: () => void) => {
      listeners.add(callback);
      return { unregister: () => { cleanups++; listeners.delete(callback); } };
    },
  };
  const exports = loadModule("lib/lowPowerDownloads.ts", {}, {
    queueMicrotask,
    window: {
      SteamClient: { Settings: nativeSettings },
      settingsStore: {
        GetClientSetting: (key: string) => [settings[key], (value: boolean) => { writes.push([key, value]); return response; }],
      },
    } });
  return {
    wait: (promise: Promise<void>) => { response = promise; },
    api: exports as typeof import("../src/lib/lowPowerDownloads.ts"), writes,
    notify: (next: Partial<typeof settings>) => {
      for (const listener of listeners) listener();
      Object.assign(settings, next);
    },
    get cleanups() { return cleanups; },
  };
}

test("download subscriptions publish Steam's settled state and stop after cleanup", async () => {
  const app = setup();
  const seen: Array<{ enabled: boolean; onBattery: boolean }> = [];
  const stop = app.api.subscribeLowPowerDownloadSettings(() => { seen.push({ ...app.api.getLowPowerDownloadSettings() }); });
  app.notify({ system_enable_low_power_downloads: true });
  assert.deepEqual(seen, []);
  await Promise.resolve();
  assert.deepEqual(seen, [{ enabled: true, onBattery: false }]);
  await app.api.setLowPowerDownloadsOnBattery(true);
  assert.equal(app.api.getLowPowerDownloadSettings().onBattery, true);
  app.notify({ system_allow_battery_low_power_downloads: true });
  await Promise.resolve();
  assert.deepEqual(seen.at(-1), { enabled: true, onBattery: true });
  const before = seen.length;
  app.notify({ system_enable_low_power_downloads: false });
  stop();
  await Promise.resolve();
  assert.equal(seen.length, before);
  assert.equal(app.cleanups, 1);
});

test("download writes retain the latest intent across subscribers and permit retry after failure", async () => {
  const app = setup();
  let finish!: () => void;
  app.wait(new Promise<void>((resolve) => { finish = resolve; }));
  const first = app.api.setLowPowerDownloadsEnabled(true);
  const latest = app.api.setLowPowerDownloadsEnabled(false);
  await Promise.resolve();
  assert.equal(app.writes.length, 1);
  assert.equal(app.api.getLowPowerDownloadSettings().enabled, false);
  let observed: any;
  const stop = app.api.subscribeLowPowerDownloadSettings(() => { observed = app.api.getLowPowerDownloadSettings(); });
  finish();
  await Promise.all([first, latest]);
  assert.equal(app.writes.length, 2);
  assert.equal(observed.enabled, false);
  app.wait(Promise.reject(new Error("native failure")));
  await assert.rejects(app.api.setLowPowerDownloadsEnabled(true), /native failure/);
  assert.equal(app.api.getLowPowerDownloadSettings().enabled, false);
  app.wait(Promise.resolve());
  await app.api.setLowPowerDownloadsEnabled(true);
  assert.equal(app.api.getLowPowerDownloadSettings().enabled, true);
  stop();
});
