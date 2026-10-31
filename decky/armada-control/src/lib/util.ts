export function clone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function titleCase(value: any): string {
  const text = String(value || "");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
