import type { AutoHdrMode, HdrRuntimeState } from "../types";

export const AUTO_HDR_MODE_HIGH_QUALITY: AutoHdrMode = 2;

export function autoHdrModeSupported(
  mode: AutoHdrMode,
  runtime: HdrRuntimeState | undefined,
): boolean {
  return runtime?.autoHdrSupported === true &&
    runtime.autoHdrModeProtocol === true &&
    (runtime.autoHdrSupportedModes & mode) === mode;
}

export function shouldShowAutoHdrControl(
  steamHdrEnabled: boolean,
  runtime: HdrRuntimeState | undefined,
): boolean {
  return steamHdrEnabled === true &&
    runtime?.available === true &&
    runtime.displayIsExternal === false &&
    runtime.supportsHdr === true &&
    runtime.enabled === true &&
    runtime.outputFeedback === true &&
    runtime.autoHdrSupported === true &&
    runtime.autoHdrModeProtocol === true &&
    autoHdrModeSupported(AUTO_HDR_MODE_HIGH_QUALITY, runtime);
}

/** Keep an active QAM control reachable during transient output readback loss. */
export function shouldKeepAutoHdrControlVisible(
  steamHdrEnabled: boolean,
  runtime: HdrRuntimeState | undefined,
): boolean {
  return shouldShowAutoHdrControl(steamHdrEnabled, runtime) ||
    (steamHdrEnabled === true && runtime?.autoHdrEnabled === true);
}
