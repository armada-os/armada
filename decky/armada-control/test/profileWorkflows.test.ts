import assert from "node:assert/strict";
import test from "node:test";
import { elements, type Element } from "./helpers/elements.ts";
import { loadModule } from "./helpers/loadModule.ts";
import * as fanCurve from "../src/lib/fanCurve.ts";
import * as freq from "../src/lib/freq.ts";
import * as util from "../src/lib/util.ts";

function setup() {
  const curve = { label: "Moderate", curve: "40:50,70:100,90:255", ramp_up: 5, ramp_down: 4, smoothing: 0.5, min_pwm: 40 };
  const profile = { label: "Balanced", cpu_max: "1.00", cpu_governor: "schedutil", cpu_underclock: "small", gpu_min: "0.00", gpu_max: "1.00", gpu_min_mhz: 300, gpu_max_mhz: 1200, cpu_max_policy0: null, cpu_max_policy4: null, fan_curve: "moderate" };
  let config: any = {
    power: { profiles: { balanced: profile, eco: { ...profile, label: "Eco" } }, fan_curves: { moderate: curve }, general: { default_profile: "balanced" }, underclocks: { TEST: { small: { cpu_max_policy0: "600000", cpu_max_policy4: "2000000" } } }, fan: {} },
    powerDefaults: { profiles: { balanced: { ...profile, cpu_underclock: "none" } } },
    freqLimits: { gpuMhz: [300, 600, 900, 1200], gpuStockMaxMhz: 900, cpuPolicies: [
      { id: 0, cpus: "0-3", khz: [600000, 1200000], mhz: [600, 1200] },
      { id: 4, cpus: "4-7", khz: [1000000, 2000000, 3000000], mhz: [1000, 2000, 3000] },
    ], cpuTopology: { little: "0-3", big: "4-7", prime: "" } },
    cpuDeviceClass: "TEST", chargingFanPwm: 50, perf: { governors: ["schedutil"] }, sshEnabled: false,
  };
  const initial = {
    fanCurves: { moderate: curve, custom: { ...curve, label: "Custom", ramp_up: 8 } },
    factoryFanCurves: { moderate: { ...curve, curve: "40:30,80:255", ramp_up: 3, min_pwm: 30 } },
    profiles: { balanced: { label: "Balanced", fan_curve: "moderate" } }, activeProfile: "balanced",
  };
  const fanWrites: Array<{ changes: any; deleted: string[] }> = [];
  const powerWrites: any[] = [];
  const modals: Element[] = [];
  let closed = 0;
  let fanResult: (() => Promise<any>) | undefined;
  let powerResult: (() => Promise<any>) | undefined;
  let root: Element;
  let tree: any;
  const frames = new Map<string, any[]>();
  let slots: any[];
  let cursor = 0;
  const componentNames = ["DialogBody", "DialogButton", "DialogControlsSection", "DialogControlsSectionHeader", "Dropdown", "Field", "PanelSection", "SliderField", "ToggleField"];
  const element = (type: Element["type"], props: any, key?: string): Element => ({ type, props, key });
  const react = {
    useState: (initial: any) => {
      const owner = slots;
      const index = cursor++;
      if (!(index in owner)) owner[index] = typeof initial === "function" ? initial() : initial;
      return [owner[index], (next: any) => { owner[index] = typeof next === "function" ? next(owner[index]) : next; }];
    },
    useRef: (initial: any) => {
      const index = cursor++;
      if (!(index in slots)) slots[index] = { current: initial };
      return slots[index];
    },
  };
  const setConfig = (next: any) => { config = typeof next === "function" ? next(config) : next; };
  const backend = {
    saveFanCurves: async (changes: any, deleted: string[]) => {
      fanWrites.push({ changes: util.clone(changes), deleted: [...deleted] });
      if (fanResult) return fanResult();
      const next = util.clone(initial);
      Object.assign(next.fanCurves, changes);
      for (const id of deleted) delete (next.fanCurves as any)[id];
      return next;
    },
    savePowerProfile: async (id: string, profile: any) => {
      const power = { ...config.power, profiles: { ...config.power.profiles, [id]: profile } };
      powerWrites.push(util.clone(power));
      return powerResult ? powerResult() : { ...util.clone(config), power: util.clone(power) };
    },
  };
  const modules = new Map<string, any>();
  function load(path: string): any {
    if (modules.has(path)) return modules.get(path);
    const exports = loadModule(path, (id: string): any => {
      if (id === "react") return react;
      if (id === "@decky/ui") return { ...Object.fromEntries(componentNames.map((name) => [name, name])), DialogButtonPrimary: "DialogButton" };
      if (id === "../backend") return backend;
      if (id === "../i18n") return { t: (key: string) => key, translateLabel: (label: string) => label };
      if (id === "../lib/fanCurve") return fanCurve;
      if (id === "../lib/freq") return freq;
      if (id === "../lib/util") return util;
      if (id === "../lib/configMutation") return load("lib/configMutation.ts");
      if (id === "../hooks/useCurrentTemp") return { useCurrentTemp: () => 55 };
      if (id === "./FanCurveGraph") return { FanCurveGraph: "FanCurveGraph" };
      if (id.endsWith("/widgets")) return Object.fromEntries(["ButtonRow", "SectionDescription", "SliderEdit", "TextEdit", "SupportingText"].map((name) => [name, name]));
      if (id.endsWith("/LoadingState")) return { LoadingState: "LoadingState" };
      if (id.endsWith("/modalFocusView")) return { showArmadaModal: (modal: Element) => modals.push(modal) };
      if (id.endsWith("/ArmadaModalRoot")) return { ArmadaModalRoot: "ArmadaModalRoot", ArmadaConfirmModal: "ArmadaConfirmModal", ArmadaDialogHeader: "ArmadaDialogHeader", ArmadaDialogFooter: "ArmadaDialogFooter" };
      if (id === "./AnimatedCollapse") return { AnimatedCollapse: "AnimatedCollapse" };
      const directory = path.slice(0, path.lastIndexOf("/"));
      const resolved: string[] = [];
      for (const part of `${directory}/${id}`.split("/")) {
        if (part === "..") resolved.pop();
        else if (part !== ".") resolved.push(part);
      }
      const target = resolved.join("/");
      return load(`${target}.${target.includes("/hooks/") || target.startsWith("hooks/") ? "ts" : "tsx"}`);
    });
    modules.set(path, exports);
    return exports;
  }
  function render() {
    const expand = (node: any, path: string): any => {
      if (Array.isArray(node)) return node.map((child, index) => expand(child, `${path}/${index}`));
      if (!node || typeof node !== "object") return node;
      if (typeof node.type === "function") {
        const identity = `${path}/${node.type.name}/${node.key || ""}`;
        slots = frames.get(identity) || [];
        frames.set(identity, slots);
        cursor = 0;
        return { ...node, rendered: expand(node.type(node.props), `${identity}/rendered`) };
      }
      return { ...node, props: { ...node.props, children: expand(node.props?.children, `${path}/children`) } };
    };
    tree = expand(root, "root");
  }
  const mount = (node: Element) => {
    root = { ...node, props: { ...node.props, closeModal: () => { closed += 1; } } };
    render();
  };
  const control = (type: string, label?: string) => {
    const node = elements(tree).find((node) => node.type === type && (!label || node.props.label === label || node.props.children === label));
    assert.ok(node, `Missing ${type}: ${label}`);
    return node.props;
  };
  return {
    fanWrites, powerWrites, modals, initial, setConfig, render, mount, control,
    get nodes() { return elements(tree); },
    get config() { return config; }, get closed() { return closed; },
    failFan: (result: () => Promise<any>) => { fanResult = result; },
    respondPower: (result: () => Promise<any>) => { powerResult = result; },
    fan: (curveId = "moderate") => mount(element(load("components/FanCurveEditorModal.tsx").FanCurveEditorModal, { initial, curveId, onSaved: () => {} })),
    power: () => mount(element(load("tabs/Power.tsx").PowerProfileEditorModal, { profileId: "balanced", getLatestConfig: () => config, setConfig, onSaved: () => {} })),
    profiles: () => mount(element(load("tabs/Profiles.tsx").Profiles, { config, setConfig, state: {
      value: initial, loading: false, error: "", setValue: () => {}, refresh: async () => {},
    } })),
    settle: async () => {
      await new Promise((resolve) => setImmediate(resolve));
      render();
    },
  };
}

