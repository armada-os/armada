import assert from "node:assert/strict";
import test from "node:test";
import { elements } from "./helpers/elements.ts";
import { loadModule } from "./helpers/loadModule.ts";
import * as configMutation from "../src/lib/configMutation.ts";
import * as configSections from "../src/lib/configSections.ts";

function setup(initial: Record<string, any> = {}) {
  let config: any = { tweaks: { global: {}, games: {} }, installedGames: [], ...initial };
  let active: "Controller" | "About" = "Controller";
  const slots: any[] = [];
  const effects = new Map<number, { dependencies: any[]; cleanup?: () => void }>();
  let pending: Array<() => void> = [];
  let cursor = 0;
  let tree: any;
  let writes = 0;
  let childRenders = 0;
  const requests: Array<{ section: string; response: ReturnType<typeof Promise.withResolvers> }> = [];
  const element = (type: any, props: any) => ({ type, props });
  const react = {
    useRef: (value: any) => { const index = cursor++; return slots[index] ??= { current: value }; },
    useState: (initial: any) => {
      const index = cursor++;
      if (!(index in slots)) slots[index] = typeof initial === "function" ? initial() : initial;
      return [slots[index], (next: any) => { slots[index] = typeof next === "function" ? next(slots[index]) : next; }];
    },
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
  const backendState = loadModule("hooks/useBackendState.ts", { react });
  const hook = loadModule("hooks/useConfigSection.ts", {
    react, "../lib/configMutation": configMutation, "../lib/configSections": configSections,
    "./useBackendState": backendState, "./useDebouncedApply": { waitForPendingApplies: async () => {} },
  });
  const loading = { LoadingState: "LoadingState" };
  const gate = loadModule("components/ConfigSection.tsx", {
    "@decky/ui": { PanelSection: "PanelSection" }, "./LoadingState": loading,
    "./widgets": { SupportingText: "SupportingText", ButtonRow: "ButtonRow" },
    "../i18n": { t: (key: string) => key },
  });
  const read = (section: string) => () => {
    const response = Promise.withResolvers<any>();
    requests.push({ section, response });
    return response.promise;
  };
  const options = {
    Controller: { read: read("Controller"), fields: configSections.controllerConfigFields, loaded: configSections.hasControllerConfig },
    About: { read: read("About"), fields: configSections.aboutConfigFields, loaded: configSections.hasAboutConfig },
  };
  const setConfig = (next: any) => { writes++; config = typeof next === "function" ? next(config) : next; };
  function render() {
    cursor = 0;
    const state = hook.useConfigSection(config, setConfig, options[active].read, options[active].fields, true);
    tree = gate.ConfigSection({ config, state, loaded: options[active].loaded, children: (current: any) => { childRenders++; return element("LoadedSection", { config: current }); } });
    const next = pending;
    pending = [];
    next.forEach((effect) => effect());
  }
  render();
  return {
    render, requests, setConfig,
    get config() { return config; },
    get writes() { return writes; },
    get childRenders() { return childRenders; },
    nodes: () => elements(tree),
    loading: () => elements(tree).find((node) => node.type === loading.LoadingState),
    select: (section: typeof active) => { active = section; render(); },
    settle: async () => { await new Promise((resolve) => setImmediate(resolve)); render(); },
    unmount: () => { for (const effect of effects.values()) effect.cleanup?.(); },
  };
}

const controller = { gyro: { supported: false, enabled: false }, controllerType: "deck-uhid", controllerTypes: [], calibratedAt: null, hasCalibration: false };

test("a failed section offers Retry without fabricated settings and retains confirmed values on refresh errors", async () => {
  const app = setup();
  await app.settle();
  app.requests[0].response.reject(new Error("unavailable"));
  await app.settle();
  assert.equal(app.childRenders, 0);
  assert.equal(app.loading(), undefined);
  const retry = app.nodes().find((node) => node.type === "ButtonRow");
  assert.equal(retry.props.children, "common.retry");
  retry.props.onClick();
  app.render();
  assert.ok(app.loading());
  await app.settle();
  app.requests[1].response.resolve(controller);
  await app.settle();
  assert.equal(app.config.controllerType, "deck-uhid");
  app.select("About");
  app.select("Controller");
  await app.settle();
  assert.equal(app.requests.at(-1)?.section, "Controller");
  app.requests.at(-1)!.response.reject(new Error("refresh unavailable"));
  await app.settle();
  assert.ok(app.nodes().some((node) => node.type === "LoadedSection"));
  assert.equal(app.config.controllerType, "deck-uhid");
  app.unmount();
});

test("late reads preserve newer intent even when it returns to the original value", async () => {
  const app = setup(controller);
  await app.settle();
  for (const value of ["xbox", "deck-uhid"]) {
    configMutation.markConfigFieldChange(app.setConfig, "controllerType");
    app.setConfig((current: any) => ({ ...current, controllerType: value, selectedGame: null, tweaks: { global: { nice: -7 }, games: {} } }));
    app.render();
  }
  app.requests[0].response.resolve({ ...controller, gyro: { supported: true, enabled: true }, controllerType: "dualsense" });
  await app.settle();
  assert.equal(app.config.controllerType, "deck-uhid");
  assert.deepEqual(app.config.gyro, { supported: true, enabled: true });
  assert.equal(app.config.selectedGame, null);
  assert.equal(app.config.tweaks.global.nice, -7);
  app.select("About");
  await app.settle();
  const writes = app.writes;
  app.unmount();
  app.requests.at(-1)!.response.resolve({ osVersion: "OS", ablVersion: "ABL", sshEnabled: false });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(app.writes, writes);
});
