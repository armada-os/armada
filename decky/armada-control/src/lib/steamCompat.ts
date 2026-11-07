import {
  defaultWindowsCompatTool,
  type CompatTool,
} from "./protonPolicy";
import { readCompatTools } from "./compatTools";
import { getCompatManagerTools } from "./compatManager";
import { runGameSettingsMutation } from "./gameSettingsQueue";
import type { GameTweak } from "../types";
export {
  defaultWindowsCompatTool,
} from "./protonPolicy";
export type { CompatTool } from "./protonPolicy";

export interface CompatState {
  tool: string;
  priority: number;
}

type CompatRoute = "windows" | "linux";

const STEAM_SHORTCUT_APP_TYPE = 1073741824;
// EAppType 1 Game, 2 Application, 8 Demo. Tool (4) stays out so Proton, the Steam
// Linux Runtimes and FEX never get launch options or a compat pin.
const MANAGED_APP_TYPES = new Set([1, 2, 8]);

function isManagedType(type: number | null): boolean {
  return type !== null && MANAGED_APP_TYPES.has(type);
}

const apps = () => window.SteamClient?.Apps;

export const USE_DEFAULT_COMPAT = "__armada_default__";
export const FOLLOW_STEAM_COMPAT = "__steam_default__";
let windowsCompatTool = "";
let compatPolicyRevision = 0;
let windowsCompatDefaults: string[] = [];
let autoApplyCompat = true;
const handledAppids = new Set<string>();
let handledHistoryLoaded: boolean | undefined;
let finishHandledHistory = () => {};
const handledHistoryReady = new Promise<void>((resolve) => { finishHandledHistory = resolve; });
let handledSaveQueue: Promise<void> = Promise.resolve();
const explicitCompatAppids = new Set<string>();
type GameCompatProfile = Pick<GameTweak, "enabled" | "steamCompatTool">;
const gameCompatProfiles = new Map<string, GameCompatProfile>();
// Keep choices made while the startup configuration is still loading.
let pendingPolicy: {
  tool?: string;
  autoApply?: boolean;
  replaceGames?: boolean;
  games: Array<[string, GameCompatProfile | null]>;
} | null = { games: [] };
let protonToolsCache: CompatTool[] = [];
let protonToolsCachedAt = 0;
let protonToolsRequest: Promise<CompatTool[]> | null = null;
const compatWrites = new Map<string, CompatState>();
const compatListeners = new Map<string, Set<(state: CompatState | null) => void>>();
const detailsRequests = new Map<string, Promise<any>>();
const failedMigrations = new Map<string, { previousTool: string; state: CompatState | null }>();

function compatState(appid: string, details: any): CompatState | null {
  const state = typeof details?.strCompatToolName === "string" ? { tool: details.strCompatToolName, priority: Number(details.nCompatToolPriority || 0) } : null;
  const written = compatWrites.get(appid);
  if (!written) return state;
  const confirmed = state && (written.priority < 250 ? state.priority < 250 : state.priority >= 250 && state.tool === written.tool);
  if (confirmed) {
    compatWrites.delete(appid);
    return state;
  }
  return written.priority < 250 && state ? { ...state, priority: 0 } : written;
}

export function subscribeCompatState(appid: string, listener: (state: CompatState | null) => void): () => void {
  const listeners = compatListeners.get(appid) || new Set();
  compatListeners.set(appid, listeners);
  listeners.add(listener);
  let subscribed = true;
  const handle = apps()?.RegisterForAppDetails?.(Number(appid), (details: any) => {
    if (!details) return;
    // Native callbacks can arrive after Steam has already replaced their snapshot.
    void Promise.resolve().then(() => {
      if (!subscribed) return;
      const current = appDetails(appid);
      listener(compatState(appid, typeof current?.strCompatToolName === "string" ? current : details));
    });
  });
  return () => {
    subscribed = false;
    listeners.delete(listener);
    if (!listeners.size) compatListeners.delete(appid);
    handle?.unregister?.();
  };
}

