// Keep writes ordered even when a panel closes and another instance opens.
const pendingSaves = new Set<() => Promise<void>>();

export async function flushSettingsSaves(): Promise<void> {
  // A reopened panel must read after the previous panel's last edit, including
  // edits queued behind an in-flight request.
  while (pendingSaves.size) {
    await Promise.all([...pendingSaves].map((flush) => flush()));
  }
}

export function createSettingsQueue() {
  let tail: Promise<unknown> = Promise.resolve();
  return {
    run<T>(operation: () => Promise<T>): Promise<T> {
      const result = tail.then(operation);
      tail = result.catch(() => {});
      return result;
    },
  };
}

export function createDebouncedSave<T, R>(options: {
  snapshot: () => string;
  save: (value: T) => Promise<R>;
  onSaved: (result: R, submitted: string) => void;
  onError: (error: unknown, submitted: string) => void;
  delay: number;
}) {
  let pending: string | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let inFlight: Promise<void> | undefined;

  function clearTimer() {
    if (timer !== undefined) clearTimeout(timer);
    timer = undefined;
  }

  function flush(): Promise<void> {
    clearTimer();
    if (inFlight) return inFlight.then(flush);
    if (!pending || pending === options.snapshot()) {
      pending = undefined;
      pendingSaves.delete(flush);
      return Promise.resolve();
    }
    const request = pending;
    pending = undefined;
    inFlight = (async () => {
      try {
        const result = await Promise.resolve().then(() => options.save(JSON.parse(request)));
        options.onSaved(result, request);
      } catch (error) {
        options.onError(error, request);
      } finally {
        inFlight = undefined;
        if (!pending) pendingSaves.delete(flush);
      }
    })();
    return inFlight;
  }

  return {
    update(value: T) {
      // Retain a toggle back to the saved value: an older write may still
      // change the backend before this value gets its turn.
      pending = JSON.stringify(value);
      pendingSaves.add(flush);
      clearTimer();
      timer = setTimeout(() => { void flush(); }, options.delay);
    },
    flush,
  };
}
