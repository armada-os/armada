import { toaster } from "@decky/api";
import { useEffect, useRef } from "react";

// Module-level so a closed panel's last change still lands before changes from a reopened one.
let queue: Promise<void> = Promise.resolve();

export function useDebouncedApply(
  read: () => Promise<number>,
  show: (value: number) => void,
  apply: (value: number) => Promise<number>,
  errorTitle: string,
  delay: number,
) {
  const timer = useRef<number | undefined>(undefined);
  const pending = useRef<(() => void) | undefined>(undefined);
  const request = useRef<number>(0);

  // Closing the panel flushes the last change instead of dropping it.
  useEffect(() => () => {
    window.clearTimeout(timer.current);
    pending.current?.();
    request.current += 1;
  }, []);

  return (value: number) => {
    show(value);
    window.clearTimeout(timer.current);
    const current = ++request.current;
    pending.current = () => {
      pending.current = undefined;
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
    timer.current = window.setTimeout(() => pending.current?.(), delay);
  };
}
