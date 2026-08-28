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
    .sort((a, b) => a.temp - b.temp);
}

export function formatCurve(points: CurvePoint[]): string {
  return [...points]
    .sort((a, b) => a.temp - b.temp)
    .map((point) => `${Math.round(point.temp)}:${Math.round(point.pwm)}`)
    .join(",");
}

export function slugifyCurveName(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 32);
}
