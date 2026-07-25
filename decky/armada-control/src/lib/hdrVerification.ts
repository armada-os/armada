import type { HdrRuntimeState } from "../types";

export const HDR_BRIGHTNESS_READBACK_EPSILON = 0.002;
export const HDR_BRIGHTNESS_NITS_EPSILON = 0.1;

type BrightnessReadyRuntime = HdrRuntimeState & {
  available: true;
  supportsHdr: true;
  enabled: true;
  outputFeedback: true;
  sdrContentBrightnessNits: number;
};

export function brightnessRuntimeReady(
  runtime: HdrRuntimeState | undefined,
): runtime is BrightnessReadyRuntime {
  return runtime?.available === true &&
    runtime.supportsHdr === true &&
    runtime.enabled === true &&
    runtime.outputFeedback === true &&
    runtime.sdrContentBrightnessNits !== null;
}

/**
 * A Steam setting readback alone is not proof that the compositor changed.
 * Treat an HDR request as complete only when Steam and Gamescope agree and
 * Gamescope reports output feedback in the requested state.
 */
export function hdrRequestConverged(
  requested: boolean,
  steamEnabled: boolean,
  runtime: HdrRuntimeState | undefined,
): boolean {
  return steamEnabled === requested &&
    runtime?.available === true &&
    runtime.supportsHdr === true &&
    runtime.enabled === requested &&
    runtime.outputFeedback === requested;
}

/** Show paper-white controls only while HDR is verified active end to end. */
export function shouldShowHdrBrightnessControl(
  steamEnabled: boolean,
  runtime: HdrRuntimeState | undefined,
): boolean {
  return hdrRequestConverged(true, steamEnabled, runtime);
}

/**
 * Steam keeps the SDR-on-HDR paper-white preference writable while HDR is
 * disabled for persistence, even though the UI hides its slider. In that state
 * the compositor atom may retain the preference, but the pixel pipeline must
 * remain SDR, so verify the saved value and real off output state instead of
 * requiring active-HDR nits feedback.
 */
export function brightnessRequestStoredWhileHdrOff(
  requested: number,
  readback: number | undefined,
  steamEnabled: boolean,
  runtime: HdrRuntimeState | undefined,
): boolean {
  return readback !== undefined &&
    Math.abs(readback - requested) <= HDR_BRIGHTNESS_READBACK_EPSILON &&
    hdrRequestConverged(false, steamEnabled, runtime);
}

export interface BrightnessConvergenceInput {
  requested: number;
  expectedNits: number;
  readback: number | undefined;
  beforeReadback: number | undefined;
  beforeRuntime: HdrRuntimeState | undefined;
  runtime: HdrRuntimeState | undefined;
}

/**
 * Verify both Steam's normalized setting and Gamescope's real nits atom. A
 * no-op request may retain the same atom; a changed request must move it.
 */
export function brightnessRequestConverged({
  requested,
  expectedNits,
  readback,
  beforeReadback,
  beforeRuntime,
  runtime,
}: BrightnessConvergenceInput): boolean {
  if (
    readback === undefined ||
    Math.abs(readback - requested) > HDR_BRIGHTNESS_READBACK_EPSILON ||
    !brightnessRuntimeReady(runtime) ||
    Math.abs(runtime.sdrContentBrightnessNits - expectedNits) > HDR_BRIGHTNESS_NITS_EPSILON
  ) {
    return false;
  }

  const requestedChange = beforeReadback === undefined ||
    Math.abs(beforeReadback - requested) > HDR_BRIGHTNESS_READBACK_EPSILON;
  if (!requestedChange) return true;

  const beforeNits = beforeRuntime?.sdrContentBrightnessNits;
  return beforeNits !== null &&
    beforeNits !== undefined &&
    Math.abs(runtime.sdrContentBrightnessNits - beforeNits) > HDR_BRIGHTNESS_NITS_EPSILON;
}
