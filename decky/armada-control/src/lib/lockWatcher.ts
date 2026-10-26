import { setCompanionLocked } from "../backend";

const RESUME_LOCK_GRACE_MS = 5000;

// Steam's lock screen never reaches gamescope; mirror it so the bottom screen locks too.
export function registerLockWatcher(): () => void {
  let sent: boolean | undefined;
  let busy = false;
  let lockPending = false;
  let resumedAt: number | undefined;
  let timer: number | undefined;
  let stopped = false;
  const tick = () => {
    const store = window.securitystore;
    if (busy || !store?.IsLockScreenActive) return;
    const active = !!store.IsLockScreenActive();
    const suspending = !!window.SuspendResumeStore?.suspending;
    // Lock before sleeping: on wake the bottom screen lights before Steam shows its lock screen.
    if (suspending && store.m_Settings?.bLockOnWake && store.m_Settings?.strPIN) {
      lockPending = true;
      resumedAt = undefined;
    }
    if (active) lockPending = false;
    if (lockPending && !suspending) {
      resumedAt ??= Date.now();
      if (Date.now() - resumedAt > RESUME_LOCK_GRACE_MS) lockPending = false;
    }
    const locked = active || lockPending;
    if (locked === sent) return;
    busy = true;
    setCompanionLocked(locked)
      .then(() => { sent = locked; })
      .catch(() => {})
      .finally(() => { busy = false; });
  };
  // gamescope keeps the bottom screen locked until the first report; an early
  // "unlocked" would beat the lock screen Steam shows on start.
  Promise.resolve((window as any).App?.WaitForServicesInitialized?.())
    .catch(() => {})
    .then(() => {
      if (!stopped) timer = window.setInterval(tick, 250);
    });
  return () => {
    stopped = true;
    window.clearInterval(timer);
  };
}