export function setWindowsCompatTool(toolName: string | undefined): void {
  windowsCompatTool = toolName || "";
  if (pendingPolicy) pendingPolicy.tool = windowsCompatTool;
  compatPolicyRevision++;
}

export function getCompatPolicyRevision(): number {
  return compatPolicyRevision;
}

// A saved default can name a tool a later release stopped shipping.
async function effectiveWindowsCompatTool(): Promise<string> {
  if (windowsCompatTool === FOLLOW_STEAM_COMPAT) return FOLLOW_STEAM_COMPAT;
  const tools = await getProtonTools();
  if (!tools.length) return "";
  if (windowsCompatTool && tools.some((tool) => tool.id === windowsCompatTool)) return windowsCompatTool;
  return defaultWindowsCompatTool(tools, windowsCompatDefaults);
}

// Steam keeps reporting stale details for an app whose tool went missing, so a write
// to one can never be confirmed; take the call at its word.
async function repinToTool(appid: string, tool: string): Promise<boolean> {
  try {
    await specifyCompatTool(appid, tool);
  } catch (error) {
    return false;
  }
  markCompatHandled(appid);
  return true;
}

export function configureCompatPolicy(
  toolName: string | undefined,
  autoApply: boolean,
  appids: string[],
  defaults: string[] = [],
  games: Record<string, GameTweak> = {},
): void {
  const pending = pendingPolicy;
  pendingPolicy = null;
  if (pending) {
    toolName = pending.tool ?? toolName;
    autoApply = pending.autoApply ?? autoApply;
    appids = [...appids, ...handledAppids];
    games = { ...(pending.replaceGames ? {} : games) };
    for (const [appid, patch] of pending.games) {
      if (patch) games[appid] = { ...games[appid], ...patch };
      else delete games[appid];
    }
  }
  setWindowsCompatTool(toolName);
  windowsCompatDefaults = defaults.map(String).filter(Boolean);
  autoApplyCompat = autoApply;
  setGameCompatProfiles(games);
  handledAppids.clear();
  for (const appid of appids) {
    const id = String(appid);
    if (/^\d+$/.test(id)) handledAppids.add(id);
  }
}

export function setGameCompatProfiles(games: Record<string, GameTweak>): void {
  if (pendingPolicy) {
    pendingPolicy.replaceGames = true;
    pendingPolicy.games = [];
  }
  explicitCompatAppids.clear();
  gameCompatProfiles.clear();
  for (const [appid, game] of Object.entries(games)) {
    updateGameCompatProfile(appid, { enabled: game.enabled, steamCompatTool: game.steamCompatTool });
  }
}

export function updateGameCompatProfile(appid: string, patch: GameCompatProfile | null): void {
  pendingPolicy?.games.push([appid, patch ? { ...patch } : null]);
  if (!patch) {
    gameCompatProfiles.delete(appid);
    explicitCompatAppids.delete(appid);
    return;
  }
  const game = { ...gameCompatProfiles.get(appid), ...patch };
  gameCompatProfiles.set(appid, game);
  if (game.enabled !== false && game.steamCompatTool && game.steamCompatTool !== USE_DEFAULT_COMPAT) {
    explicitCompatAppids.add(appid);
  } else {
    explicitCompatAppids.delete(appid);
  }
}

export function setAutoApplyCompat(enabled: boolean): void {
  autoApplyCompat = enabled;
  if (pendingPolicy) pendingPolicy.autoApply = enabled;
}

export function handledGameAppids(): string[] {
  return Array.from(handledAppids).sort((a, b) => Number(a) - Number(b));
}

export function initializeHandledGames(appids: string[] | null): void {
  if (handledHistoryLoaded !== undefined) return;
  handledHistoryLoaded = appids !== null;
  for (const appid of appids || []) {
    const id = String(appid);
    if (/^\d+$/.test(id)) handledAppids.add(id);
  }
  finishHandledHistory();
}

