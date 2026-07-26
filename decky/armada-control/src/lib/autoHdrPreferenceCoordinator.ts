import { Router } from "@decky/ui";
import {
  getAutoHdrPreferences,
  reconcileAutoHdr,
  updateAutoHdrPreferences,
} from "../backend";
import {
  AutoHdrPreferenceCoordinator,
  resolveSteamAutoHdrScope,
} from "./autoHdrPreferenceCoordinatorCore";
import type { AutoHdrActiveScope } from "./autoHdrPreferenceCoordinatorCore";
import { hdrRuntimeState } from "./hdrRuntimeState";

export {
  AutoHdrPreferenceCoordinator,
  resolveAutoHdrPreference,
  resolveSteamAutoHdrScope,
} from "./autoHdrPreferenceCoordinatorCore";
export type {
  AutoHdrActiveScope,
  AutoHdrCoordinatorSnapshot,
  AutoHdrPreferenceCoordinatorOptions,
} from "./autoHdrPreferenceCoordinatorCore";

export function currentSteamAutoHdrScope(): AutoHdrActiveScope {
  try {
    const deckyRouter = Router as unknown as { MainRunningApp?: unknown };
    return resolveSteamAutoHdrScope(
      window.SystemPerfStore,
      deckyRouter?.MainRunningApp ? deckyRouter : window.Router,
    );
  } catch {
    return { scope: "global", appId: null };
  }
}

export const autoHdrPreferenceState = new AutoHdrPreferenceCoordinator({
  resolveScope: currentSteamAutoHdrScope,
  read: getAutoHdrPreferences,
  reconcile: reconcileAutoHdr,
  update: updateAutoHdrPreferences,
  publishRuntime: (snapshot) => hdrRuntimeState.publish(snapshot.runtime),
  subscribeActivation: (listener) => hdrRuntimeState.subscribe(listener),
  activationState: () => {
    let steamEnabled = false;
    try {
      const value = window.settingsStore?.GetClientSetting?.("gamescope_hdr_enabled")?.[0];
      steamEnabled = value === true || value === 1 || value === "1" || value === "true";
    } catch {
      return "waiting";
    }
    if (!steamEnabled) return "off";
    const runtime = hdrRuntimeState.getSnapshot().runtime;
    return runtime?.available &&
      runtime.supportsHdr &&
      runtime.enabled &&
      runtime.outputFeedback
      ? "ready"
      : "waiting";
  },
});
