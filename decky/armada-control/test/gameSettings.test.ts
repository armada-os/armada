import assert from "node:assert/strict";
import test from "node:test";
import { elements as allElements, type Element } from "./helpers/elements.ts";
import { loadModule } from "./helpers/loadModule.ts";
import * as envPresets from "../src/lib/envPresets.ts";
import { clone } from "../src/lib/util.ts";
import { markConfigFieldChange } from "../src/lib/configMutation.ts";

const FOLLOW_STEAM_COMPAT = "__steam_default__";
const USE_DEFAULT_COMPAT = "__armada_default__";
const games = [{ appid: "1", name: "First game" }, { appid: "2", name: "Second game" }];

interface Frame {
  slots: any[];
  effects: Map<number, { dependencies: any[]; cleanup?: () => void }>;
  active: boolean;
}

function containsText(value: any, text: string): boolean {
  if (value === text) return true;
  if (Array.isArray(value)) return value.some((child) => containsText(child, text));
  return !!value && typeof value === "object" && containsText(value.props?.children, text);
}
function setup(overrides: Record<string, any> = {}, loadTab = false) {
  let config: any = {
    installedGames: clone(games), game: games[0], selectedGame: games[0],
    tweaks: { global: { windowsCompatTool: FOLLOW_STEAM_COMPAT, fexProfile: "default" }, games: { "1": { enabled: true } } },
    fexProfiles: { default: { label: "Default", config: { Multiblock: "1" } }, fast: { label: "Fast", config: { Multiblock: "0" } } },
    protonDefaults: ["stable"], envPresets: [], turnipDrivers: [],
    ...overrides,
  };
  const modals: Element[] = [];
  const modalEntries: Array<{ element: Element; open: boolean; Close: () => void }> = [];
  const modalTrees: any[] = [];
  const advancedWrites: any[] = [];
  let advancedResponse: () => Promise<void> = async () => {};
  const resolutionWrites: Array<[number, string]> = [];
  const resolutions = new Map<number, string | Promise<string>>();
  const compatStates = new Map<string, any>();
  const compatListeners = new Map<string, Set<(state: any) => void>>();
  const frames = new Map<string, Frame>();
  let frame: Frame;
  let cursor = 0;
  let tree: any;
  let globalResolution = "Native";
  let pendingEffects: Array<() => void> = [];
  let pendingLayoutEffects: Array<() => void> = [];
  let rootMounted = true;
  let initialState: any;
  const { promise: initialGate, resolve: releaseInitial } = Promise.withResolvers<void>();
  let initialRequest: Promise<any>;
  const initialValues = new Map<string, any>();
  const setConfig = (value: any) => { config = typeof value === "function" ? value(config) : value; };
  const saveTweaksNow = async (update: (current: any) => any) => {
    advancedWrites.push(clone(update(config.tweaks)));
    await advancedResponse();
    config = { ...config, tweaks: update(config.tweaks) };
    return config;
  };
  const componentNames = ["DialogBody", "DialogButton", "DialogControlsSection", "DialogControlsSectionHeader", "DialogFooter", "Dropdown", "Field", "PanelSection", "TextField"];
  const element = (type: Element["type"], props: any, key?: string) => ({ type, props, key });
  const effectHook = (pending: () => Array<() => void>) => (effect: () => (() => void) | undefined, dependencies: any[]) => {
    const owner = frame;
    const index = cursor++;
    const previous = owner.effects.get(index);
    if (previous && dependencies.every((value, i) => Object.is(value, previous.dependencies[i]))) return;
    pending().push(() => {
      previous?.cleanup?.();
      owner.effects.set(index, { dependencies, cleanup: effect() });
    });
  };
  const react = {
    useCallback: (callback: any, dependencies: any[]) => {
      const index = cursor++;
      const previous = frame.slots[index];
      if (!previous || !dependencies.every((value, i) => Object.is(value, previous.dependencies[i]))) frame.slots[index] = { callback, dependencies };
      return frame.slots[index].callback;
    },
    useState: (initial: any) => {
      const owner = frame;
      const index = cursor++;
      if (!(index in owner.slots)) owner.slots[index] = typeof initial === "function" ? initial() : initial;
      return [owner.slots[index], (value: any) => {
        if (owner.active) owner.slots[index] = typeof value === "function" ? value(owner.slots[index]) : value;
      }];
    },
    useRef: (initial: any) => {
      const index = cursor++;
      if (!(index in frame.slots)) frame.slots[index] = { current: initial };
      return frame.slots[index];
    },
    useEffect: effectHook(() => pendingEffects),
    useLayoutEffect: effectHook(() => pendingLayoutEffects),
    useSyncExternalStore: (subscribe: (listener: () => void) => () => void, getSnapshot: () => any) => {
      react.useEffect(() => subscribe(() => {}), [subscribe]);
      return getSnapshot();
    },
  };

  const backendState = loadModule("hooks/useBackendState.ts", { react }, { window: { document: { hidden: false, addEventListener: () => {}, removeEventListener: () => {} }, addEventListener: () => {}, removeEventListener: () => {}, clearInterval } });
  const useInitialState = (read: () => Promise<any>, ...args: any[]) => {
    const gated = react.useCallback(() => {
      const request = initialGate.then(read);
      initialRequest ??= request;
      return request;
    }, [read]);
    initialState = backendState.useBackendState(gated, ...args);
    return initialState;
  };
  const apps = {
    GetResolutionOverrideForApp: async (appid: number) => resolutions.get(appid) ?? "Default",
    SetAppResolutionOverride: async (appid: number, value: string) => { resolutionWrites.push([appid, value]); resolutions.set(appid, value); },
    RegisterForAppOverviewChanges: () => ({ unregister: () => {} }),
  };
  const compat = {
    FOLLOW_STEAM_COMPAT, USE_DEFAULT_COMPAT,
    defaultWindowsCompatTool: () => "stable",
    getProtonTools: async () => [{ id: "stable", label: "Stable" }, { id: "preview", label: "Preview" }],
    getAppCompatTools: async () => [],
    subscribeCompatState: (appid: string, listener: (state: any) => void) => {
      const listeners = compatListeners.get(appid) || new Set();
      compatListeners.set(appid, listeners);
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    resolveCompatState: async (appid: string) => compatStates.get(appid) ?? { tool: "", priority: 0 },
    compatSelection: (state: any, defaultTool: string) => !state.tool || state.priority < 250
      ? FOLLOW_STEAM_COMPAT : state.tool === defaultTool ? USE_DEFAULT_COMPAT : state.tool,
    specifyCompatTool: async (appid: string, tool: string) => {
      compatStates.set(appid, { tool: tool === FOLLOW_STEAM_COMPAT ? "" : tool, priority: tool && tool !== FOLLOW_STEAM_COMPAT ? 250 : 0 });
    },
    persistHandledGames: (save: (appids: string[]) => Promise<unknown>) => save([]), markCompatHandled: () => {},
    setAutoApplyCompat: () => {}, setWindowsCompatTool: () => {},
    setGameCompatProfiles: () => {},
    updateGameCompatProfile: () => {},
    migrateWindowsCompatTool: async () => {},
    resetCompatToolToDefault: async (appid: string) => { compatStates.set(appid, { tool: "", priority: 0 }); return ""; },
    resetLaunchOptionsForGame: async () => true,
    resolveProfileAppids: async (appids: string[]) => appids,
    resetAllGamePolicies: async () => {},
  };
  const steamSettings = {
    getGlobalResolution: () => globalResolution,
    setGlobalResolution: async (value: string) => { globalResolution = value; return value; },
    getGameResolution: (appid: string) => apps.GetResolutionOverrideForApp(Number(appid)),
    setGameResolution: (appid: string, value: string) => apps.SetAppResolutionOverride(Number(appid), value),
  };

  const gamePolicy = loadModule("lib/gameSettings.ts", { "./steamCompat": compat });
  const saves = loadModule("lib/configSaveQueue.ts", {});
  const queue = loadModule("lib/gameSettingsQueue.ts", {});
  const advanced = loadModule("lib/advancedSettings.ts", { "./util": { clone } });

  const modalView = loadModule("components/useModalView.tsx", { react });
  const exports = loadModule("tabs/Compatibility.tsx", (id: string) => {
    if (id === "react") return react;
    if (id === "@decky/ui") return { ...Object.fromEntries(componentNames.map((name) => [name, name])), DialogButtonPrimary: "DialogButton" };
    if (id === "../components/modalFocusView") return { showArmadaModal: (modal: Element, _parent: unknown, options?: { fnOnClose?: () => void }) => {
      const entry = { element: modal, open: true, Close: () => {
        if (!entry.open) return;
        entry.open = false;
        options?.fnOnClose?.();
      } };
      modals.push(modal);
      modalEntries.push(entry);
      return entry;
    } };
    if (id === "../components/widgets") return {
      ...Object.fromEntries(["ButtonRow", "ControlRow", "LabelWithBadge", "NoticeSection", "SectionDescription", "SelectEdit", "SliderEdit", "SupportingText", "TextEdit", "ToggleRow"].map((name) => [name, name])),
      Subsection: ({ title, children }: any) => element("Fragment", { children: [
        element("div", { className: "armada-subheader", role: "heading", "aria-level": 3, children: title }), children,
      ] }),
    };
    if (id === "../components/ArmadaModalRoot") return { ArmadaConfirmModal: "ArmadaConfirmModal", ArmadaModalRoot: "ArmadaModalRoot", ArmadaDialogHeader: "ArmadaDialogHeader", ArmadaDialogFooter: "ArmadaDialogFooter" };
    if (id === "../components/useModalView") return modalView;
    if (id === "../components/LoadingState") return { LoadingState: "LoadingState" };
    if (id === "../hooks/useBackendState") return { useBackendState: useInitialState };
    if (id === "../i18n") return {
      t: (key: string, values?: Record<string, string>) => values ? `${key}:${Object.values(values).join(":")}` : key,
      translateLabel: (label: string) => label, getCurrentLocale: () => "en",
    };
    if (id === "../lib/util") return { clone };
    if (id === "../lib/envPresets") return envPresets;
    if (id === "../lib/games") return { availableGames: (current: any) => [...current.installedGames] };
    if (id === "../lib/steamCompat") return compat;
    if (id === "../lib/gameSettings") return gamePolicy;
    if (id === "../lib/gameSettingsQueue") return queue;
    if (id === "../lib/configMutation") return { markConfigFieldChange };
    if (id === "../lib/configSaveQueue") return saves;
    if (id === "../lib/advancedSettings") return advanced;
    if (id === "../lib/steamSettings") return steamSettings;
    if (id === "../backend") return {
      getCompatMappedAppids: async () => [], getStartupInstalledGames: async () => clone(games), saveCompatApplied: async () => {},
      reapplyPerf: async () => {}, restartGameMode: async () => {},
    };
  }, { window: { SteamClient: { Apps: apps }, setTimeout, clearTimeout } });

  const initialHook = loadModule("hooks/useGameSettingsState.ts", (id: string) => {
    if (id === "react") return react;
    if (id === "../lib/steamCompat") return compat;
    if (id === "../lib/gameSettingsQueue") return queue;
    if (id === "../lib/configSaveQueue") return saves;
    if (id === "../lib/steamSettings") return steamSettings;
    if (id === "./useBackendState") return { useBackendState: useInitialState };
    throw Error(id);
  }, { window: { SteamClient: { Apps: apps } } });
  function LoadedSettings() {
    const state = initialHook.useGameSettingsState(config, { current: null }, true);
    return element(exports.Compatibility, { config, setConfig, saveTweaksNow, state });
  }
  function render() {
    const mounted = new Set<string>();
    const expand = (node: any, path: string): any => {
      if (Array.isArray(node)) return node.map((child, index) => expand(child, `${path}/${index}`));
      if (!node || typeof node !== "object") return node;
      if (typeof node.type === "function") {
        const identity = `${path}/${node.type.name}/${node.key || ""}`;
        mounted.add(identity);
        frame = frames.get(identity) || { slots: [], effects: new Map(), active: true };
        frames.set(identity, frame);
        cursor = 0;
        return { ...node, rendered: expand(node.type(node.props), `${identity}/rendered`) };
      }
      return { ...node, props: { ...node.props, children: expand(node.props?.children, `${path}/children`) } };
    };
    const selected = config.selectedGame === undefined ? config.game : config.selectedGame;
    const initial = {
      compatTools: [{ id: "stable", label: "Stable" }, { id: "preview", label: "Preview" }],
      policy: selected ? { resolution: resolutions.get(Number(selected.appid)) || "Default", tools: [], state: compatStates.get(selected.appid) || { tool: "", priority: 0 } } : null,
    };
    const target = selected?.appid || "";
    if (!initialValues.has(target)) initialValues.set(target, initial);
    tree = rootMounted ? expand(element(loadTab ? LoadedSettings : exports.GameSettingsContent, { config, setConfig, saveTweaksNow, initial: initialValues.get(target), state: initialState }), "root") : null;
    const layoutEffects = pendingLayoutEffects;
    pendingLayoutEffects = [];
    for (const effect of layoutEffects) effect();
    modalEntries.forEach((entry, index) => {
      modalTrees[index] = entry.open ? expand({ ...entry.element, props: { ...entry.element.props, closeModal: entry.Close } }, `modal/${index}`) : null;
    });
    for (const [identity, owner] of frames) {
      if (mounted.has(identity)) continue;
      owner.active = false;
      for (const effect of owner.effects.values()) effect.cleanup?.();
      frames.delete(identity);
    }
    const effects = pendingEffects;
    pendingEffects = [];
    for (const effect of effects) effect();
    return tree;
  }
  function editor(appid: string | null) {
    const node = allElements(tree).find((node) => typeof node.type === "function"
      && Object.prototype.hasOwnProperty.call(node.props, "game") && (node.props.game?.appid ?? null) === appid);
    assert.ok(node, `Missing settings editor for ${appid ?? "defaults"}`);
    return node;
  }
  function control(appid: string | null, type: string, label: string) {
    const node = allElements(editor(appid).rendered).find((node) => node.type === type
      && (containsText(node.props.label, label) || containsText(node.props.children, label)));
    assert.ok(node, `Missing ${type}: ${label}`);
    return node;
  }
  function modalControl(type: string, label?: string, index = modalEntries.length - 1) {
    const node = allElements(modalTrees[index]).find((node) => node.type === type
      && (label === undefined || containsText(node.props.label, label) || containsText(node.props.children, label)));
    assert.ok(node, `Missing modal ${type}: ${label}`);
    return node;
  }
  render();
  return {
    render, editor, control, modalControl, modals, resolutions, compatStates, resolutionWrites, apps, compat, setConfig, advancedWrites,
    notifyCompat: (appid: string, state: any) => { for (const listener of compatListeners.get(appid) || []) listener(state); },
    refreshInitial: () => initialState.refresh(),
    loadInitial: async () => { releaseInitial(); await initialRequest.catch(() => {}); await new Promise((resolve) => setImmediate(resolve)); render(); },
    respondAdvanced: (response: () => Promise<void>) => { advancedResponse = response; },
    get config() { return config; },
    elements: () => allElements(tree),
    modalElements: (index = modalEntries.length - 1) => allElements(modalTrees[index]),
    modalOpen: (index = modalEntries.length - 1) => modalEntries[index]?.open ?? false,
    closeModal: (index = modalEntries.length - 1) => { modalEntries[index].Close(); render(); },
    unmount: () => { rootMounted = false; render(); },
    select: (appid: string) => {
      const selector = allElements(tree).find((node) => node.type === "SelectEdit" && node.props.label === undefined);
      assert.ok(selector);
      selector.props.onChange(appid);
      render();
    },
    settle: async () => {
      await new Promise((resolve) => setImmediate(resolve));
      render();
      await new Promise((resolve) => setImmediate(resolve));
      render();
    },
  };
}

const variablePresets = [
  { name: "COMMON_OPTION", description: "A documented choice", options: [{ data: "on", label: "On" }, { data: "off", label: "Off" }] },
  { name: "COMMON_TEXT", description: "A documented text value", example: "example" },
];

test("Advanced Cancel and Back discard drafts, and target changes and unmount close the editor", () => {
  const app = setup({ tweaks: { global: { windowsCompatTool: FOLLOW_STEAM_COMPAT }, games: { "1": { enabled: true }, "2": { enabled: true } } } });
  app.control("1", "ButtonRow", "compatibility.advancedSettings").props.onClick();
  app.render();
  app.control("1", "ButtonRow", "compatibility.advancedSettings").props.onClick();
  assert.equal(app.modals.length, 1);
  app.modalControl("ToggleRow", "Host Vulkan").props.onChange(false);
  app.render();
  app.closeModal();
  assert.equal(app.modalOpen(), false);
  app.control("1", "ButtonRow", "compatibility.advancedSettings").props.onClick();
  app.render();
  assert.equal(app.modalControl("ToggleRow", "Host Vulkan").props.value, true);
  app.modalControl("ToggleRow", "Host OpenGL").props.onChange(false);
  app.render();
  app.modalControl("ArmadaModalRoot").props.onCancel();
  app.render();
  assert.equal(app.modalOpen(), false);
  app.control("1", "ButtonRow", "compatibility.advancedSettings").props.onClick();
  app.render();
  assert.equal(app.modalControl("ToggleRow", "Host OpenGL").props.value, true);
  app.select("2");
  assert.equal(app.modalOpen(), false);
  app.control("2", "ButtonRow", "compatibility.advancedSettings").props.onClick();
  app.render();
  assert.equal(app.modalControl("ToggleRow", "Host Vulkan").props.value, true);
  app.unmount();
  assert.equal(app.modalOpen(), false);
  assert.equal(app.config.tweaks.games["2"].thunks, undefined);
  assert.equal(app.config.tweaks.games["1"].thunks, undefined);
  assert.equal(app.advancedWrites.length, 0);
});

test("Advanced Restore clears only its own overrides after Save and preserves inline settings", async () => {
  const performance = { cores: "0-1", wineTopology: false, nice: -5, gamescopeCores: "2-3", gamescopeNice: -2, scheduler: "eevdf" };
  const app = setup({ tweaks: {
    global: { windowsCompatTool: FOLLOW_STEAM_COMPAT, cores: "all", nice: -1 },
    games: { "1": { enabled: true, ...performance, env: { LOCAL_OPTION: "1" }, thunks: { Vulkan: false }, turnipDriver: "preview" } },
  } });
  app.control("1", "ButtonRow", "compatibility.advancedSettings").props.onClick();
  app.render();
  app.render();
  assert.equal(app.config.tweaks.games["1"].cores, "0-1");
  app.modalControl("DialogButton", "common.resetToDefault").props.onClick();
  app.render();
  assert.equal(app.config.tweaks.games["1"].nice, -5);
  assert.equal(app.config.tweaks.games["1"].thunks.Vulkan, false);
  assert.equal(app.advancedWrites.length, 0);
  app.modalControl("DialogButton", "common.saveChanges").props.onClick();
  await app.settle();
  for (const key of ["nice", "gamescopeCores", "gamescopeNice", "scheduler", "thunks", "turnipDriver"]) {
    assert.equal(key in app.config.tweaks.games["1"], false, key);
  }
  assert.equal(app.config.tweaks.games["1"].cores, "0-1");
  assert.equal(app.config.tweaks.games["1"].wineTopology, false);
  assert.equal(app.config.tweaks.games["1"].env.LOCAL_OPTION, "1");
  assert.equal(app.config.tweaks.games["1"].enabled, true);
  assert.equal(app.config.tweaks.global.nice, -1);
  assert.equal(app.modalOpen(), false);
});

test("failed Advanced saves retain the draft and retries merge current state without duplicate saves", async () => {
  const app = setup();
  app.respondAdvanced(async () => { throw new Error("write failed"); });
  app.control("1", "ButtonRow", "compatibility.advancedSettings").props.onClick();
  app.render();
  app.modalControl("ToggleRow", "Host Vulkan").props.onChange(false);
  app.render();
  app.modalControl("DialogButton", "common.saveChanges").props.onClick();
  await app.settle();
  assert.equal(app.modalOpen(), true);
  assert.equal(app.modalControl("ToggleRow", "Host Vulkan").props.value, false);
  assert.equal(app.config.tweaks.games["1"].thunks, undefined);
  assert.ok(app.modalElements().some((node) => node.type === "SupportingText" && node.props.children === "Error: write failed"));
  let release!: () => void;
  app.respondAdvanced(() => new Promise<void>((resolve) => { release = resolve; }));
  const save = app.modalControl("DialogButton", "common.saveChanges").props.onClick;
  save();
  save();
  app.render();
  assert.equal(app.advancedWrites.length, 2);
  assert.equal(app.modalControl("DialogButton", "common.cancel").props.disabled, true);
  assert.equal(app.modalControl("DialogButton", "common.resetToDefault").props.disabled, true);
  app.modalControl("ArmadaModalRoot").props.onCancel();
  assert.equal(app.modalOpen(), true);
  app.setConfig((current: any) => ({ ...current, sshEnabled: true, tweaks: { ...current.tweaks, games: {
    ...current.tweaks.games, "1": { ...current.tweaks.games["1"], nice: -7, env: { NEW_OPTION: "1" } }, "2": { nice: -4 },
  } } }));
  app.render();
  release();
  await app.settle();
  assert.equal(app.modalOpen(), false);
  assert.equal(app.config.tweaks.games["1"].thunks.Vulkan, false);
  assert.equal(app.config.tweaks.games["1"].env.NEW_OPTION, "1");
  assert.equal(app.config.tweaks.games["1"].nice, -7);
  assert.equal(app.config.tweaks.games["2"].nice, -4);
  assert.equal(app.config.sshEnabled, true);
});

test("single-game reset cannot replay the cached native policy into the main panel", async () => {
  const app = setup({ tweaks: {
    global: { windowsCompatTool: FOLLOW_STEAM_COMPAT },
    games: { "1": { enabled: true, steamCompatTool: "preview", steamResolution: "960x540" } },
  } }, true);
  app.compatStates.set("1", { tool: "preview", priority: 250 });
  app.resolutions.set(1, "960x540");
  await app.loadInitial();
  await app.settle();
  const publish = app.elements().find((node) => typeof node.type === "function" && node.type.name === "GameSettingsContent")!.props.onPolicyChange;
  app.control("1", "ButtonRow", "common.resetToDefault").props.onClick();
  app.modals.at(-1)!.props.onConfirm();
  await app.settle();
  publish({ resolution: "Default", selection: "preview", tools: [{ id: "late-tool", label: "Late tool" }] });
  app.render();
  await app.settle();
  assert.equal(app.config.tweaks.games["1"], undefined);
  assert.equal(app.control("1", "ToggleRow", "gameSettings.usePerGame").props.value, false);
  assert.equal(allElements(app.editor("1").rendered).some((node) => node.type === "SelectEdit"), false);
  app.control("1", "ToggleRow", "gameSettings.usePerGame").props.onChange(true);
  await app.settle();
  assert.equal(app.control("1", "SelectEdit", "compatibility.tool").props.value, USE_DEFAULT_COMPAT);
});

test("reset all clears game overrides and resolutions without replacing global defaults", async () => {
  const app = setup({ tweaks: {
    global: { windowsCompatTool: FOLLOW_STEAM_COMPAT, fexProfile: "fast" },
    games: { "1": { nice: -5 }, "2": { scheduler: "eevdf" } },
  } });
  const defaults = clone(app.config.tweaks.global);
  app.control(null, "ButtonRow", "compatibility.resetAllGames").props.onClick();
  app.modals.at(-1)!.props.onConfirm();
  await app.settle();
  assert.equal(Object.keys(app.config.tweaks.games).length, 0);
  assert.deepEqual(app.config.tweaks.global, defaults);
  assert.deepEqual(app.resolutionWrites.sort((a, b) => a[0] - b[0]), [[1, "Default"], [2, "Default"]]);
  assert.equal(app.control("1", "ToggleRow", "gameSettings.usePerGame").props.value, false);
  assert.equal(allElements(app.editor("1").rendered).some((node) => node.type === "SelectEdit"), false);
});

test("profile toggles preserve saved overrides despite stale native settings and restore them when reenabling", async () => {
  const app = setup({ tweaks: {
    global: { windowsCompatTool: FOLLOW_STEAM_COMPAT, fexProfile: "default" },
    games: { "1": { fexProfile: "fast", nice: -5, steamCompatTool: "preview", steamResolution: "960x540" }, "2": { scheduler: "lavd" } },
  } });
  app.resolutions.set(1, "Default");
  app.compatStates.set("1", { tool: "", priority: 0 });
  await app.settle();
  assert.equal(app.control("1", "ToggleRow", "gameSettings.usePerGame").props.value, true);
  app.control("1", "ToggleRow", "gameSettings.usePerGame").props.onChange(false);
  await app.settle();
  assert.equal(app.config.tweaks.games["1"].enabled, false);
  assert.equal(app.config.tweaks.games["1"].steamCompatTool, "preview");
  assert.equal(app.config.tweaks.games["1"].steamResolution, "960x540");
  assert.equal(app.config.tweaks.games["1"].fexProfile, "fast");
  assert.equal(app.config.tweaks.games["2"].scheduler, "lavd");
  assert.equal(app.control("1", "ToggleRow", "gameSettings.usePerGame").props.value, false);
  assert.equal(allElements(app.editor("1").rendered).some((node) => node.type === "SelectEdit"), false);
  app.control(null, "SelectEdit", "compatibility.fexPreset").props.onChange("custom");
  app.render();
  app.control("1", "ToggleRow", "gameSettings.usePerGame").props.onChange(true);
  await app.settle();
  assert.equal(app.config.tweaks.games["1"].enabled, true);
  assert.equal(app.control("1", "ToggleRow", "gameSettings.usePerGame").props.value, true);
  assert.equal(app.config.tweaks.games["1"].nice, -5);
  assert.equal(app.config.tweaks.global.fexProfile, "custom");
  assert.equal(app.control("1", "SelectEdit", "compatibility.tool").props.value, "preview");
  assert.equal(app.control("1", "SelectEdit", "compatibility.gameResolution").props.value, "960x540");
});

test("late per-game toggle responses change the original target without replacing another game or newer defaults", async () => {
  const app = setup({ tweaks: {
    global: { windowsCompatTool: FOLLOW_STEAM_COMPAT, fexProfile: "default" },
    games: { "1": { fexProfile: "fast" }, "2": { nice: -2 } },
  } });
  let finish!: (value: string) => void;
  app.resolutions.set(1, new Promise((resolve) => { finish = resolve; }));
  app.control("1", "ToggleRow", "gameSettings.usePerGame").props.onChange(false);
  app.select("2");
  app.control(null, "SelectEdit", "compatibility.fexPreset").props.onChange("custom");
  app.render();
  finish("1280x720");
  await app.settle();
  assert.equal(app.config.selectedGame.appid, "2");
  assert.equal(app.config.tweaks.games["1"].enabled, false);
  assert.equal(app.config.tweaks.games["1"].steamResolution, "1280x720");
  assert.equal(app.config.tweaks.games["2"].nice, -2);
  assert.equal(app.config.tweaks.games["2"].enabled, undefined);
  assert.equal(app.config.tweaks.global.fexProfile, "custom");
});

test("reset waits for pending native saves instead of allowing them to recreate a deleted profile", async () => {
  const app = setup();
  await app.settle();
  const { promise: pending, resolve: release } = Promise.withResolvers<void>();
  const write = app.apps.SetAppResolutionOverride;
  app.apps.SetAppResolutionOverride = async (appid, value) => {
    if (value === "1280x720") await pending;
    await write(appid, value);
  };
  const saving = app.control("1", "SelectEdit", "compatibility.gameResolution").props.onChange("1280x720");
  app.control("1", "ButtonRow", "common.resetToDefault").props.onClick();
  app.modals.at(-1)!.props.onConfirm();
  release();
  await saving;
  await app.settle();
  assert.equal(app.config.tweaks.games["1"], undefined);
  assert.equal(app.resolutions.get(1), "Default");
  assert.equal(app.control("1", "ToggleRow", "gameSettings.usePerGame").props.value, false);
});

test("an explicit Proton equal to the global choice stays selected through refresh and later global changes", async () => {
  const app = setup({ tweaks: { global: { windowsCompatTool: "stable" }, games: { "1": { enabled: true } } } });
  const selecting = app.control("1", "SelectEdit", "compatibility.tool").props.onChange("stable");
  app.render();
  assert.equal(app.control("1", "SelectEdit", "compatibility.tool").props.value, "stable");
  await selecting;
  await app.settle();
  assert.equal(app.config.tweaks.games["1"].steamCompatTool, "stable");
  assert.equal(app.control("1", "SelectEdit", "compatibility.tool").props.value, "stable");
  app.setConfig((current: any) => ({ ...current, tweaks: { ...current.tweaks, global: { ...current.tweaks.global, windowsCompatTool: "preview" } } }));
  await app.settle();
  assert.equal(app.control("1", "SelectEdit", "compatibility.tool").props.value, "stable");
  app.select("2");
  app.select("1");
  await app.settle();
  assert.equal(app.control("1", "SelectEdit", "compatibility.tool").props.value, "stable");
  assert.equal(app.elements().some((node) => node.type === "LoadingState"), false);
});

test("a selected game's inherited Proton stays stable while a global migration is pending with real cached policy state", async () => {
  const app = setup({ installedGames: [], tweaks: { global: { windowsCompatTool: "stable" }, games: { "1": { enabled: true }, "3": { enabled: false } } } }, true);
  app.compatStates.set("1", { tool: "stable", priority: 250 });
  await app.loadInitial();
  await app.settle();
  const { promise: pending, resolve: release } = Promise.withResolvers<void>();
  let migrated: string[] = [];
  app.compat.migrateWindowsCompatTool = async (appids, _old, next) => {
    migrated = Array.from(appids);
    await pending;
    const state = { tool: next, priority: 250 };
    app.compatStates.set("1", state);
    app.notifyCompat("1", state);
  };
  assert.equal(app.control("1", "SelectEdit", "compatibility.tool").props.value, USE_DEFAULT_COMPAT);
  const changing = app.control(null, "SelectEdit", "compatibility.defaultProton").props.onChange("preview");
  await app.settle();
  assert.equal(app.control("1", "SelectEdit", "compatibility.tool").props.value, USE_DEFAULT_COMPAT);
  assert.equal(app.elements().some((node) => node.type === "LoadingState"), false);
  assert.deepEqual(migrated.sort(), ["1", "2", "3"]);
  release();
  await changing;
  await app.settle();
  assert.equal(app.config.tweaks.global.windowsCompatTool, "preview");
  assert.equal(app.control("1", "SelectEdit", "compatibility.tool").props.value, USE_DEFAULT_COMPAT);
  assert.equal(app.config.tweaks.games["1"].steamCompatTool, undefined);
});

test("a failed global Proton update offers a working Retry action and clears it after propagation succeeds", async () => {
  const app = setup({ tweaks: { global: { windowsCompatTool: "stable" }, games: {} } });
  let attempts = 0;
  app.compat.migrateWindowsCompatTool = async () => { if (++attempts === 1) throw new Error("native propagation failed"); };
  await app.control(null, "SelectEdit", "compatibility.defaultProton").props.onChange("preview");
  await app.settle();
  assert.ok(app.control(null, "ButtonRow", "common.retry"));
  app.control(null, "ButtonRow", "common.retry").props.onClick();
  await app.settle();
  assert.equal(attempts, 2);
  assert.equal(app.config.tweaks.global.windowsCompatTool, "preview");
  assert.equal(allElements(app.editor(null).rendered).some((node) => node.type === "ButtonRow" && node.props.children === "common.retry"), false);
});

test("failed native metadata saves restore Proton, resolution and toggle state before reporting errors", async () => {
  const app = setup({ tweaks: { global: { windowsCompatTool: FOLLOW_STEAM_COMPAT }, games: {
    "1": { enabled: true, steamCompatTool: "stable", steamResolution: "Native" },
  } } });
  app.compatStates.set("1", { tool: "stable", priority: 250 });
  app.resolutions.set(1, "Native");
  await app.settle();
  app.respondAdvanced(async () => { throw new Error("metadata save failed"); });
  await app.control("1", "SelectEdit", "compatibility.tool").props.onChange("preview");
  await app.settle();
  assert.equal(app.compatStates.get("1").tool, "stable");
  assert.equal(app.control("1", "SelectEdit", "compatibility.tool").props.value, "stable");
  await app.control("1", "SelectEdit", "compatibility.gameResolution").props.onChange("960x540");
  await app.settle();
  assert.equal(app.resolutions.get(1), "Native");
  assert.equal(app.control("1", "SelectEdit", "compatibility.gameResolution").props.value, "Native");
  app.control("1", "ToggleRow", "gameSettings.usePerGame").props.onChange(false);
  await app.settle();
  assert.equal(app.config.tweaks.games["1"].enabled, true);
  assert.equal(app.compatStates.get("1").tool, "stable");
  assert.equal(app.resolutions.get(1), "Native");
  assert.equal(app.control("1", "ToggleRow", "gameSettings.usePerGame").props.value, true);
});

test("native game refresh waits for a pending save and still reflects external resolution changes", async () => {
  const app = setup({}, true);
  await app.loadInitial();
  await app.settle();
  let release!: () => void;
  app.respondAdvanced(() => new Promise<void>((resolve) => { release = resolve; }));
  app.control("1", "ToggleRow", "gameSettings.usePerGame").props.onChange(false);
  await app.settle();
  let reads = 0;
  const read = app.compat.resolveCompatState;
  app.compat.resolveCompatState = async (appid: string) => { reads++; return read(appid); };
  const refreshed = app.refreshInitial();
  await app.settle();
  assert.equal(reads, 0);
  release();
  await refreshed;
  await app.settle();
  assert.ok(reads > 0);
  app.setConfig((current: any) => ({ ...current, tweaks: { ...current.tweaks, games: {} } }));
  app.resolutions.set(1, "1280x720");
  await app.refreshInitial();
  await app.settle();
  assert.equal(app.control("1", "SelectEdit", "compatibility.gameResolution").props.value, "1280x720");
});

test("consecutive FEX and thunk changes merge the latest target before React renders", async () => {
  const app = setup({ tweaks: {
    global: { windowsCompatTool: FOLLOW_STEAM_COMPAT, fexProfile: "custom", fexConfig: { TSOEnabled: "0", X87ReducedPrecision: "0" }, thunks: { Vulkan: true, GL: true } },
    games: { "1": { enabled: true, fexProfile: "custom", fexConfig: { TSOEnabled: "0", X87ReducedPrecision: "0" } } },
  } });
  for (const target of ["1", null]) {
    const tso = app.control(target, "ToggleRow", "TSO Enabled").props.onChange;
    const x87 = app.control(target, "ToggleRow", "X87 Reduced Precision").props.onChange;
    tso(true);
    x87(true);
    const settings = target ? app.config.tweaks.games[target] : app.config.tweaks.global;
    assert.equal(settings.fexConfig.TSOEnabled, "1");
    assert.equal(settings.fexConfig.X87ReducedPrecision, "1");
    app.render();
    app.control(target, "ButtonRow", "compatibility.advancedSettings").props.onClick();
    app.render();
    const vulkan = app.modalControl("ToggleRow", "Host Vulkan").props.onChange;
    const gl = app.modalControl("ToggleRow", "Host OpenGL").props.onChange;
    vulkan(false);
    gl(false);
    app.render();
    assert.equal(app.modalControl("ToggleRow", "Host Vulkan").props.value, false);
    assert.equal(app.modalControl("ToggleRow", "Host OpenGL").props.value, false);
    app.modalControl("DialogButton", "common.saveChanges").props.onClick();
    await app.settle();
    const saved = target ? app.config.tweaks.games[target] : app.config.tweaks.global;
    assert.equal(saved.thunks.Vulkan, false);
    assert.equal(saved.thunks.GL, false);
  }
});

test("explicit per-game settings stay separate from later defaults and a cleared game selection", async () => {
  const app = setup({ tweaks: {
    global: { windowsCompatTool: FOLLOW_STEAM_COMPAT, fexProfile: "fast", cores: "all", env: { EXAMPLE: "1" } },
    games: { "1": { enabled: true } },
  } });
  app.control("1", "SelectEdit", "compatibility.gameCpuCores").props.onChange("all");
  app.control("1", "SelectEdit", "compatibility.fexPreset").props.onChange("fast");
  await app.control("1", "SelectEdit", "compatibility.gameResolution").props.onChange("Native");
  app.render();
  app.control("1", "ButtonRow", "compatibility.addVariable").props.onClick();
  app.modals.at(-1)!.props.onSave("EXAMPLE", "1");
  app.control(null, "SelectEdit", "compatibility.fexPreset").props.onChange("default");
  app.setConfig((current: any) => ({ ...current, tweaks: { ...current.tweaks,
    global: { ...current.tweaks.global, cores: "0-3", env: { EXAMPLE: "2" } },
  } }));
  await app.settle();
  assert.equal(app.control("1", "SelectEdit", "compatibility.gameCpuCores").props.value, "all");
  assert.equal(app.control("1", "SelectEdit", "compatibility.fexPreset").props.value, "fast");
  assert.equal(app.control("1", "SelectEdit", "compatibility.gameResolution").props.value, "Native");
  assert.equal(app.config.tweaks.games["1"].env.EXAMPLE, "1");
  assert.equal(app.config.tweaks.games["2"], undefined);
  app.select("");
  app.render();
  assert.equal(app.config.selectedGame, null);
  assert.equal(app.config.game.appid, "1");
  assert.ok(app.editor(null));
});

test("inherited FEX and environment settings follow defaults without deleting unrelated overrides", () => {
  const app = setup({ tweaks: {
    global: { windowsCompatTool: FOLLOW_STEAM_COMPAT, fexProfile: "default", env: { GLOBAL: "1" } },
    games: { "1": { fexProfile: "custom", fexConfig: { Multiblock: "0" }, scheduler: "eevdf", env: { LOCAL: "2" } } },
  } });
  app.control("1", "SelectEdit", "compatibility.fexPreset").props.onChange("");
  app.control("1", "ToggleRow", "GLOBAL=1").props.onChange(false);
  assert.equal(app.config.tweaks.games["1"].fexConfig, undefined);
  assert.equal(app.config.tweaks.games["1"].env.GLOBAL, null);
  assert.equal(app.config.tweaks.games["1"].env.LOCAL, "2");
  app.render();
  app.control("1", "ToggleRow", "GLOBAL=1").props.onChange(true);
  app.control(null, "SelectEdit", "compatibility.fexPreset").props.onChange("fast");
  app.render();
  assert.equal(app.control("1", "SelectEdit", "compatibility.fexPreset").props.value, "");
  assert.equal(app.config.tweaks.games["1"].scheduler, "eevdf");
  assert.equal(app.config.tweaks.games["1"].env.GLOBAL, undefined);
  assert.equal(app.config.tweaks.global.env.GLOBAL, "1");
});

test("variable drafts survive type changes and save into their original game with newer variables intact", () => {
  const app = setup({ envPresets: variablePresets, tweaks: {
    global: { windowsCompatTool: FOLLOW_STEAM_COMPAT, env: { COMMON_OPTION: "off" } },
    games: { "1": { enabled: true, env: { EXISTING: "1" } }, "2": { enabled: true } },
  } });
  app.control("1", "ButtonRow", "compatibility.addVariable").props.onClick();
  app.render();
  app.modalControl("SelectEdit", "common.name").props.onChange("COMMON_OPTION");
  app.render();
  app.modalControl("SelectEdit", "common.value").props.onChange("on");
  app.modalControl("SelectEdit", "compatibility.variableType").props.onChange("custom");
  app.render();
  app.modalControl("TextEdit", "common.name").props.onChange("CUSTOM_FLAG");
  app.modalControl("TextEdit", "common.value").props.onChange("custom value");
  app.modalControl("SelectEdit", "compatibility.variableType").props.onChange("common");
  app.render();
  assert.equal(app.modalControl("SelectEdit", "common.value").props.value, "on");
  app.modalControl("SelectEdit", "compatibility.variableType").props.onChange("custom");
  app.render();
  assert.equal(app.modalControl("TextEdit", "common.value").props.value, "custom value");
  app.setConfig((current: any) => ({ ...current, tweaks: { ...current.tweaks, games: {
    ...current.tweaks.games, "1": { ...current.tweaks.games["1"], env: { EXISTING: "newer", ADDED: "3" } },
  } } }));
  app.select("2");
  app.modalControl("DialogButton", "common.save").props.onClick();
  app.render();
  assert.deepEqual({ ...app.config.tweaks.games["1"].env }, { EXISTING: "newer", ADDED: "3", CUSTOM_FLAG: "custom value" });
  assert.equal(app.config.tweaks.games["2"].env, undefined);
  assert.equal(app.config.tweaks.global.env.COMMON_OPTION, "off");
  assert.equal(app.modalOpen(), false);
});
