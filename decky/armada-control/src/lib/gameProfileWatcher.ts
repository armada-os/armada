import { Router } from "@decky/ui";
import { getGamePowerProfile } from "../backend";

// The running game's own power profile while it is in force, else "". Polled
// only while a game runs; Steam's dropdown reads it synchronously while rendering.
export function registerGameProfileWatcher() {
  let profile = "";
  let busy = false;
  const listeners = new Set<() => void>();
  const set = (next: string) => {
    if (next === profile) return;
    profile = next;
    for (const listener of listeners) listener();
  };
  const tick = () => {
    const running = (Router as any)?.MainRunningApp || window.Router?.MainRunningApp;
    if (!running?.appid) {
      set("");
      return;
    }
    if (busy) return;
    busy = true;
    getGamePowerProfile()
      .then((next) => set(next || ""))
      .catch(() => {})
      .finally(() => { busy = false; });
  };
  const timer = window.setInterval(tick, 1000);
  return {
    profile: () => profile,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },
    unregister: () => window.clearInterval(timer),
  };
}
