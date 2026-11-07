export interface CurvePoint {
  temp: number;
  pwm: number;
}

export const CURVE_TEMP_MIN = 0;
export const CURVE_TEMP_MAX = 120;
export const CURVE_PWM_MIN = 0;
export const CURVE_PWM_MAX = 255;

export const DEFAULT_POINT: CurvePoint = { temp: 60, pwm: 128 };

export function pwmToPercent(pwm: number): number {
  return Math.round((Math.min(CURVE_PWM_MAX, Math.max(CURVE_PWM_MIN, pwm)) / CURVE_PWM_MAX) * 100);
}

export function percentToPwm(percent: number): number {
  return Math.round((Math.min(100, Math.max(0, percent)) / 100) * CURVE_PWM_MAX);
}

export function compareCurvePoints(a: CurvePoint, b: CurvePoint): number {
  return a.temp - b.temp || a.pwm - b.pwm;
}

export function parseCurve(text: string | undefined): CurvePoint[] {
  if (!text) return [];
  return text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const [tempPart, pwmPart] = item.split(":");
      return { temp: parseInt(tempPart, 10), pwm: parseInt(pwmPart, 10) };
    })
    .filter((point) => Number.isFinite(point.temp) && Number.isFinite(point.pwm))
    .sort(compareCurvePoints);
}

export function formatCurve(points: CurvePoint[]): string {
  return [...points]
    .sort(compareCurvePoints)
    .map((point) => `${Math.round(point.temp)}:${Math.round(point.pwm)}`)
    .join(",");
}

export function slugifyCurveName(value: string): string {
  const name = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 32);
  return name && !/^[a-z]/.test(name) ? `curve_${name}`.slice(0, 32) : name;
}

export function restoreFanStopPoints(points: CurvePoint[]): CurvePoint[] {
  const speed = points.find((point) => point.pwm > 0)?.pwm || DEFAULT_POINT.pwm;
  return points.map((point) => ({ ...point, pwm: point.pwm || speed }));
}

export function buildFanStopPoints(temp: number, points: CurvePoint[]): CurvePoint[] {
  const stop = Math.max(CURVE_TEMP_MIN, Math.min(CURVE_TEMP_MAX - 1, Math.round(temp)));
  const below = points.filter((point) => point.temp < stop).map((point) => ({ ...point, pwm: 0 }));
  const above = points.filter((point) => point.temp > stop);
  if (!above.length) {
    above.push({ temp: Math.min(stop + 20, CURVE_TEMP_MAX), pwm: points[points.length - 1]?.pwm || DEFAULT_POINT.pwm });
  }
  return [...below, { temp: stop, pwm: 0 }, ...above];
}
