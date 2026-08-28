export function clone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function update<T>(obj: T, path: (string | number)[], value: any): T {
  const next = clone(obj);
  let cursor: any = next;
  for (let i = 0; i < path.length - 1; i += 1) cursor = cursor[path[i]];
  cursor[path[path.length - 1]] = value;
  return next;
}

export function titleCase(value: any): string {
  const text = String(value || "");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