function create(app: ReturnType<typeof setup>, name: string) {
  app.profiles();
  app.control("ButtonRow", "fanCurve.add").onClick();
  app.mount(app.modals.at(-1)!);
  app.control("TextEdit", "fanCurve.name").onChange(name);
  app.render();
  app.control("DialogButton", "fanCurve.create").onClick();
  app.mount(app.modals.at(-1)!);
}

test("fan reset stays in the draft until Save and Cancel preserves the original", async () => {
  const cancelled = setup();
  cancelled.fan();
  cancelled.control("DialogButton", "fanCurve.resetFactory").onClick();
  cancelled.render();
  cancelled.control("DialogButton", "common.cancel").onClick();
  assert.equal(cancelled.fanWrites.length, 0);
  assert.equal(cancelled.initial.fanCurves.moderate.min_pwm, 40);
  const app = setup();
  app.fan();
  app.control("DialogButton", "fanCurve.resetFactory").onClick();
  app.render();
  app.control("DialogButton", "common.saveChanges").onClick();
  await app.settle();
  assert.deepEqual(app.fanWrites[0].changes.moderate, app.initial.factoryFanCurves.moderate);
});

test("fan point edits survive failed Save and retry writes only its fixed target once", async () => {
  const app = setup();
  app.failFan(async () => { throw new Error("write failed"); });
  app.fan();
  app.control("DialogButton", "fanCurve.editPoints").onClick();
  app.render();
  app.control("TextEdit", "P2: fanCurve.temperature").onChange("65");
  app.render();
  app.control("TextEdit", "P2: fanCurve.temperature").onBlur();
  app.render();
  app.control("DialogButton", "common.saveChanges").onClick();
  await app.settle();
  assert.equal(app.closed, 0);
  assert.equal(app.control("TextEdit", "P2: fanCurve.temperature").value, "65");
  assert.match(app.control("div").children, /write failed/);
  let finish!: (next: any) => void;
  app.failFan(() => new Promise((resolve) => { finish = resolve; }));
  const save = app.control("DialogButton", "common.saveChanges").onClick;
  save();
  save();
  app.control("ArmadaModalRoot").onCancel();
  assert.equal(app.fanWrites.length, 2);
  assert.equal(app.closed, 0);
  assert.deepEqual(app.fanWrites[1], { changes: { moderate: { ...app.initial.fanCurves.moderate, curve: "40:50,65:100,90:255" } }, deleted: [] });
  finish(app.initial);
  await app.settle();
  assert.equal(app.closed, 1);
  assert.equal(app.initial.fanCurves.moderate.curve, "40:50,70:100,90:255");
});

