import type { Config, HdrRuntimeState } from "../types";

export function hasHdrControlCapability(
  config: Config | undefined,
  runtime: HdrRuntimeState | undefined,
): boolean {
  return config?.hdrCapable === true ||
    (runtime?.available === true && runtime.supportsHdr === true);
}