export function persistHandledGames(save: (appids: string[]) => Promise<unknown>): Promise<void> {
  const request = handledSaveQueue.then(async () => {
    // An early edit must not replace history that has not loaded yet.
    await handledHistoryReady;
    if (handledHistoryLoaded) await save(handledGameAppids());
  });
  handledSaveQueue = request.catch(() => {});
  return request;
}

export function markCompatHandled(appid: string): boolean {
  const size = handledAppids.size;
  handledAppids.add(appid);
  return handledAppids.size !== size;
}

export async function getProtonTools(refresh = false): Promise<CompatTool[]> {
  if (!refresh && protonToolsCache.length && Date.now() - protonToolsCachedAt < 5000) return protonToolsCache;
  if (protonToolsRequest) return protonToolsRequest;
  protonToolsRequest = (async () => {
    try {
      // Steam exposes Proton globally; per-app Linux runtimes only appear in available tools.
      const tools = await readCompatTools(window.SteamClient, getCompatManagerTools);
      if (tools.length) {
        protonToolsCache = tools;
        protonToolsCachedAt = Date.now();
      }
      return tools.length ? tools : protonToolsCache;
    } catch (error) {
      return protonToolsCache;
    } finally {
      protonToolsRequest = null;
    }
  })();
  return protonToolsRequest;
}

// A game's supported tools per Steam's OS filtering (Proton, plus SLR for a Linux depot); for the per-game picker.
export async function getAppCompatTools(appid: string): Promise<CompatTool[]> {
  try {
    return await readCompatTools(window.SteamClient, getCompatManagerTools, Number(appid));
  } catch (error) {
    return [];
  }
}

function appDetails(appid: string): any {
  try {
    return window.appDetailsStore?.GetAppDetails?.(Number(appid)) || null;
  } catch (error) {
    return null;
  }
}

export async function resolveCompatState(appid: string): Promise<CompatState | null> {
  return compatState(appid, await resolveDetails(appid, "strCompatToolName"));
}

export function compatSelection(state: CompatState | null, defaultTool?: string): string {
  if (!state || !state.tool || state.priority < 250) return FOLLOW_STEAM_COMPAT;
  return state.tool === (defaultTool || windowsCompatTool) ? USE_DEFAULT_COMPAT : state.tool;
}

export async function specifyCompatTool(appid: string, toolName: string): Promise<void> {
  const store = apps();
  if (!store?.SpecifyCompatTool) throw new Error("Steam compatibility settings are unavailable");
  const tool = toolName === FOLLOW_STEAM_COMPAT ? "" : toolName;
  await store.SpecifyCompatTool(Number(appid), tool);
  // Steam can acknowledge the write before its details cache changes.
  const state = { tool, priority: tool ? 250 : 0 };
  compatWrites.set(appid, state);
  for (const listener of compatListeners.get(appid) || []) listener(state);
}

const delay = (ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms));

function requestAppDetails(appid: string): void {
  // Not in @decky/ui's type defs (incomplete); exists on the runtime store.
  try {
    (window.appDetailsStore as any)?.RequestAppDetails?.(Number(appid));
  } catch (error) {
  }
}

// Absolute path: launch options run via a shell without /usr/libexec on PATH.
const LAUNCH_WRAPPER = "/usr/libexec/armada/armada-game-launch";
const COMMAND_TOKEN = "%command%";
const DEFAULT_LAUNCH_OPTIONS = `${LAUNCH_WRAPPER} ${COMMAND_TOKEN}`;

// null when already wrapped (idempotent); preserves user options around %command%.
export function wrapLaunchOptions(current: string): string | null {
  const opts = current || "";
  if (opts.includes(LAUNCH_WRAPPER)) return null;
  if (opts.includes(COMMAND_TOKEN)) {
    return opts.replace(COMMAND_TOKEN, DEFAULT_LAUNCH_OPTIONS);
  }
  // No %command%: Steam appends bare options as args, so keep them after it.
  const trimmed = opts.trim();
  return trimmed
    ? `${DEFAULT_LAUNCH_OPTIONS} ${trimmed}`
    : DEFAULT_LAUNCH_OPTIONS;
}

