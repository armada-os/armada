export function indexAtMost(list: number[], mhz: number): number {
  let index = 0;
  list.forEach((value, i) => {
    if (value <= mhz) index = i;
  });
  return index;
}

export const UNDERCLOCK_OFF = new Set(["", "none", "stock", "custom"]);

export function presetKhz(presets: Record<string, Record<string, string>> | undefined, level: string, key: string): number | undefined {
  const normalized = level.trim().toLowerCase();
  if (UNDERCLOCK_OFF.has(normalized)) return undefined;
  return Number(presets?.[normalized]?.[key]) || undefined;
}

export function derivedKhz(top: number, preset: number | undefined, ratio: number, presetClass: boolean): number {
  return preset ?? (presetClass ? top : Math.floor(top * ratio));
}

export function isOverclocked(mhz: number, stock: number): boolean {
  return stock > 0 && mhz > stock;
}

export function clusterRoles(policies: { id: number; khz: number[] }[]): string[] {
  const tops = policies.map((policy) => Math.max(...policy.khz));
  const roles = tops.map(() => "big");
  if (tops.length < 2) return roles;
  const highest = Math.max(...tops);
  const lowest = Math.min(...tops);
  if (tops.filter((top) => top === highest).length === 1) roles[tops.indexOf(highest)] = "prime";
  if (tops.length >= 3 && lowest < highest) roles[tops.indexOf(lowest)] = "little";
  const bigs = roles.flatMap((role, i) => (role === "big" ? [i] : [])).sort((a, b) => tops[a] - tops[b]);
  if (bigs.length >= 2) bigs.forEach((i, rank) => (roles[i] = `big${rank + 1}`));
  return roles;
}
