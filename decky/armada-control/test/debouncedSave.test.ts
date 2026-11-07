import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./helpers/loadModule.ts";
import { configChanges } from "../src/lib/configPatch.ts";
import { configFieldRevision, configPathChanged, markConfigFieldChange } from "../src/lib/configMutation.ts";

function setup(initial = { global: { nice: 0 }, games: {} } as any, sharedQueue?: any) {
  const queue = sharedQueue || loadModule("lib/configSaveQueue.ts", {});
  const slots: any[] = [];
  const effects = new Map<number, { dependencies: any[]; cleanup?: () => void }>();
  const timers = new Map<number, () => void>();
  const calls: Array<{ value: any; result: ReturnType<typeof Promise.withResolvers> }> = [];
  const errors: unknown[] = [];
  const snapshot = { current: JSON.stringify(initial) };
  let config: any = { tweaks: structuredClone(initial), marker: "original" };
  let pending: Array<() => void> = [];
  let cursor = 0;
  let timerId = 0;
  let saveNow: (update: (value: any) => any) => Promise<any>;
  const setConfig = (update: any) => { config = typeof update === "function" ? update(config) : update; };
  const api = loadModule("hooks/useDebouncedSave.ts", {
    "../lib/configMutation": { configFieldRevision, configPathChanged },
    "../lib/configSaveQueue": queue,
    react: {
      useRef: (initial: any) => {
        const index = cursor++;
        if (!(index in slots)) slots[index] = { current: initial };
        return slots[index];
      },
      useCallback: (callback: any) => {
        const index = cursor++;
        if (!(index in slots)) slots[index] = callback;
        return slots[index];
      },
      useEffect: (effect: () => (() => void) | undefined, dependencies: any[]) => {
        const index = cursor++;
        const previous = effects.get(index);
        if (previous && dependencies.every((value, i) => Object.is(value, previous.dependencies[i]))) return;
        pending.push(() => {
          previous?.cleanup?.();
          effects.set(index, { dependencies, cleanup: effect() });
        });
      },
    },
  }, { window: {
    setTimeout: (callback: () => void) => { const id = ++timerId; timers.set(id, callback); return id; },
    clearTimeout: (id: number) => timers.delete(id),
  } });
  function render() {
    cursor = 0;
    saveNow = api.useDebouncedSave({ config, snapshot, setConfig,
      save: (value: any) => {
        const result = Promise.withResolvers<any>();
        calls.push({ value: structuredClone(value), result });
        return result.promise;
      }, onError: (error: unknown) => { errors.push(error); },
    });
    const current = pending;
    pending = [];
    for (const effect of current) effect();
  }
  render();
  return {
    calls, errors, snapshot, render, setConfig, queue,
    get config() { return config; },
    get timers() { return timers.size; },
    save: (update: (value: any) => any) => saveNow(update),
    edit: (update: (config: any) => any) => {
      const before = structuredClone(config.tweaks);
      config = update(config);
      const changes = configChanges(before, config.tweaks);
      if (changes.length) markConfigFieldChange(setConfig, "tweaks", changes.map((change) => change.path));
      render();
    },
    flush: () => { const current = [...timers.values()]; timers.clear(); for (const run of current) run(); },
    succeed: (index: number, tweaks = calls[index].value) => calls[index].result.resolve({ tweaks, marker: "backend" }),
    settle: async () => { await new Promise((resolve) => setImmediate(resolve)); render(); },
    unmount: () => { for (const effect of effects.values()) effect.cleanup?.(); },
  };
}

const changeNice = (nice: number) => (tweaks: any) => ({ ...tweaks, global: { ...tweaks.global, nice } });

test("manual saving waits for an automatic save and computes its update from the latest config", async () => {
  const app = setup();
  app.edit((current) => ({ ...current, tweaks: { ...current.tweaks, global: { ...current.tweaks.global, env: { A: "1" } } } }));
  app.flush();
  await app.settle();
  const saving = app.save(changeNice(-4));
  app.edit((current) => ({ ...current, tweaks: { ...current.tweaks, games: { "1": { name: "Latest game" } } } }));
  await app.settle();
  assert.equal(app.calls.length, 1);
  app.succeed(0);
  await app.settle();
  assert.equal(app.calls.length, 2);
  assert.equal(app.calls[1].value.global.env.A, "1");
  assert.equal(app.calls[1].value.games["1"].name, "Latest game");
  assert.equal(app.calls[1].value.global.nice, -4);
  app.succeed(1);
  await saving;
  assert.equal(app.config.tweaks.global.nice, -4);
  assert.equal(app.config.marker, "original");
});