async function resolveDetails(appid: string, field: "strLaunchOptions" | "strCompatToolName" = "strLaunchOptions"): Promise<any> {
  const key = `${appid}:${field}`;
  const cached = appDetails(appid);
  if (typeof cached?.[field] === "string") return cached;
  const pending = detailsRequests.get(key);
  if (pending) return pending;
  const request = (async () => {
    const waiter = waitForAppDetails(appid, (details) => typeof details[field] === "string", 1500, 250);
    requestAppDetails(appid);
    const loaded = await waiter.promise || appDetails(appid);
    return typeof loaded?.[field] === "string" ? loaded : null;
  })();
  detailsRequests.set(key, request);
  try {
    return await request;
  } finally {
    if (detailsRequests.get(key) === request) detailsRequests.delete(key);
  }
}

function resolveSettledCompatDetails(appid: string): Promise<any> {
  return waitForAppDetails(appid, (details) => typeof details.strCompatToolName === "string", 1500, 250, true).promise;
}

// Polls because overviews load a beat after plugin init.
async function resolveOverviewType(appid: string): Promise<number | null> {
  for (let i = 0; i < 5; i++) {
    try {
      const type = (window as any).appStore?.GetAppOverviewByAppID?.(Number(appid))?.app_type;
      if (type != null) return type;
    } catch (error) {
    }
    await delay(1000);
  }
  return null;
}

async function resolveCompatRoute(currentTool: string): Promise<CompatRoute | null> {
  if (!currentTool) return "linux";
  const protonTools = await getProtonTools();
  if (!protonTools.length) return null;
  return protonTools.some((tool) => tool.id === currentTool) ? "windows" : "linux";
}

function waitForAppDetails(
  appid: string,
  accepts: (details: any) => boolean,
  timeoutMs = 1000,
  refreshMs = 0,
  settleEmpty = false,
): { promise: Promise<any>; cancel: () => void } {
  let cancel = () => {};
  const promise = new Promise<any>((resolve) => {
    const store = apps();
    if (!store?.RegisterForAppDetails) {
      resolve(null);
      return;
    }
    let done = false;
    let handle: any;
    let timeout: number | undefined;
    let refresh: number | undefined;
    let emptyTimer: number | undefined;
    let unregisterPending = false;
    const finish = (details: any) => {
      if (done) return;
      done = true;
      if (timeout !== undefined) window.clearTimeout(timeout);
      if (refresh !== undefined) window.clearInterval(refresh);
      if (emptyTimer !== undefined) window.clearTimeout(emptyTimer);
      if (handle) {
        try {
          handle.unregister?.();
        } catch (error) {
        }
      } else {
        unregisterPending = true;
      }
      resolve(details || null);
    };
    cancel = () => finish(null);
    const accept = (details: any) => {
      if (!details || !accepts(details)) return;
      if (!settleEmpty || String(details.strCompatToolName || "")) {
        finish(details);
      } else if (emptyTimer === undefined) {
        emptyTimer = window.setTimeout(() => finish(details), 500);
      }
    };
    try {
      handle = store.RegisterForAppDetails(Number(appid), accept);
      if (unregisterPending) handle?.unregister?.();
    } catch (error) {
      finish(null);
      return;
    }
    if (!done) {
      timeout = window.setTimeout(() => finish(null), timeoutMs);
      if (refreshMs > 0) refresh = window.setInterval(() => requestAppDetails(appid), refreshMs);
    }
  });
  return { promise, cancel };
}

async function clearCompatToolAndResolveRoute(appid: string): Promise<CompatRoute | null> {
  const waiter = waitForAppDetails(
    appid,
    (details) => typeof details.strCompatToolName === "string" && Number(details.nCompatToolPriority || 0) < 250,
    5000,
    250,
    true,
  );
  try {
    await specifyCompatTool(appid, "");
  } catch (error) {
    waiter.cancel();
    return null;
  }
  requestAppDetails(appid);
  const details = await waiter.promise;
  if (!details) return null;
  return resolveCompatRoute(String(details.strCompatToolName || ""));
}

