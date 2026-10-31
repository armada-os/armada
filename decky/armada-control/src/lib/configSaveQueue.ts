let tail: Promise<unknown> = Promise.resolve();
const pending = new Map<object, () => void>();
const inFlight = new Set<Promise<unknown>>();

export function trackConfigSave<T>(request: Promise<T>): Promise<T> {
  inFlight.add(request);
  void request.then(() => inFlight.delete(request), () => inFlight.delete(request));
  return request;
}

export function queueConfigSave<T>(write: () => Promise<T>): Promise<T> {
  const request = tail.then(write);
  tail = request.catch(() => {});
  return trackConfigSave(request);
}

export function registerPendingConfigSave(owner: object, flush: (() => void) | null): void {
  if (flush) pending.set(owner, flush);
  else pending.delete(owner);
}

// Reopening the plugin must see edits from its previous instance.
export async function waitForPendingSaves(): Promise<void> {
  for (;;) {
    for (const flush of [...pending.values()]) flush();
    const writes = [...inFlight];
    await Promise.allSettled(writes);
    if (!pending.size && !inFlight.size) return;
  }
}