test("creation clones resolved settings temporarily and renaming keeps the generated ID", async () => {
  const cancelled = setup();
  create(cancelled, "Cancelled");
  cancelled.control("DialogButton", "common.cancel").onClick();
  assert.equal(cancelled.fanWrites.length, 0);
  const app = setup();
  app.initial.fanCurves.moderate = { label: "Moderate", curve: "40:50,90:255", ramp_up: 10, ramp_down: 9, smoothing: 0, min_pwm: 0 };
  app.profiles();
  app.control("ButtonRow", "Moderate").onClick();
  assert.equal(app.modals.at(-1)!.props.curveId, "moderate");
  assert.equal(app.initial.activeProfile, "balanced");
  create(app, "123 Quiet");
  assert.equal(app.fanWrites.length, 0);
  app.control("TextEdit", "fanCurve.name").onChange("Renamed later");
  app.render();
  app.control("DialogButton", "common.saveChanges").onClick();
  await app.settle();
  assert.deepEqual(app.fanWrites[0], { changes: { curve_123_quiet: {
    label: "Renamed later", curve: "40:50,90:255", ramp_up: 10, ramp_down: 9, smoothing: 0, min_pwm: 0,
  } }, deleted: [] });
  assert.equal("curve_123_quiet" in app.initial.fanCurves, false);
});

test("deletion requires confirmation and cannot remove an assigned custom curve", async () => {
  const app = setup();
  app.fan("custom");
  app.control("DialogButton", "fanCurve.delete").onClick();
  assert.equal(app.fanWrites.length, 0);
  app.modals.at(-1)!.props.onConfirm();
  await app.settle();
  assert.deepEqual(app.fanWrites[0], { changes: {}, deleted: ["custom"] });
  const assigned = setup();
  assigned.initial.profiles.balanced.fan_curve = "custom";
  assigned.fan("custom");
  assert.equal(assigned.control("DialogButton", "fanCurve.delete").disabled, true);
});