test("successful manual saves merge changed leaves and preserve newer unrelated edits", async () => {
  const app = setup({ global: { nice: 0, scheduler: "old", thunks: { Vulkan: true, GL: true } }, games: { "1": { nice: 1 } } });
  const saving = app.save((tweaks) => {
    delete tweaks.global.scheduler;
    tweaks.global.nice = -3;
    tweaks.global.thunks.Vulkan = false;
    return tweaks;
  });
  await app.settle();
  app.edit((current) => ({ ...current, marker: "newer", tweaks: { ...current.tweaks,
    global: { ...current.tweaks.global, thunks: { ...current.tweaks.global.thunks, GL: false }, env: { NEW: "1" } },
    games: { ...current.tweaks.games, "2": { nice: 2 } },
  } }));
  const saved = app.calls[0].value;
  saved.global.env = JSON.parse('{"__proto__":"backend"}');
  app.succeed(0, saved);
  await saving;
  assert.equal(Object.hasOwn(app.config.tweaks.global.env, "__proto__"), true);
  assert.equal(app.config.tweaks.global.env.__proto__, "backend");
  assert.equal(app.config.tweaks.global.nice, -3);
  assert.equal("scheduler" in app.config.tweaks.global, false);
  assert.equal(app.config.tweaks.global.thunks.Vulkan, false);
  assert.equal(app.config.tweaks.global.thunks.GL, false);
  assert.equal(app.config.tweaks.global.env.NEW, "1");
  assert.equal(app.config.tweaks.games["2"].nice, 2);
  assert.equal(app.config.marker, "newer");
  assert.equal(app.timers, 1);
  app.flush();
  await app.settle();
  app.succeed(1);
  await app.settle();
});

test("automatic saves preserve edits made during their request and stop retrying identical failures", async () => {
  const app = setup();
  app.edit((current) => ({ ...current, tweaks: changeNice(-1)(current.tweaks) }));
  app.flush();
  await app.settle();
  app.edit((current) => ({ ...current, tweaks: changeNice(-2)(current.tweaks) }));
  app.succeed(0, { global: { nice: -1, normalized: true }, games: {} });
  await app.settle();
  assert.equal(app.config.tweaks.global.nice, -2);
  assert.equal(app.config.tweaks.global.normalized, true);
  app.flush();
  await app.settle();
  app.calls[1].result.reject(new Error("auto failed"));
  await app.settle();
  assert.equal(app.errors.length, 1);
  assert.equal(app.timers, 0);
});

test("a newer choice changed away and back survives a successful manual save", async () => {
  const app = setup();
  const saving = app.save(changeNice(-5));
  await app.settle();
  app.edit((current) => ({ ...current, tweaks: changeNice(-3)(current.tweaks) }));
  app.edit((current) => ({ ...current, tweaks: changeNice(0)(current.tweaks) }));
  app.succeed(0);
  await saving;
  assert.equal(app.config.tweaks.global.nice, 0);
  app.flush();
  await app.settle();
  assert.equal(app.calls[1].value.global.nice, 0);
  app.succeed(1);
  await app.settle();
});

test("closed and reopened hook owners share a persistence barrier and the confirmed baseline", async () => {
  const previous = setup();
  previous.edit((current) => ({ ...current, tweaks: changeNice(-6)(current.tweaks) }));
  previous.unmount();
  let reopened = false;
  const startup = previous.queue.waitForPendingSaves().then(() => { reopened = true; });
  await previous.settle();
  assert.equal(reopened, false);
  previous.succeed(0);
  await startup;
  const current = setup(previous.calls[0].value, previous.queue);
  current.edit((config) => ({ ...config, tweaks: { ...config.tweaks, games: { "7": { enabled: true } } } }));
  current.flush();
  await current.settle();
  assert.equal(current.calls[0].value.global.nice, -6);
  assert.equal(current.calls[0].value.games["7"].enabled, true);
  current.succeed(0);
  await current.settle();
  assert.equal(previous.calls.length, 1);
});
