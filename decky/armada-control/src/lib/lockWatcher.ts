import { setCompanionLocked } from "../backend";

// Steam's lock screen never reaches gamescope; mirror it so the bottom screen locks too.
export function registerLockWatcher(): () => void {
  let sent: boolean | undefined;
  let busy = false;
  const timer = window.setInterval(() => {
    const store = window.securitystore;
    if (busy || !store?.IsLockScreenActive) return;
    const locked = !!store.IsLockScreenActive();
    if (locked === sent) return;
    busy = true;
    setCompanionLocked(locked)
      .then(() => { sent = locked; })
      .catch(() => {})
      .finally(() => { busy = false; });
  }, 250);
  return () => window.clearInterval(timer);
}
