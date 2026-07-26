import assert from "node:assert/strict";
import test from "node:test";
import {
  AutoHdrPreferenceCoordinator,
  resolveAutoHdrPreference,
  resolveSteamAutoHdrScope,
} from "../src/lib/autoHdrPreferenceCoordinatorCore.ts";

const runtime = (enabled) => ({
  autoHdrEnabled: enabled,
  autoHdrMode: 2,
  autoHdrEffectiveMode: enabled ? 2 : 0,
});

const snapshot = ({
  scope = "global",
  appId = null,
  global = { enabled: true },
  override = null,
  runtimeEnabled = false,
} = {}) => ({
  version: 2,
  global,
  override,
  scope,
  appId,
  resolved: resolveAutoHdrPreference(global, override),
  runtime: runtime(runtimeEnabled),
});

const flush = () => new Promise((resolve) => setImmediate(resolve));

test("per-game enabled overrides inherit the global enabled preference", () => {
  const global = { enabled: true };
  assert.deepEqual(resolveAutoHdrPreference(global, null), global);
  assert.deepEqual(resolveAutoHdrPreference(global, { enabled: false }), {
    enabled: false,
  });
});

test("Steam game scope requires matching profile IDs and real running AppID", () => {
  const store = { nCurrentGameID: 42, nActiveProfileGameID: "42" };
  assert.deepEqual(resolveSteamAutoHdrScope(store, {
    MainRunningApp: { AppID: 42 },
  }), { scope: "game", appId: "42" });
  assert.deepEqual(resolveSteamAutoHdrScope({
    ...store,
    nActiveProfileGameID: 41,
  }, { MainRunningApp: { AppID: 42 } }), { scope: "global", appId: null });
  assert.deepEqual(resolveSteamAutoHdrScope(store, {
    MainRunningApp: { AppID: 41 },
  }), { scope: "global", appId: null });
  assert.deepEqual(resolveSteamAutoHdrScope({
    nCurrentGameID: 769,
    nActiveProfileGameID: 769,
  }, { MainRunningApp: { AppID: 769 } }), { scope: "global", appId: null });
});

test("preference writes are serialized and carry the current active scope", async () => {
  let active = 0;
  let maxActive = 0;
  const calls = [];
  const coordinator = new AutoHdrPreferenceCoordinator({
    resolveScope: () => ({ scope: "game", appId: "42" }),
    read: async () => snapshot({ scope: "game", appId: "42" }),
    reconcile: async () => snapshot({ scope: "game", appId: "42" }),
    update: async (targetScope, targetAppId, activeScope, activeAppId, patch) => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      calls.push({ targetScope, targetAppId, activeScope, activeAppId, patch });
      await flush();
      active -= 1;
      return snapshot({
        scope: "game",
        appId: "42",
        override: patch,
        runtimeEnabled: patch.enabled ?? true,
      });
    },
  });

  await Promise.all([
    coordinator.updatePreference("game", "42", { enabled: false }),
    coordinator.updatePreference("game", "42", { enabled: true }),
  ]);

  assert.equal(maxActive, 1);
  assert.deepEqual(calls.map((call) => call.patch), [
    { enabled: false },
    { enabled: true },
  ]);
  assert.ok(calls.every((call) =>
    call.activeScope === "game" && call.activeAppId === "42"));
});

test("stale AppID response is discarded and reconciled to the new running game", async () => {
  let activeScope = { scope: "game", appId: "10" };
  let resolveFirst;
  const calls = [];
  const published = [];
  const scheduled = [];
  const coordinator = new AutoHdrPreferenceCoordinator({
    resolveScope: () => activeScope,
    read: async (scope, appId) => snapshot({ scope, appId }),
    reconcile: (scope, appId) => {
      calls.push(appId);
      if (calls.length === 1) {
        return new Promise((resolve) => { resolveFirst = resolve; });
      }
      return Promise.resolve(snapshot({ scope, appId, runtimeEnabled: true }));
    },
    update: async () => snapshot(),
    publishRuntime: (value) => published.push(value.appId),
    schedule: (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancel: () => {},
  });

  coordinator.start();
  await flush();
  activeScope = { scope: "game", appId: "20" };
  resolveFirst(snapshot({ scope: "game", appId: "10", runtimeEnabled: true }));
  await flush();
  await flush();

  assert.deepEqual(calls, ["10", "20"]);
  assert.deepEqual(published, ["20"]);
  assert.equal(coordinator.getSnapshot().preferences.appId, "20");
  coordinator.stop();
});

test("stopping prevents a stale response from scheduling another request", async () => {
  let activeScope = { scope: "game", appId: "10" };
  let resolveFirst;
  const calls = [];
  const coordinator = new AutoHdrPreferenceCoordinator({
    resolveScope: () => activeScope,
    read: async (scope, appId) => snapshot({ scope, appId }),
    reconcile: (scope, appId) => {
      calls.push(appId);
      return new Promise((resolve) => { resolveFirst = resolve; });
    },
    update: async () => snapshot(),
    schedule: () => 1,
    cancel: () => {},
  });

  coordinator.start();
  await flush();
  activeScope = { scope: "game", appId: "20" };
  coordinator.stop();
  resolveFirst(snapshot({ scope: "game", appId: "10", runtimeEnabled: true }));
  await flush();
  await flush();

  assert.deepEqual(calls, ["10"]);
});

test("HDR off then ready restores saved AutoHDR once without retries", async () => {
  let activation = "off";
  const calls = [];
  const scheduled = [];
  let activationListener;
  const coordinator = new AutoHdrPreferenceCoordinator({
    resolveScope: () => ({ scope: "game", appId: "42" }),
    activationState: () => activation,
    subscribeActivation: (listener) => {
      activationListener = listener;
      return () => { activationListener = undefined; };
    },
    read: async (scope, appId) => {
      calls.push({ operation: "read", activation, scope, appId });
      return snapshot({
        scope,
        appId,
        override: { enabled: true },
        runtimeEnabled: false,
      });
    },
    reconcile: async (scope, appId) => {
      calls.push({ operation: "reconcile", activation, scope, appId });
      return snapshot({
        scope,
        appId,
        override: { enabled: true },
        runtimeEnabled: activation === "ready",
      });
    },
    update: async () => snapshot(),
    schedule: (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancel: () => {},
  });

  coordinator.start();
  await flush();
  assert.equal(calls.length, 1);
  assert.equal(coordinator.getSnapshot().preferences.resolved.enabled, true);
  assert.equal(coordinator.getSnapshot().preferences.runtime.autoHdrEnabled, false);

  activation = "waiting";
  activationListener();
  await flush();
  assert.equal(calls.length, 1);

  activation = "ready";
  activationListener();
  await flush();
  assert.equal(calls.length, 2);
  assert.deepEqual(calls.map((call) => call.operation), ["read", "reconcile"]);
  assert.equal(coordinator.getSnapshot().preferences.runtime.autoHdrEnabled, true);
  assert.equal(coordinator.getSnapshot().preferences.runtime.autoHdrMode, 2);
  coordinator.stop();
});
