import { configFieldRevision, markConfigFieldChange } from "../../src/lib/configMutation.ts";
import * as configSections from "../../src/lib/configSections.ts";
import { loadModule } from "./loadModule.ts";

type Game = { appid: string; name: string };

export function createContentFixture({ games = [], autoLoad = false }: { games?: Game[]; autoLoad?: boolean } = {}) {
  const slots: any[] = [];
  const setters = new Map<number, (next: any) => void>();
  const effects = new Map<number, { dependencies: any[]; effect: () => (() => void) | undefined; cleanup?: () => void }>();
  const timers = new Set<() => void>();
  const requests: ReturnType<typeof Promise.withResolvers>[] = [];
  const readers: string[] = [];
  let pending: Array<() => void> = [];
  let runtimeGame: Game | null = null;
  let cursor = 0;
  let saveOptions: any;
  let tree: any;
  const resolve = (index: number, marker = "loaded") => requests[index].resolve({
    tweaks: { global: { marker }, games: {} }, installedGames: [], rgbSupported: false,
  });
  const request = (kind: string) => {
    readers.push(kind);
    const next = Promise.withResolvers<any>();
    requests.push(next);
    if (autoLoad) resolve(requests.length - 1);
    return next.promise;
  };
  const react = {
    useState: (initial: any) => {
      const index = cursor++;
      if (!(index in slots)) slots[index] = typeof initial === "function" ? initial() : initial;
      if (!setters.has(index)) setters.set(index, (next: any) => {
        slots[index] = typeof next === "function" ? next(slots[index]) : next;
      });
      return [slots[index], setters.get(index)];
    },
    useRef: (initial: any) => {
      const index = cursor++;
      if (!(index in slots)) slots[index] = { current: initial };
      return slots[index];
    },
    useCallback: (callback: any, dependencies: any[]) => {
      const index = cursor++;
      const previous = slots[index];
      if (!previous || dependencies.length !== previous.dependencies.length || !dependencies.every((value, i) => Object.is(value, previous.dependencies[i]))) slots[index] = { callback, dependencies };
      return slots[index].callback;
    },
    useEffect: (effect: () => (() => void) | undefined, dependencies: any[]) => {
      const index = cursor++;
      const previous = effects.get(index);
      if (previous && dependencies.length === previous.dependencies.length && dependencies.every((value, i) => Object.is(value, previous.dependencies[i]))) return;
      pending.push(() => {
        previous?.cleanup?.();
        effects.set(index, { dependencies, effect, cleanup: effect() });
      });
    },
  };
  const components = ["components/TabNavigation", "components/ArmadaStyles", "components/LoadingState", "components/ConfigSection",
    "tabs/Compatibility", "tabs/Profiles", "tabs/Controller", "tabs/DeviceSettings", "tabs/Experimental", "tabs/About"];
  const api = loadModule("Content.tsx", {
    react,
    "@decky/api": { toaster: { toast: () => {} } },
    "@decky/ui": { PanelSection: "PanelSection" },
    "./backend": {
      getConfig: () => request("full"), getInitialConfig: () => request("initial"), getStartupConfig: () => request("startup"),
      getStartupInstalledGames: async () => games,
    },
    "./lib/configSections": configSections,
    "./lib/configMutation": { configFieldRevision },
    "./components/widgets": { SupportingText: "SupportingText", ButtonRow: "ButtonRow" },
    "./hooks/useDebouncedSave": { useDebouncedSave: (options: any) => { saveOptions = options; } },
    "./hooks/useTabData": { useTabData: () => Object.fromEntries(["device", "controller", "profiles", "experimental", "about", "rgb", "fans", "logs", "game"].map((key) => [key, { loading: true, error: "", value: null }])) },
    "./hooks/useLocale": { useLocale: () => {} },
    "./lib/games": { currentGame: () => runtimeGame },
    "./i18n": { t: (key: string) => key },
    "./icons": { tabIcons: {} },
    ...Object.fromEntries(components.map((path) => { const name = path.split("/").at(-1)!; return [`./${path}`, { [name]: name }]; })),
  }, { window: {
    setInterval: (callback: () => void) => { timers.add(callback); return callback; },
    clearInterval: (callback: () => void) => timers.delete(callback),
  } });
  function render() {
    cursor = 0;
    tree = api.Content();
    const next = pending;
    pending = [];
    next.forEach((effect) => effect());
    return tree;
  }
  async function settle() {
    await new Promise((resolve) => setImmediate(resolve));
    render();
    await new Promise((resolve) => setImmediate(resolve));
    render();
  }
  render();
  return {
    requests, readers, resolve, render, settle,
    get config() { return saveOptions.config; },
    get state() { const navigation = tree.props.children[1]; return saveOptions.config ? navigation : navigation.props.tabs[0].content; },
    reload: () => saveOptions.onError(),
    edit: (update: (current: any) => any) => {
      markConfigFieldChange(saveOptions.setConfig, "tweaks");
      saveOptions.setConfig(update);
      render();
    },
    setRuntime: (game: Game | null) => {
      runtimeGame = game;
      for (const callback of timers) callback();
      render();
    },
    select: (selectedGame: Game | null) => {
      const navigation = tree.props.children.find((child: any) => child.type === "TabNavigation");
      navigation.props.tabs.find((tab: any) => tab.id === "Compatibility").content.props.setConfig((current: any) => ({ ...current, selectedGame }));
      render();
    },
    replayEffects: () => {
      for (const effect of effects.values()) effect.cleanup?.();
      for (const effect of effects.values()) effect.cleanup = effect.effect();
    },
    unmount: () => { for (const effect of effects.values()) effect.cleanup?.(); },
  };
}
