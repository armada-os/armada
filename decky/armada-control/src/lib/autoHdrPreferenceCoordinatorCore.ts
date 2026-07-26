import type {
  AutoHdrAppOverride,
  AutoHdrPreference,
  AutoHdrPreferencePatch,
  AutoHdrPreferencesSnapshot,
  AutoHdrScope,
} from "../types";

export const AUTO_HDR_SCOPE_POLL_MS = 500;

export interface AutoHdrActiveScope {
  scope: AutoHdrScope;
  appId: string | null;
}

export function resolveAutoHdrPreference(
  globalPreference: AutoHdrPreference,
  override: AutoHdrAppOverride | null | undefined,
): AutoHdrPreference {
  return {
    enabled: override?.enabled ?? globalPreference.enabled,
  };
}

export interface AutoHdrCoordinatorSnapshot {
  initialized: boolean;
  preferences?: AutoHdrPreferencesSnapshot;
  error: string;
}

type Listener = (snapshot: AutoHdrCoordinatorSnapshot) => void;
type TimerHandle = ReturnType<typeof globalThis.setTimeout>;

export interface AutoHdrPreferenceCoordinatorOptions {
  resolveScope: () => AutoHdrActiveScope;
  read: (
    scope: AutoHdrScope,
    appId: string | null,
  ) => Promise<AutoHdrPreferencesSnapshot>;
  reconcile: (
    scope: AutoHdrScope,
    appId: string | null,
  ) => Promise<AutoHdrPreferencesSnapshot>;
  update: (
    targetScope: AutoHdrScope,
    targetAppId: string | null,
    activeScope: AutoHdrScope,
    activeAppId: string | null,
    patch: AutoHdrPreferencePatch,
  ) => Promise<AutoHdrPreferencesSnapshot>;
  publishRuntime?: (snapshot: AutoHdrPreferencesSnapshot) => void;
  activationState?: () => "off" | "waiting" | "ready";
  subscribeActivation?: (listener: () => void) => () => void;
  pollMs?: number;
  schedule?: (callback: () => void, delayMs: number) => TimerHandle;
  cancel?: (handle: TimerHandle) => void;
}

function normalizedAppId(value: unknown): string | null {
  if (typeof value !== "string" && typeof value !== "number") return null;
  const text = String(value);
  if (!/^[1-9]\d*$/.test(text)) return null;
  const numeric = Number(text);
  if (!Number.isSafeInteger(numeric) || numeric === 769 || numeric > 0xffffffff) return null;
  return String(numeric);
}

function runningAppId(router: unknown): string | null {
  const running = (router as { MainRunningApp?: Record<string, unknown> } | undefined)
    ?.MainRunningApp;
  return normalizedAppId(
    running?.appid ??
    running?.appID ??
    running?.AppID ??
    running?.unAppID,
  );
}

/**
 * Steam's per-game Performance profile is active only when its two store IDs
 * agree with the real running app. Any stale or partial state resolves global.
 */
export function resolveSteamAutoHdrScope(
  systemPerfStore: unknown,
  router: unknown,
): AutoHdrActiveScope {
  const store = systemPerfStore as {
    nCurrentGameID?: unknown;
    nActiveProfileGameID?: unknown;
  } | undefined;
  const current = normalizedAppId(store?.nCurrentGameID);
  const active = normalizedAppId(store?.nActiveProfileGameID);
  const running = runningAppId(router);
  if (current && current === active && current === running) {
    return { scope: "game", appId: current };
  }
  return { scope: "global", appId: null };
}

function scopeKey(scope: AutoHdrActiveScope): string {
  return `${scope.scope}:${scope.appId ?? ""}`;
}

const INITIAL_SNAPSHOT: AutoHdrCoordinatorSnapshot = {
  initialized: false,
  error: "",
};

export class AutoHdrPreferenceCoordinator {
  private readonly resolveScope: () => AutoHdrActiveScope;
  private readonly readRequest: AutoHdrPreferenceCoordinatorOptions["read"];
  private readonly reconcileRequest: AutoHdrPreferenceCoordinatorOptions["reconcile"];
  private readonly updateRequest: AutoHdrPreferenceCoordinatorOptions["update"];
  private readonly publishRuntime: (snapshot: AutoHdrPreferencesSnapshot) => void;
  private readonly activationState: () => "off" | "waiting" | "ready";
  private readonly subscribeActivation: (listener: () => void) => () => void;
  private readonly pollMs: number;
  private readonly schedule: (callback: () => void, delayMs: number) => TimerHandle;
  private readonly cancel: (handle: TimerHandle) => void;
  private readonly listeners = new Set<Listener>();
  private snapshot = INITIAL_SNAPSHOT;
  private chain = Promise.resolve<unknown>(undefined);
  private timer: TimerHandle | undefined;
  private running = false;
  private generation = 0;
  private observedScopeKey = "";
  private observedActivationState: "off" | "waiting" | "ready" = "waiting";
  private activationUnsubscribe: (() => void) | undefined;

