export const SYSTEM_PERF_STORE_BOOTSTRAP_POLL_MS = 50;
export const SYSTEM_PERF_STORE_BOOTSTRAP_TIMEOUT_MS = 2000;

export function isSystemPerfStoreReady(value: unknown): boolean {
  if (value === null || (typeof value !== "object" && typeof value !== "function")) {
    return false;
  }
  return typeof (value as { SetHDRSDRContentBrightness?: unknown })
    .SetHDRSDRContentBrightness === "function";
}

/** Fail closed on invalid time input and stop once the bounded window expires. */
export function shouldKeepSystemPerfStoreBootstrap(
  store: unknown,
  elapsedMs: number,
  timeoutMs = SYSTEM_PERF_STORE_BOOTSTRAP_TIMEOUT_MS,
): boolean {
  return Number.isFinite(elapsedMs) && elapsedMs >= 0 &&
    Number.isFinite(timeoutMs) && timeoutMs > 0 &&
    elapsedMs < timeoutMs && !isSystemPerfStoreReady(store);
}
