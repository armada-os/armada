import { getHdrRuntimeState } from "../backend";
import type { HdrRuntimeState } from "../types";
import {
  brightnessRequestStoredWhileHdrOff,
  brightnessRequestConverged,
  brightnessRuntimeReady,
  hdrRequestConverged,
} from "./hdrVerification";
import { hdrSdrBrightnessNormalizedToNits } from "./hdrBrightness";

const GLOBAL_RESOLUTION_KEY = "gamescope_game_resolution_global";
const HDR_ENABLED_KEY = "gamescope_hdr_enabled";
export const HDR_SDR_CONTENT_BRIGHTNESS_DEFAULT = 0.292;
const HDR_SDR_CONTENT_BRIGHTNESS_MIN = 0;
const HDR_SDR_CONTENT_BRIGHTNESS_MAX = 1;
const HDR_VERIFY_INTERVAL_MS = 100;
const HDR_VERIFY_TIMEOUT_MS = 2500;
const HDR_BRIGHTNESS_BASELINE_TIMEOUT_MS = 1500;

function getClientSetting(key: string): any {
  try {
    return window.settingsStore?.GetClientSetting?.(key);
  } catch (error) {
    return undefined;
  }
}

function getSystemPerfStore(): any {
  try {
    return window.SystemPerfStore;
  } catch (error) {
    return undefined;
  }
}

export function getGlobalResolution(): string {
  return getClientSetting(GLOBAL_RESOLUTION_KEY)?.[0] || "Default";
}

export async function setGlobalResolution(value: string): Promise<string> {
  const setting = getClientSetting(GLOBAL_RESOLUTION_KEY);
  const setter = setting?.[1];
  if (!setter) throw new Error("Steam settings are unavailable");
  await Promise.resolve(setter(value));
  return getGlobalResolution();
}

export function isHdrSettingAvailable(): boolean {
  return typeof getClientSetting(HDR_ENABLED_KEY)?.[1] === "function";
}

export function getHdrEnabled(): boolean {
  const value = getClientSetting(HDR_ENABLED_KEY)?.[0];
  return value === true || value === 1 || value === "1" || value === "true";
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function runtimeSummary(runtime: HdrRuntimeState | undefined): string {
  if (!runtime) return "Gamescope=unavailable";
  if (!runtime.available) return `Gamescope=unavailable (${runtime.reason || "no primary root"})`;
  return [
    `support=${Number(runtime.supportsHdr)}`,
    `enabled=${Number(runtime.enabled)}`,
    `feedback=${Number(runtime.outputFeedback)}`,
  ].join(", ");
}

export async function setHdrEnabled(value: boolean): Promise<boolean> {
  const setter = getClientSetting(HDR_ENABLED_KEY)?.[1];
  if (typeof setter !== "function") throw new Error("Steam HDR control is unavailable");
  await Promise.resolve(setter(value));

  const deadline = Date.now() + HDR_VERIFY_TIMEOUT_MS;
  let runtime: HdrRuntimeState | undefined;
  while (Date.now() <= deadline) {
    try {
      runtime = await getHdrRuntimeState();
    } catch {
      runtime = undefined;
    }
    if (hdrRequestConverged(value, getHdrEnabled(), runtime)) {
      return value;
    }
    await delay(HDR_VERIFY_INTERVAL_MS);
  }

  throw new Error(
    `HDR output did not reach ${value ? "on" : "off"}: ` +
    `Steam=${Number(getHdrEnabled())}, ${runtimeSummary(runtime)}`,
  );
}

export function getHdrSdrContentBrightness(): number | undefined {
  const value = getSystemPerfStore()?.msgSettingsGlobal?.sdr_to_hdr_brightness;
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    value < HDR_SDR_CONTENT_BRIGHTNESS_MIN ||
    value > HDR_SDR_CONTENT_BRIGHTNESS_MAX
  ) {
    return undefined;
  }
  return value;
}

export function isHdrSdrContentBrightnessAvailable(): boolean {
  const store = getSystemPerfStore();
  // This low-level API intentionally remains readable and writable while HDR
  // is off so Steam can persist the remembered paper-white preference. The UI
  // separately hides its slider until HDR is verified active end to end.
  return (
    typeof store?.SetHDRSDRContentBrightness === "function" &&
    getHdrSdrContentBrightness() !== undefined
  );
}

export async function setHdrSdrContentBrightness(value: number): Promise<number> {
  const store = getSystemPerfStore();
  if (
    typeof store?.SetHDRSDRContentBrightness !== "function" ||
    getHdrSdrContentBrightness() === undefined
  ) {
    throw new Error("Steam SDR-on-HDR brightness control is unavailable");
  }
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error("Invalid SDR-on-HDR brightness value");
  }

  const normalized = Math.min(
    HDR_SDR_CONTENT_BRIGHTNESS_MAX,
    Math.max(HDR_SDR_CONTENT_BRIGHTNESS_MIN, value),
  );
  // Preserve off-state writes for preference persistence. This does not make
  // the setting visible while HDR is off; presentation owns that policy.
  const hdrEnabledBefore = getHdrEnabled();
  const beforeNormalized = getHdrSdrContentBrightness();
  let beforeRuntime: HdrRuntimeState | undefined;
  const baselineDeadline = Date.now() + HDR_BRIGHTNESS_BASELINE_TIMEOUT_MS;
  while (Date.now() <= baselineDeadline) {
    try {
      beforeRuntime = await getHdrRuntimeState();
    } catch {
      beforeRuntime = undefined;
    }
    if (
      hdrEnabledBefore
        ? brightnessRuntimeReady(beforeRuntime)
        : hdrRequestConverged(false, getHdrEnabled(), beforeRuntime)
    ) break;
    await delay(HDR_VERIFY_INTERVAL_MS);
  }
  if (
    hdrEnabledBefore
      ? !brightnessRuntimeReady(beforeRuntime)
      : !hdrRequestConverged(false, getHdrEnabled(), beforeRuntime)
  ) {
    throw new Error(
      `Cannot verify SDR-on-HDR brightness before changing it: ${runtimeSummary(beforeRuntime)}`,
    );
  }
  store.SetHDRSDRContentBrightness(normalized);

  const deadline = Date.now() + HDR_VERIFY_TIMEOUT_MS;
  let runtime: HdrRuntimeState | undefined;
  while (Date.now() <= deadline) {
    const readback = getHdrSdrContentBrightness();
    try {
      runtime = await getHdrRuntimeState();
    } catch {
      runtime = undefined;
    }
    const converged = hdrEnabledBefore
      ? brightnessRequestConverged({
        requested: normalized,
        expectedNits: hdrSdrBrightnessNormalizedToNits(normalized),
        readback,
        beforeReadback: beforeNormalized,
        beforeRuntime,
        runtime,
      })
      : brightnessRequestStoredWhileHdrOff(
        normalized,
        readback,
        getHdrEnabled(),
        runtime,
      );
    if (converged) {
      return normalized;
    }
    await delay(HDR_VERIFY_INTERVAL_MS);
  }

  throw new Error(
    `SDR-on-HDR brightness did not reach ` +
    `${hdrSdrBrightnessNormalizedToNits(normalized).toFixed(0)} nits: ` +
    `${runtimeSummary(runtime)}, nits=${runtime?.sdrContentBrightnessNits ?? "unavailable"}`,
  );
}