async function applyCompatDefaultForRoute(appid: string, route: CompatRoute | null): Promise<boolean> {
  if (windowsCompatTool === FOLLOW_STEAM_COMPAT) return repinToTool(appid, "");
  if (route === null) return false;
  if (route === "linux") {
    markCompatHandled(appid);
    return true;
  }
  const tool = await effectiveWindowsCompatTool();
  if (!tool) return false;
  return repinToTool(appid, tool);
}

// Trust allowShortcut only for IDs discovered in shortcuts.vdf; other app types stay untouched.
export async function applyLaunchWrapperToGame(appid: string, allowShortcut = false): Promise<boolean> {
  const type = await resolveOverviewType(appid);
  if (type === null) return false;
  if (!isManagedType(type) && !(allowShortcut && type === STEAM_SHORTCUT_APP_TYPE)) return true;
  const details = await resolveDetails(appid);
  if (!details) return false;
  const next = wrapLaunchOptions(String(details.strLaunchOptions || ""));
  if (next === null) return true;
  const store = apps();
  if (!store?.SetAppLaunchOptions) return false;
  try {
    await store.SetAppLaunchOptions(Number(appid), next);
    return true;
  } catch (error) {
    return false;
  }
}

export async function resetLaunchOptionsForGame(appid: string, attempts = 3): Promise<boolean> {
  for (let attempt = 0; attempt < attempts; attempt++) {
    const type = await resolveOverviewType(appid);
    if (type !== null) {
      if (!isManagedType(type)) return true;
      const store = apps();
      if (store?.SetAppLaunchOptions) {
        try {
          await store.SetAppLaunchOptions(Number(appid), DEFAULT_LAUNCH_OPTIONS);
          return true;
        } catch (error) {
        }
      }
    }
    if (attempt + 1 < attempts) await delay(500);
  }
  return false;
}

async function applyWindowsCompatDefault(appid: string): Promise<boolean> {
  const type = await resolveOverviewType(appid);
  if (type === null) return false;
  if (!isManagedType(type)) return true;
  if (handledAppids.has(appid)) return true;
  const details = await resolveSettledCompatDetails(appid);
  if (!details) return false;
  if (!autoApplyCompat || handledHistoryLoaded === false || windowsCompatTool === FOLLOW_STEAM_COMPAT || Number(details.nCompatToolPriority || 0) >= 250) {
    markCompatHandled(appid);
    return true;
  }
  const route = await resolveCompatRoute(String(details.strCompatToolName || ""));
  return applyCompatDefaultForRoute(appid, route);
}

async function applyGamePolicy(appid: string, nonSteam = false): Promise<boolean> {
  if (await resolveOverviewType(appid) === null || !(await resolveDetails(appid))) return false;
  return runGameSettingsMutation(async () => {
    const wrapped = await applyLaunchWrapperToGame(appid, nonSteam);
    if (nonSteam || explicitCompatAppids.has(appid)) return wrapped;
    const compat = await applyWindowsCompatDefault(appid);
    return wrapped && compat;
  }, "background");
}

async function applyGamePolicyWithRetries(appid: string, onHandledChange: () => void): Promise<void> {
  const before = handledAppids.size;
  for (let attempt = 0; attempt < 6; attempt++) {
    if (await applyGamePolicy(appid)) {
      if (handledAppids.size !== before) onHandledChange();
      return;
    }
    await delay(5000);
  }
}

