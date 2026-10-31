import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./helpers/loadModule.ts";

function setup(read: () => Promise<any>, separateWindow = false) {
  const slots: any[] = [];
  const effects = new Map<number, { dependencies: any[]; cleanup?: () => void }>();
  const listeners = new Map<string, () => void>();
  let pending: Array<() => void> = [];
  let cursor = 0;
  let state: any;
  const react = {
    useState: (initial: any) => {
      const index = cursor++;
      if (!(index in slots)) slots[index] = typeof initial === "function" ? initial() : initial;
      return [slots[index], (next: any) => { slots[index] = typeof next === "function" ? next(slots[index]) : next; }];
    },
    useRef: (initial: any) => { const index = cursor++; return slots[index] ??= { current: initial }; },
    useCallback: (callback: any, dependencies: any[]) => {
      const index = cursor++;
      if (!slots[index] || !dependencies.every((value, i) => Object.is(value, slots[index].dependencies[i]))) slots[index] = { callback, dependencies };
      return slots[index].callback;
    },
    useEffect: (effect: () => (() => void), dependencies: any[]) => {
      const index = cursor++;
      const previous = effects.get(index);
      if (previous && dependencies.every((value, i) => Object.is(value, previous.dependencies[i]))) return;
      pending.push(() => { previous?.cleanup?.(); effects.set(index, { dependencies, cleanup: effect() }); });
    },
  };
  const events = {
    hidden: false,
    addEventListener: (name: string, listener: () => void) => { listeners.set(name, listener); },
    removeEventListener: (name: string) => { listeners.delete(name); },
    setInterval: (listener: () => void) => { listeners.set("tick", listener); return 1; },
    clearInterval: () => { listeners.delete("tick"); },
  };
  Object.assign(events, { document: events });
  const host = separateWindow ? { current: { ownerDocument: { defaultView: events } } } : undefined;
  const fallback = separateWindow ? {
    document: { hidden: true },
    addEventListener: () => { throw new Error("Use the rendered window's events"); },
    setInterval: () => { throw new Error("Use the rendered window's timers"); },
  } : events;
  const api = loadModule("hooks/useBackendState.ts", { react }, { window: fallback });
  function render() {
    cursor = 0;
    state = api.useBackendState(read, 10000, false, host);
    const next = pending;
    pending = [];
    next.forEach((effect) => effect());
  }
  render();
  return {
    get state() { return state; }, events, listeners, render,
    emit: (name: string) => { listeners.get(name)?.(); },
    settle: async () => { await new Promise((resolve) => setImmediate(resolve)); render(); },
    unmount: () => { for (const effect of effects.values()) effect.cleanup?.(); },
    changeRead: (nextRead: typeof read) => { read = nextRead; render(); },
  };
}

test("shared backend state refreshes configuration on focus and polling", async () => {
  let directory = "/first";
  const app = setup(async () => ({ directory }), true);
  assert.equal(app.state.loading, true);
  await app.settle();
  assert.equal(app.state.value.directory, "/first");
  directory = "/changed";
  app.emit("focus");
  await app.settle();
  assert.equal(app.state.value.directory, "/changed");
  app.events.hidden = true;
  directory = "/hidden";
  app.emit("tick");
  await app.settle();
  assert.equal(app.state.value.directory, "/changed");
  app.events.hidden = false;
  app.emit("visibilitychange");
  await app.settle();
  assert.equal(app.state.value.directory, "/hidden");
  app.unmount();
  assert.equal(app.listeners.size, 0);
});

test("failed refreshes retain the last good state and can recover", async () => {
  let failing = false;
  const app = setup(async () => { if (failing) throw new Error("unavailable"); return { directory: "/logs" }; });
  await app.settle();
  failing = true;
  app.emit("focus");
  await app.settle();
  assert.equal(app.state.value.directory, "/logs");
  assert.match(app.state.error, /unavailable/);
  failing = false;
  await app.state.refresh();
  app.render();
  assert.equal(app.state.error, "");
  app.unmount();
});

test("discarded reads and callbacks cannot overwrite a newer reader", async () => {
  let finish!: (value: any) => void;
  const app = setup(() => new Promise((resolve) => { finish = resolve; }));
  const oldSet = app.state.setValue;
  const oldRefresh = app.state.refresh;
  app.changeRead(async () => ({ enabled: true }));
  await app.settle();
  oldSet({ enabled: false });
  await oldRefresh();
  finish({ enabled: false });
  await app.settle();
  assert.equal(app.state.loading, false);
  assert.equal(app.state.value.enabled, true);
  app.unmount();
});
