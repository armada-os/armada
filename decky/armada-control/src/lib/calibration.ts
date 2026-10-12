import type { CalibrationState } from "../types";

export function controlValue(state: CalibrationState | null, name: string): number {
  return Number(state?.controls?.[name]?.value || 0);
}

export function controlRange(state: CalibrationState | null, name: string): { min: number; max: number } {
  const control = state?.controls?.[name] || ({} as any);
  const min = Number(control.min);
  const max = Number(control.max);
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return { min: -32768, max: 32767 };
  return { min, max };
}

export function normalizedValue(state: CalibrationState | null, name: string): number {
  const { min, max } = controlRange(state, name);
  const value = controlValue(state, name);
  const side = value < 0 ? Math.abs(min) : max;
  if (!side) return 0;
  return Math.max(-1, Math.min(1, value / side));
}

export function triggerPercent(state: CalibrationState | null, name: string): number {
  const { min, max } = controlRange(state, name);
  const value = controlValue(state, name);
  if (max === min) return 0;
  return Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
}
