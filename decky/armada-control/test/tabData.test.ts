import * as configSaveQueue from "../src/lib/configSaveQueue.ts";
import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./helpers/loadModule.ts";
import * as configMutation from "../src/lib/configMutation.ts";
import * as configSections from "../src/lib/configSections.ts";

const seeds: Record<string, any> = {
  getDeviceConfig: { panelCalibrationSupported: false, chargingFanSupported: true, chargingFanPwm: 50 },
  getControllerConfig: { gyro: { supported: false, enabled: false }, controllerType: "deck-uhid", controllerTypes: [], calibratedAt: null, hasCalibration: false },
  getProfilesConfig: { power: {}, powerDefaults: {}, freqLimits: {} },
  getExperimentalConfig: Object.fromEntries(configSections.experimentalConfigFields.map((field) => [field, false])),
  getAboutConfig: { osVersion: "OS", ablVersion: "ABL", sshEnabled: false },
  getRgb: { enabled: false }, getFansState: { fanCurves: {}, profiles: {} },
  getSleepLogsStatus: { enabled: false, directory: "/logs" }, getProtonTools: [],
};

function setup() {
  let config: any = null;
  let active = "Compatibility";
  let cursor = 0;
  let state: any;
  const slots: any[] = [];
  const effects = new Map<number, any>();
  let pending: Array<() => void> = [];
  const requests = new Map<string, Array<{ resolve: (value: any) => void; reject: (error: Error) => void }>>();
  const listeners = new Map<string, Set<() => void>>();
  const timers = new Map<number, () => void>();
  let timerId = 0;
  const events: any = {
    hidden: false,
    addEventListener: (name: string, callback: () => void) => {
      if (!listeners.has(name)) listeners.set(name, new Set());
      listeners.get(name)!.add(callback);
    },
    removeEventListener: (name: string, callback: () => void) => listeners.get(name)?.delete(callback),
    setInterval: (callback: () => void) => { timers.set(++timerId, callback); return timerId; },
    clearInterval: (id: number) => timers.delete(id),
  };
  events.document = events;
  const host = { current: { ownerDocument: { defaultView: events } } };
  const react = {
    useRef: (value: any) => slots[cursor++] ??= { current: value },
    useState: (value: any) => {
      const index = cursor++;
      if (!(index in slots)) slots[index] = typeof value === "function" ? value() : value;
      return [slots[index], (next: any) => { slots[index] = typeof next === "function" ? next(slots[index]) : next; }];
    },
    useCallback: (callback: any, dependencies: any[]) => {
      const index = cursor++;
      if (!slots[index] || !dependencies.every((value, i) => Object.is(value, slots[index].dependencies[i]))) slots[index] = { callback, dependencies };
      return slots[index].callback;
    },
    useEffect: (effect: () => any, dependencies: any[]) => {
      const index = cursor++;
      const previous = effects.get(index);
      if (previous && dependencies.every((value, i) => Object.is(value, previous.dependencies[i]))) return;
      pending.push(() => { previous?.cleanup?.(); effects.set(index, { dependencies, cleanup: effect() }); });
    },
  };
  const read = (name: string) => () => new Promise((resolve, reject) => {
    if (!requests.has(name)) requests.set(name, []);
    requests.get(name)!.push({ resolve, reject });
  });
  const backend = Object.fromEntries(Object.keys(seeds).map((name) => [name, read(name)]));
  const modules = new Map<string, any>();
  function load(name: string): any {
    if (modules.has(name)) return modules.get(name);
    const result = loadModule("hooks/" + name + ".ts", (id: string) => {
      if (id === "react") return react;
      if (id === "../backend") return backend;
      if (id === "../lib/configSections") return configSections;
      if (id === "../lib/configMutation") return configMutation;
      if (id === "../lib/configSaveQueue") return configSaveQueue;
      if (id === "../lib/steamCompat") return { getProtonTools: backend.getProtonTools };
      if (id === "../lib/steamSettings") return { getGameResolution: async () => "Default" };
      if (id === "./useDebouncedApply") return { waitForPendingApplies: async () => {} };
      if (id.startsWith("./")) return load(id.slice(2));
      throw Error(id);
      }, { window: { document: { hidden: true }, addEventListener: () => { throw Error("Wrong window"); } } });
    modules.set(name, result);
    return result;
  }
  const owner = load("useTabData");
  const setConfig = (next: any) => { config = typeof next === "function" ? next(config) : next; };
  const render = () => {
    cursor = 0;
    state = owner.useTabData(config, setConfig, active, host);
    const next = pending;
    pending = [];
    next.forEach((effect) => effect());
  };
  const settle = async () => { await new Promise((resolve) => setImmediate(resolve)); render(); };
  render();
  return {
    get state() { return state; }, requests, timers, listeners, settle, render,
    open: async () => { config = { tweaks: { global: {}, games: {} }, installedGames: [], rgbSupported: true }; render(); await settle(); },
    select: (tab: string) => { active = tab; render(); },
    resolve: (name: string, index = 0) => requests.get(name)![index].resolve(seeds[name]),
    reject: (name: string) => requests.get(name)![0].reject(new Error("offline")),
    unmount: () => { for (const effect of effects.values()) effect.cleanup?.(); },
  };
}

test("all tab payloads warm together without waiting for the first Game Settings read", async () => {
  const app = setup();
  assert.equal(app.requests.size, 0);
  await app.open();
  assert.deepEqual([...app.requests.keys()].sort(), Object.keys(seeds).sort());
  for (const name of Object.keys(seeds)) if (name !== "getProtonTools") app.resolve(name);
  await app.settle();
  assert.equal(app.state.game.loading, true);
  for (const name of ["device", "controller", "profiles", "experimental", "about", "rgb", "fans", "logs"]) assert.equal(app.state[name].loading, false, name);
  app.select("Profiles");
  assert.equal(app.state.profiles.loading, false);
  assert.equal(app.state.fans.loading, false);
  assert.ok(app.state.fans.value);
  assert.equal(app.timers.size, 1);
  app.select("About");
  assert.equal(app.state.about.loading, false);
  assert.equal(app.state.logs.loading, false);
  assert.equal(app.timers.size, 1);
  app.resolve("getProtonTools");
  await app.settle();
  app.select("Compatibility");
  assert.equal(app.state.game.loading, false);
  assert.equal(app.timers.size, 0);
  app.unmount();
  assert.ok([...app.listeners.values()].every((callbacks) => callbacks.size === 0));
});

test("an unfinished tab shares its warm read and another tab failure stays isolated", async () => {
  const app = setup();
  await app.open();
  app.resolve("getAboutConfig");
  app.resolve("getProtonTools");
  app.reject("getRgb");
  await app.settle();
  app.select("About");
  assert.equal(app.state.logs.loading, true);
  assert.equal(app.requests.get("getSleepLogsStatus")!.length, 1);
  app.resolve("getSleepLogsStatus");
  await app.settle();
  assert.equal(app.state.logs.loading, false);
  assert.equal(app.state.logs.value.directory, "/logs");
  assert.match(app.state.rgb.error, /offline/);
  assert.equal(app.state.game.loading, false);
  app.select("Controller");
  assert.equal(app.state.controller.loading, true);
  assert.equal(app.requests.get("getControllerConfig")!.length, 1);
  app.resolve("getControllerConfig");
  await app.settle();
  assert.equal(app.state.controller.loading, false);
  app.unmount();
});
