export interface CompatTool {
  id: string;
  label: string;
}

export interface CompatState {
  tool: string;
  priority: number;
}

type CompatRoute = "windows" | "linux";

const STEAM_SHORTCUT_APP_TYPE = 1073741824;

const apps = () => window.SteamClient?.Apps;
const settings = () => window.SteamClient?.Settings;

// Keep in sync with PROTON_TOOL_NAME (build) and PROTON_11_STABLE (armada-fixups).
export const DEFAULT_WINDOWS_COMPAT_TOOL = "proton-cachyos-11.0-arm64";
export const USE_DEFAULT_COMPAT = "__armada_default__";
export const FOLLOW_STEAM_COMPAT = "__steam_default__";
let windowsCompatTool = DEFAULT_WINDOWS_COMPAT_TOOL;
let autoApplyCompat = true;
const handledAppids = new Set<string>();
let protonToolsCache: CompatTool[] = [];
let protonToolsCachedAt = 0;
let protonToolsRequest: Promise<CompatTool[]> | null = null;

export function setWindowsCompatTool(toolName: string | undefined): void {
  windowsCompatTool = toolName || DEFAULT_WINDOWS_COMPAT_TOOL;
}

// A saved default can name a tool a later release stopped shipping.
async function effectiveWindowsCompatTool(): Promise<string> {
  const tools = await getProtonTools();
  if (!tools.length) return "";
  if (tools.some((tool) => tool.id === windowsCompatTool)) return windowsCompatTool;
  return tools.some((tool) => tool.id === DEFAULT_WINDOWS_COMPAT_TOOL) ? DEFAULT_WINDOWS_COMPAT_TOOL : "";
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

export function configureCompatPolicy(toolName: string | undefined, autoApply: boolean, appids: string[]): void {
  setWindowsCompatTool(toolName);
  autoApplyCompat = autoApply;
  handledAppids.clear();
  for (const appid of appids) {
    const id = String(appid);
    if (/^\d+$/.test(id)) handledAppids.add(id);
  }
}

export function setAutoApplyCompat(enabled: boolean): void {
  autoApplyCompat = enabled;
}

export function handledGameAppids(): string[] {
  return Array.from(handledAppids).sort((a, b) => Number(a) - Number(b));
}

export function markCompatHandled(appid: string): boolean {
  const size = handledAppids.size;
  handledAppids.add(appid);
  return handledAppids.size !== size;
}

function mapCompatTools(raw: any): CompatTool[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((tool: any) => ({
      id: String(tool?.strToolName ?? tool?.strName ?? tool?.name ?? ""),
      label: String(tool?.strDisplayName ?? tool?.strToolName ?? tool?.strName ?? ""),
    }))
    .filter((tool: CompatTool) => tool.id);
}

export async function getProtonTools(refresh = false): Promise<CompatTool[]> {
  if (!refresh && protonToolsCache.length && Date.now() - protonToolsCachedAt < 5000) return protonToolsCache;
  if (protonToolsRequest) return protonToolsRequest;
  protonToolsRequest = (async () => {
    try {
      // Steam exposes Proton globally; per-app Linux runtimes only appear in available tools.
      const tools = mapCompatTools(await settings()?.GetGlobalCompatTools?.());
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
    return mapCompatTools(await apps()?.GetAvailableCompatTools?.(Number(appid)));
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
  const details = await resolveDetails(appid);
  if (!details) return null;
  return {
    tool: String(details.strCompatToolName || ""),
    priority: Number(details.nCompatToolPriority || 0),
  };
}

export function compatSelection(state: CompatState | null, defaultTool?: string): string {
  if (!state || !state.tool || state.priority < 250) return FOLLOW_STEAM_COMPAT;
  return state.tool === (defaultTool || windowsCompatTool) ? USE_DEFAULT_COMPAT : state.tool;
}

export async function specifyCompatTool(appid: string, toolName: string): Promise<void> {
  const store = apps();
  if (!store?.SpecifyCompatTool) throw new Error("Steam compatibility settings are unavailable");
  await store.SpecifyCompatTool(Number(appid), toolName);
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

async function resolveDetails(appid: string, attempts = 5): Promise<any> {
  for (let i = 0; i < attempts; i++) {
    const details = await subscribeAppDetails(appid);
    if (details) return details;
    requestAppDetails(appid);
    await delay(250);
  }
  return appDetails(appid);
}

function subscribeAppDetails(appid: string): Promise<any> {
  return waitForAppDetails(appid, () => true).promise;
}

function resolveSettledCompatDetails(appid: string): Promise<any> {
  return waitForAppDetails(appid, () => true, 1500, 250, true).promise;
}

// app_type: 1 = Game. Polls because overviews load a beat after plugin init.
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
    (details) => Number(details.nCompatToolPriority || 0) < 250,
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
  if (route === null) return false;
  if (route === "linux") {
    markCompatHandled(appid);
    return true;
  }
  const tool = await effectiveWindowsCompatTool();
  if (!tool) return false;
  const waiter = waitForAppDetails(
    appid,
    (details) => Number(details.nCompatToolPriority || 0) >= 250
      && String(details.strCompatToolName || "") === tool,
    5000,
    250,
  );
  try {
    await specifyCompatTool(appid, tool);
  } catch (error) {
    waiter.cancel();
    return false;
  }
  requestAppDetails(appid);
  if (!(await waiter.promise)) return false;
  markCompatHandled(appid);
  return true;
}

// Trust allowShortcut only for IDs discovered in shortcuts.vdf; other app types stay untouched.
export async function applyLaunchWrapperToGame(appid: string, allowShortcut = false): Promise<boolean> {
  const type = await resolveOverviewType(appid);
  if (type === null) return false;
  if (type !== 1 && !(allowShortcut && type === STEAM_SHORTCUT_APP_TYPE)) return true;
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
      if (type !== 1) return true;
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
  if (type !== 1) return true;
  if (handledAppids.has(appid)) return true;
  const details = await resolveSettledCompatDetails(appid);
  if (!details) return false;
  if (!autoApplyCompat || Number(details.nCompatToolPriority || 0) >= 250) {
    markCompatHandled(appid);
    return true;
  }
  const route = await resolveCompatRoute(String(details.strCompatToolName || ""));
  return applyCompatDefaultForRoute(appid, route);
}

async function applyGamePolicy(appid: string, nonSteam = false): Promise<boolean> {
  const wrapped = await applyLaunchWrapperToGame(appid, nonSteam);
  if (nonSteam) return wrapped;
  const compat = await applyWindowsCompatDefault(appid);
  return wrapped && compat;
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
  if (!oldTool || oldTool === newTool) return;
  const protonTools = await getProtonTools();
  if (!protonTools.some((tool) => tool.id === newTool)) return;
  setWindowsCompatTool(newTool);
  const pinned = pinnedAppids ? new Set(pinnedAppids.map(String)) : null;
  let next = 0;
  const worker = async () => {
    while (next < appids.length) {
      const appid = appids[next++];
      if (pinned && !pinned.has(appid)) continue;
      const type = await resolveOverviewType(appid);
      if (type !== 1) continue;
      const details = await resolveDetails(appid);
      if (!details) continue;
      const priority = Number(details.nCompatToolPriority || 0);
      if (pinned) {
        // A pin the client can resolve means the stored record is stale.
        if (priority >= 250) continue;
        await repinToTool(appid, newTool);
        continue;
      }
      if (priority < 250 || String(details.strCompatToolName || "") !== oldTool) continue;
      for (let attempt = 0; attempt < 3; attempt++) {
        if (await applyCompatDefaultForRoute(appid, "windows")) break;
      }
    }
  };
  await Promise.all(Array.from({ length: Math.min(10, appids.length) }, worker));
}

export async function resetCompatToolToDefault(appid: string, pinnedAppids?: string[] | null): Promise<string> {
  const type = await resolveOverviewType(appid);
  if (type === STEAM_SHORTCUT_APP_TYPE) {
    await specifyCompatTool(appid, "");
    return "";
  }
  if (type !== 1) return "";
  const tool = await effectiveWindowsCompatTool();
  // Clearing first needs a default to put back and a known pin state; null is unknown.
  if (!tool || pinnedAppids === null) {
    const state = await resolveCompatState(appid);
    return state && state.priority >= 250 ? state.tool : "";
  }
  // A dangling pin reads as unset, so clearing it first would route the game as Linux.
  if (pinnedAppids?.includes(appid)) return (await repinToTool(appid, tool)) ? tool : "";
  const route = await clearCompatToolAndResolveRoute(appid);
  const applied = await applyCompatDefaultForRoute(appid, route);
  return applied && route === "windows" ? tool : "";
}

export async function resetAllGamePolicies(appids: string[], pinnedAppids?: string[] | null): Promise<void> {
  await getProtonTools(true);
  const tool = await effectiveWindowsCompatTool();
  // null pin state is unknown, so leave mappings alone rather than risk stranding one.
  const canResetCompat = Boolean(tool) && pinnedAppids !== null;
  const pinned = pinnedAppids ? new Set(pinnedAppids.map(String)) : null;
  let next = 0;
  const worker = async () => {
    while (next < appids.length) {
      const appid = appids[next++];
      const type = await resolveOverviewType(appid);
      if (type === STEAM_SHORTCUT_APP_TYPE) {
        try {
          await specifyCompatTool(appid, "");
        } catch (error) {
        }
        continue;
      }
      if (type !== 1) continue;
      if (canResetCompat && pinned?.has(appid)) {
        await repinToTool(appid, tool);
      } else if (canResetCompat) {
        await applyCompatDefaultForRoute(appid, await clearCompatToolAndResolveRoute(appid));
      }
      await resetLaunchOptionsForGame(appid);
    }
  };
  await Promise.all(Array.from({ length: Math.min(10, appids.length) }, worker));
}

// Unknown app_type (overview not loaded yet) is treated as a game so a real game is never hidden.
export function isGameApp(appid: string): boolean {
  try {
    const type = (window as any).appStore?.GetAppOverviewByAppID?.(Number(appid))?.app_type;
    return type == null || type === 1;
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
      if (type === 1 || type === STEAM_SHORTCUT_APP_TYPE) games.push(appid);
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