// Steam reports an unresolvable tool as unset, so oldTool matches nothing; pinnedAppids carries those games.
export async function migrateWindowsCompatTool(
  appids: string[],
  oldTool: string,
  newTool: string,
  pinnedAppids?: string[] | null,
): Promise<void> {
  if (!oldTool || oldTool === newTool && !failedMigrations.size) return;
  if (newTool !== FOLLOW_STEAM_COMPAT) {
    const protonTools = await getProtonTools();
    if (!protonTools.some((tool) => tool.id === newTool)) throw new Error("Steam compatibility settings are unavailable");
  }
  setWindowsCompatTool(newTool);
  const pinned = pinnedAppids ? new Set(pinnedAppids.map(String)) : null;
  const failures: string[] = [];
  let next = 0;
  const worker = async () => {
    while (next < appids.length) {
      const appid = appids[next++];
      if (explicitCompatAppids.has(appid)) { failedMigrations.delete(appid); continue; }
      const retry = failedMigrations.get(appid);
      if (oldTool === newTool && !retry) continue;
      if (pinned && !pinned.has(appid) && !retry) continue;
      let state: CompatState | null = null;
      try {
        const type = await resolveOverviewType(appid);
        if (type === null) throw new Error("Steam game details are unavailable");
        if (!isManagedType(type)) { failedMigrations.delete(appid); continue; }
        state = await resolveCompatState(appid);
        if (!state) throw new Error("Steam game details are unavailable");
        if (retry?.state) {
          if (state.priority !== retry.state.priority || state.tool !== retry.state.tool) {
            failedMigrations.delete(appid);
            continue;
          }
        } else if (pinned) {
          // A pin the client can resolve means the stored record is stale.
          if (state.priority >= 250) continue;
        } else if ((retry?.previousTool || oldTool) === FOLLOW_STEAM_COMPAT) {
          if (state.priority >= 250 || await resolveCompatRoute(state.tool) !== "windows") continue;
        } else if (state.priority < 250 || state.tool !== (retry?.previousTool || oldTool)) {
          continue;
        }
        let applied = false;
        for (let attempt = 0; attempt < 3 && !applied; attempt++) {
          applied = await repinToTool(appid, newTool === FOLLOW_STEAM_COMPAT ? "" : newTool);
        }
        if (!applied) throw new Error("Could not apply the global compatibility tool");
        failedMigrations.delete(appid);
      } catch (error) {
        failedMigrations.set(appid, { previousTool: retry?.previousTool || oldTool, state });
        failures.push(`${appid}: ${String(error)}`);
      }
    }
  };
  await Promise.all(Array.from({ length: Math.min(10, appids.length) }, worker));
  if (failures.length) throw new Error(failures.join("\n"));
}

export async function resetCompatToolToDefault(appid: string, pinnedAppids?: string[] | null): Promise<string> {
  const type = await resolveOverviewType(appid);
  if (type === STEAM_SHORTCUT_APP_TYPE) {
    await specifyCompatTool(appid, "");
    return "";
  }
  if (!isManagedType(type)) throw new Error("Steam game details are unavailable");
  const tool = await effectiveWindowsCompatTool();
  if (tool === FOLLOW_STEAM_COMPAT) {
    await specifyCompatTool(appid, "");
    markCompatHandled(appid);
    return "";
  }
  // Clearing first needs a default to put back and a known pin state; null is unknown.
  if (!tool || pinnedAppids === null) throw new Error("Steam compatibility settings are unavailable");
  const current = await resolveCompatState(appid);
  if (current?.priority && current.priority >= 250 && current.tool === tool) return tool;
  // A dangling pin reads as unset, so clearing it first would route the game as Linux.
  if (pinnedAppids?.includes(appid)) {
    if (!(await repinToTool(appid, tool))) throw new Error("Could not apply the global compatibility tool");
    return tool;
  }
  const route = await clearCompatToolAndResolveRoute(appid);
  if (!(await applyCompatDefaultForRoute(appid, route))) throw new Error("Could not apply the global compatibility tool");
  return route === "windows" ? tool : "";
}

