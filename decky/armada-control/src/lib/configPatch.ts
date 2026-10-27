export type ConfigPatch = { path: string[]; value: unknown } | { path: string[]; remove: true };

const isRecord = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);

export function configChanges(before: unknown, after: unknown, path: string[] = []): ConfigPatch[] {
  if (JSON.stringify(before) === JSON.stringify(after)) return [];
  if (before === undefined && isRecord(after) && Object.keys(after).length) before = {};
  if (!isRecord(before) || !isRecord(after)) return [{ path, value: after }];
  return [...new Set([...Object.keys(before), ...Object.keys(after)])].flatMap((key) => {
    const nextPath = [...path, key];
    if (!Object.prototype.hasOwnProperty.call(after, key) || after[key] === undefined) return [{ path: nextPath, remove: true }];
    return configChanges(Object.prototype.hasOwnProperty.call(before, key) ? before[key] : undefined, after[key], nextPath);
  });
}