test("Fan Stop persists locally and restores the configured minimum after reopening", async () => {
  const app = setup();
  app.fan();
  app.control("ToggleField", "fanCurve.stop").onChange(true);
  app.render();
  app.control("DialogButton", "common.saveChanges").onClick();
  await app.settle();
  const saved = app.fanWrites[0].changes.moderate;
  assert.equal(fanCurve.parseCurve(saved.curve)[0].pwm, 0);
  assert.equal(saved.min_pwm, 40);
  assert.deepEqual(Object.keys(app.fanWrites[0].changes), ["moderate"]);
  const reopened = setup();
  reopened.initial.fanCurves.moderate = saved;
  reopened.fan();
  reopened.control("ToggleField", "fanCurve.stop").onChange(false);
  reopened.render();
  assert.equal(reopened.control("SliderField", "fanCurve.minimumSpeed").value, fanCurve.pwmToPercent(40));
});

test("performance edits couple GPU limits and preserve other CPU cluster caps", async () => {
  const app = setup();
  app.power();
  app.control("SliderField", "power.gpuMin").onChange(2);
  app.render();
  app.control("SliderField", "power.gpuMax").onChange(1);
  app.render();
  const clusters = app.nodes.filter((node) => node.type === "SliderField" && node.props.label === "power.cpuCluster");
  clusters[0].props.onChange(1);
  app.render();
  assert.equal(app.config.power.profiles.balanced.cpu_underclock, "small");
  app.control("DialogButton", "common.saveChanges").onClick();
  await app.settle();
  const saved = app.powerWrites[0].profiles.balanced;
  assert.equal(saved.gpu_min_mhz, 600);
  assert.equal(saved.gpu_max_mhz, 600);
  assert.equal(saved.cpu_max_policy0, 1200000);
  assert.equal(saved.cpu_max_policy4, 2000000);
});

test("performance reset can be cancelled and Save clears custom frequency caps", async () => {
  const cancelled = setup();
  cancelled.power();
  cancelled.control("DialogButton", "common.resetToDefault").onClick();
  cancelled.control("ArmadaModalRoot").onCancel();
  assert.equal(cancelled.powerWrites.length, 0);
  assert.equal(cancelled.config.power.profiles.balanced.cpu_underclock, "small");
  const app = setup();
  app.power();
  app.control("DialogButton", "common.resetToDefault").onClick();
  app.render();
  app.control("DialogButton", "common.saveChanges").onClick();
  await app.settle();
  const saved = app.powerWrites[0].profiles.balanced;
  assert.equal(saved.cpu_underclock, "none");
  assert.deepEqual([saved.gpu_min_mhz, saved.gpu_max_mhz, saved.cpu_max_policy0, saved.cpu_max_policy4], [null, null, null, null]);
});

test("performance retry keeps its draft, rejects duplicate saves and merges newer unrelated state", async () => {
  const app = setup();
  app.respondPower(async () => { throw new Error("write failed"); });
  app.power();
  app.control("SliderField", "power.gpuMin").onChange(2);
  app.render();
  app.control("DialogButton", "common.saveChanges").onClick();
  await app.settle();
  assert.equal(app.closed, 0);
  assert.equal(app.config.power.profiles.balanced.gpu_min_mhz, 300);
  assert.equal(app.control("SliderField", "power.gpuMin").value, 2);
  let finish!: (next: any) => void;
  app.respondPower(() => new Promise((resolve) => { finish = resolve; }));
  const save = app.control("DialogButton", "common.saveChanges").onClick;
  save();
  save();
  app.control("ArmadaModalRoot").onCancel();
  assert.equal(app.powerWrites.length, 2);
  assert.equal(app.closed, 0);
  app.setConfig((current: any) => ({ ...current, sshEnabled: true, power: { ...current.power, profiles: { ...current.power.profiles, eco: { ...current.power.profiles.eco, cpu_underclock: "large" } } } }));
  finish({ ...app.config, sshEnabled: false, power: app.powerWrites[1] });
  await app.settle();
  assert.equal(app.config.power.profiles.balanced.gpu_min_mhz, 900);
  assert.equal(app.config.power.profiles.eco.cpu_underclock, "large");
  assert.equal(app.config.sshEnabled, true);
  assert.equal(app.closed, 1);
});
