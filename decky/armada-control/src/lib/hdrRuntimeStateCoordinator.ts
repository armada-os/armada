import type { HdrRuntimeState } from "../types";

export const HDR_RUNTIME_FALLBACK_MS = 5000;

export interface HdrRuntimeSnapshot {
  initialized: boolean;
  runtime?: HdrRuntimeState;
  error: string;
}

type HdrRuntimeListener = (snapshot: HdrRuntimeSnapshot) => void;
type TimerHandle = ReturnType<typeof globalThis.setTimeout>;

export interface HdrRuntimeStateCoordinatorOptions {
  read: () => Promise<HdrRuntimeState>;
  fallbackMs?: number;
  schedule?: (callback: () => void, delayMs: number) => TimerHandle;
  cancel?: (handle: TimerHandle) => void;
}

const INITIAL_SNAPSHOT: HdrRuntimeSnapshot = {
  initialized: false,
  error: "",
};

function runtimeStatesEqual(
  left: HdrRuntimeState | undefined,
  right: HdrRuntimeState | undefined,
): boolean {
  if (left === right) return true;
  if (!left || !right) return false;
  return (
    left.available === right.available &&
    left.display === right.display &&
    left.supportsHdr === right.supportsHdr &&
    left.enabled === right.enabled &&
    left.outputFeedback === right.outputFeedback &&
    left.sdrContentBrightnessNits === right.sdrContentBrightnessNits &&
    left.reason === right.reason
  );
}

function snapshotsEqual(left: HdrRuntimeSnapshot, right: HdrRuntimeSnapshot): boolean {
  return (
    left.initialized === right.initialized &&
    left.error === right.error &&
    runtimeStatesEqual(left.runtime, right.runtime)
  );
}

/**
 * Owns the comparatively expensive Gamescope readback for every mounted HDR
 * control. The first subscriber reads immediately, all subscribers share that
 * request and its stable snapshot, and the last unsubscribe stops all timers.
 */
export class HdrRuntimeStateCoordinator {
  private readonly read: () => Promise<HdrRuntimeState>;
  private readonly fallbackMs: number;
  private readonly schedule: (callback: () => void, delayMs: number) => TimerHandle;
  private readonly cancel: (handle: TimerHandle) => void;
  private readonly listeners = new Set<HdrRuntimeListener>();
  private snapshot: HdrRuntimeSnapshot = INITIAL_SNAPSHOT;
  private generation = 0;
  private timer: TimerHandle | undefined;
  private inFlight: { generation: number; promise: Promise<HdrRuntimeSnapshot> } | undefined;

  constructor(options: HdrRuntimeStateCoordinatorOptions) {
    this.read = options.read;
    this.fallbackMs = options.fallbackMs ?? HDR_RUNTIME_FALLBACK_MS;
    this.schedule = options.schedule ?? ((callback, delayMs) =>
      globalThis.setTimeout(callback, delayMs));
    this.cancel = options.cancel ?? ((handle) => globalThis.clearTimeout(handle));
  }

  getSnapshot = (): HdrRuntimeSnapshot => this.snapshot;

  subscribe = (listener: HdrRuntimeListener): (() => void) => {
    // Give every subscription its own identity so even repeated registration
    // of the same callback remains correctly reference-counted.
    const subscription = (snapshot: HdrRuntimeSnapshot) => listener(snapshot);
    this.listeners.add(subscription);
    if (this.listeners.size === 1) {
      this.generation += 1;
      const generation = this.generation;
      void this.refresh();
      this.scheduleFallback(generation);
    }

    let subscribed = true;
    return () => {
      if (!subscribed) return;
      subscribed = false;
      this.listeners.delete(subscription);
      if (this.listeners.size !== 0) return;

      this.generation += 1;
      if (this.timer !== undefined) {
        this.cancel(this.timer);
        this.timer = undefined;
      }
    };
  };

  refresh = (): Promise<HdrRuntimeSnapshot> => {
    if (this.listeners.size === 0) return Promise.resolve(this.snapshot);

    const generation = this.generation;
    if (this.inFlight?.generation === generation) return this.inFlight.promise;

    const promise = this.read()
      .then((runtime): HdrRuntimeSnapshot => ({ initialized: true, runtime, error: "" }))
      .catch((error): HdrRuntimeSnapshot => ({
        initialized: true,
        runtime: undefined,
        error: String(error),
      }))
      .then((next) => {
        if (generation !== this.generation || this.listeners.size === 0) {
          return this.snapshot;
        }
        if (!snapshotsEqual(this.snapshot, next)) {
          this.snapshot = next;
          for (const listener of this.listeners) listener(this.snapshot);
        }
        return this.snapshot;
      })
      .finally(() => {
        if (this.inFlight?.generation === generation) this.inFlight = undefined;
      });

    this.inFlight = { generation, promise };
    return promise;
  };

  private scheduleFallback(generation: number): void {
    if (this.timer !== undefined || this.listeners.size === 0) return;
    this.timer = this.schedule(() => {
      this.timer = undefined;
      if (generation !== this.generation || this.listeners.size === 0) return;
      void this.refresh();
      this.scheduleFallback(generation);
    }, this.fallbackMs);
  }
}
