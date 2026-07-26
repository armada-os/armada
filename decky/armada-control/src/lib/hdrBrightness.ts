export const HDR_SDR_BRIGHTNESS_MIN_NITS = 80;
export const HDR_SDR_BRIGHTNESS_MAX_NITS = 500;
const HDR_SDR_BRIGHTNESS_RANGE_NITS =
  HDR_SDR_BRIGHTNESS_MAX_NITS - HDR_SDR_BRIGHTNESS_MIN_NITS;

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

/** Steam build 1784145295 maps its normalized setting linearly onto 80–500 nits. */
export function hdrSdrBrightnessNormalizedToNits(normalized: number): number {
  const safeNormalized = Number.isFinite(normalized) ? clamp(normalized, 0, 1) : 0;
  return HDR_SDR_BRIGHTNESS_MIN_NITS + safeNormalized * HDR_SDR_BRIGHTNESS_RANGE_NITS;
}

export function hdrSdrBrightnessNitsToNormalized(nits: number): number {
  const safeNits = Number.isFinite(nits)
    ? clamp(nits, HDR_SDR_BRIGHTNESS_MIN_NITS, HDR_SDR_BRIGHTNESS_MAX_NITS)
    : HDR_SDR_BRIGHTNESS_MIN_NITS;
  return (safeNits - HDR_SDR_BRIGHTNESS_MIN_NITS) / HDR_SDR_BRIGHTNESS_RANGE_NITS;
}