  constructor(options: AutoHdrPreferenceCoordinatorOptions) {
    this.resolveScope = options.resolveScope;
    this.readRequest = options.read;
    this.reconcileRequest = options.reconcile;
    this.updateRequest = options.update;
    this.publishRuntime = options.publishRuntime ?? (() => {});
    this.activationState = options.activationState ?? (() => "ready");
    this.subscribeActivation = options.subscribeActivation ?? (() => () => {});
    this.pollMs = options.pollMs ?? AUTO_HDR_SCOPE_POLL_MS;
    this.schedule = options.schedule ?? ((callback, delayMs) =>
      globalThis.setTimeout(callback, delayMs));
    this.cancel = options.cancel ?? ((handle) => globalThis.clearTimeout(handle));
  }

  getSnapshot = (): AutoHdrCoordinatorSnapshot => this.snapshot;

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  start = (): void => {
    if (this.running) return;
    this.running = true;
    this.generation += 1;
    this.observedScopeKey = scopeKey(this.resolveScope());
    this.observedActivationState = this.activationState();
    if (this.observedActivationState === "ready") void this.reconcile();
    if (this.observedActivationState === "off") void this.load();
    this.activationUnsubscribe = this.subscribeActivation(this.inspectState);
    this.schedulePoll(this.generation);
  };

  stop = (): void => {
    if (!this.running) return;
    this.running = false;
    this.generation += 1;
    this.activationUnsubscribe?.();
    this.activationUnsubscribe = undefined;
    if (this.timer !== undefined) {
      this.cancel(this.timer);
      this.timer = undefined;
    }
  };

  reconcile = (): Promise<AutoHdrCoordinatorSnapshot> =>
    this.enqueue(async () => {
      const active = this.resolveScope();
      const requestedKey = scopeKey(active);
      const result = await this.reconcileRequest(active.scope, active.appId);
      return this.acceptOrRefresh(result, requestedKey);
    });

  load = (): Promise<AutoHdrCoordinatorSnapshot> =>
    this.enqueue(async () => {
      const active = this.resolveScope();
      const requestedKey = scopeKey(active);
      const result = await this.readRequest(active.scope, active.appId);
      return this.acceptOrRefresh(result, requestedKey);
    });

  updatePreference = (
    targetScope: AutoHdrScope,
    targetAppId: string | null,
    patch: AutoHdrPreferencePatch,
  ): Promise<AutoHdrCoordinatorSnapshot> =>
    this.enqueue(async () => {
      const active = this.resolveScope();
      const requestedKey = scopeKey(active);
      const result = await this.updateRequest(
        targetScope,
        targetAppId,
        active.scope,
        active.appId,
        patch,
      );
      return this.acceptOrRefresh(result, requestedKey);
    });

  private enqueue(
    operation: () => Promise<AutoHdrCoordinatorSnapshot>,
  ): Promise<AutoHdrCoordinatorSnapshot> {
    const request = this.chain
      .catch(() => {})
      .then(operation)
      .catch((error): AutoHdrCoordinatorSnapshot => {
        const next = {
          ...this.snapshot,
          initialized: true,
          error: String(error),
        };
        this.publish(next);
        return next;
      });
    this.chain = request;
    return request;
  }

  private acceptOrRefresh(
    result: AutoHdrPreferencesSnapshot,
    requestedKey: string,
  ): AutoHdrCoordinatorSnapshot {
    const current = this.resolveScope();
    const currentKey = scopeKey(current);
    if (currentKey !== requestedKey) {
      if (!this.running) return this.snapshot;
      this.observedScopeKey = currentKey;
      const activation = this.activationState();
      if (activation === "ready") void this.reconcile();
      if (activation === "off") void this.load();
      return this.snapshot;
    }
    const resultKey = scopeKey({ scope: result.scope, appId: result.appId });
    if (resultKey !== requestedKey) {
      throw new Error("AutoHDR response scope did not match the active Steam preference scope");
    }
    const next = { initialized: true, preferences: result, error: "" };
    this.publishRuntime(result);
    this.publish(next);
    return next;
  }

  private publish(snapshot: AutoHdrCoordinatorSnapshot): void {
    this.snapshot = snapshot;
    for (const listener of this.listeners) listener(snapshot);
  }

  private schedulePoll(generation: number): void {
    if (!this.running || this.timer !== undefined) return;
    this.timer = this.schedule(() => {
      this.timer = undefined;
      if (!this.running || generation !== this.generation) return;
      this.inspectState();
      this.schedulePoll(generation);
    }, this.pollMs);
  }

  private inspectState = (): void => {
    if (!this.running) return;
    const nextKey = scopeKey(this.resolveScope());
    const nextActivation = this.activationState();
    const scopeChanged = nextKey !== this.observedScopeKey;
    const activationChanged = nextActivation !== this.observedActivationState;
    if (scopeChanged) this.observedScopeKey = nextKey;
    if (activationChanged) this.observedActivationState = nextActivation;
    if (scopeChanged || activationChanged) {
      if (nextActivation === "ready") void this.reconcile();
      if (nextActivation === "off") void this.load();
    }
  };
}