export async function resetAllGamePolicies(appids: string[], pinnedAppids?: string[] | null): Promise<void> {
  await getProtonTools(true);
  let next = 0;
  const failures: string[] = [];
  const worker = async () => {
    while (next < appids.length) {
      const appid = appids[next++];
      try {
        await resetCompatToolToDefault(appid, pinnedAppids);
        if (!(await resetLaunchOptionsForGame(appid))) throw new Error("Could not reset Steam launch options");
      } catch (error) {
        failures.push(`${appid}: ${String(error)}`);
      }
    }
  };
  await Promise.all(Array.from({ length: Math.min(10, appids.length) }, worker));
  if (failures.length) throw new Error(failures.join("\n"));
}

// Unknown app_type (overview not loaded yet) is treated as a game so a real game is never hidden.
export function isGameApp(appid: string): boolean {
  try {
    const type = (window as any).appStore?.GetAppOverviewByAppID?.(Number(appid))?.app_type;
    return type == null || MANAGED_APP_TYPES.has(type);
  } catch (error) {
    return true;
  }
}

export function isNonSteamApp(appid: string): boolean {
  try {
    return (window as any).appStore?.GetAppOverviewByAppID?.(Number(appid))?.app_type
      === STEAM_SHORTCUT_APP_TYPE;
  } catch (error) {
    return false;
  }
}

export async function resolveProfileAppids(appids: string[]): Promise<string[]> {
  const games: string[] = [];
  let next = 0;
  const worker = async () => {
    while (next < appids.length) {
      const appid = appids[next++];
      const type = await resolveOverviewType(appid);
      if (isManagedType(type) || type === STEAM_SHORTCUT_APP_TYPE) games.push(appid);
    }
  };
  await Promise.all(Array.from({ length: Math.min(10, appids.length) }, worker));
  return games;
}

// Manifests include tools/runtimes, so type-check each; cold overviews are retried across rounds, not dropped.
export async function sweepInstalledGames(games: Array<{ appid: string; nonSteam?: boolean }>): Promise<void> {
  const steamAppids = games.filter((game) => !game.nonSteam).map((game) => String(game.appid));
  const installed = new Set(steamAppids);
  for (const appid of handledAppids) {
    if (!installed.has(appid)) handledAppids.delete(appid);
  }
  let pending = games
    .map((game) => ({ appid: String(game.appid), nonSteam: Boolean(game.nonSteam) }))
    .filter((game) => game.nonSteam || isGameApp(game.appid));
  for (let round = 0; round < 6 && pending.length; round++) {
    if (round > 0) await delay(5000);
    const unresolved: typeof pending = [];
    let next = 0;
    const worker = async () => {
      while (next < pending.length) {
        const game = pending[next++];
        if (!(await applyGamePolicy(game.appid, game.nonSteam))) unresolved.push(game);
      }
    };
    await Promise.all(Array.from({ length: Math.min(10, pending.length) }, worker));
    pending = unresolved;
  }
}

export function registerDownloadWatcher(onHandledChange: () => void): () => void {
  const downloads = window.SteamClient?.Downloads;
  if (!downloads?.RegisterForDownloadItems) return () => {};
  let timer: number | undefined;
  const pending = new Set<string>();
  const flush = () => {
    timer = undefined;
    for (const appid of pending) {
      applyGamePolicyWithRetries(appid, onHandledChange);
    }
    pending.clear();
  };
  // Each queue item is { remote_client_id, item_data: [{ appid, ... }] } - the
  // appids live in the item_data entries, not on the item itself.
  const handle = downloads.RegisterForDownloadItems((_paused: boolean, items: any[]) => {
    if (!Array.isArray(items)) return;
    for (const item of items) {
      const entries = item?.item_data;
      if (!entries || typeof entries !== "object") continue;
      for (const entry of Object.values(entries) as any[]) {
        const appid = String(entry?.appid ?? "");
        if (appid && appid !== "0" && isGameApp(appid)) pending.add(appid);
      }
    }
    if (timer === undefined) timer = window.setTimeout(flush, 1500);
  });
  return () => {
    if (timer !== undefined) window.clearTimeout(timer);
    try {
      handle?.unregister?.();
    } catch (error) {
    }
  };
}
