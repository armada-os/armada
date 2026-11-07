import { toaster } from "@decky/api";
import { useEffect, useRef } from "react";

// Module-level so a closed panel's last change still lands before changes from a reopened one.
let queue: Promise<void> = Promise.resolve();
const pendingApplies = new Map<object, () => void>();

export async function waitForPendingApplies(): Promise<void> {
  for (;;) {
    for (const flush of [...pendingApplies.values()]) flush();
    const pending = queue;
    await pending;
    if (pending === queue && !pendingApplies.size) return;
  }
}

export function readAfterPendingApplies<T>(read: () => Promise<T>): Promise<T> {
  for (const flush of [...pendingApplies.values()]) flush();
  const result = queue.then(read);
  queue = result.then(() => {}, () => {});
  return result;
}

export function useDebouncedApply<T>(
  read: () => Promise<T>,
  show: (value: T) => void,
  apply: (value: T) => Promise<T>,
  errorTitle: string,
  delay: number,
) {
  const timer = useRef<number | undefined>(undefined);
  const pending = useRef<(() => void) | undefined>(undefined);
  const request = useRef<number>(0);
  const owner = useRef({});
  const flush = () => {
    window.clearTimeout(timer.current);
    timer.current = undefined;
    pendingApplies.delete(owner.current);
    const applyPending = pending.current;
    pending.current = undefined;
    applyPending?.();
  };

  // Closing the panel flushes the last change instead of dropping it.
  useEffect(() => () => {
    flush();
    request.current += 1;
  }, []);

  return (value: T) => {
    show(value);
    window.clearTimeout(timer.current);
    const current = ++request.current;
    pending.current = () => {
      queue = queue.then(async () => {
        try {
          const result = await apply(value);
          if (current === request.current) show(result);
        } catch (error) {
          if (current !== request.current) return;
          toaster.toast({ title: errorTitle, body: String(error) });
          await read().then((saved) => { if (current === request.current) show(saved); }, () => {});
        }
      });
    };
    pendingApplies.set(owner.current, flush);
    timer.current = window.setTimeout(flush, delay);
  };
}
