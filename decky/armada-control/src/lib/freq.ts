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

export function parseCpuList(list: string): number[] {
  return list.split(",").flatMap((part) => {
    const [start, end = start] = part.trim().split("-").map(Number);
    if (!part.trim() || !Number.isInteger(start) || !Number.isInteger(end) || end < start) return [];
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  });
}

// Roles come from the device topology cpulists when set; frequency order is
// only a fallback, since SM8650 reports its prime core below the top big cluster.
// BIG includes the prime cores, so PRIME wins where both match. Clusters a
// cpulist covers are never relabelled by the fallback.
export function clusterRoles(
  policies: { id: number; cpus?: string; khz: number[] }[],
  topology: { big?: string; prime?: string; little?: string } = {},
): string[] {
  const tops = policies.map((policy) => Math.max(...policy.khz));
  const roles = tops.map(() => "big");
  if (tops.length < 2) return roles;
  const highest = Math.max(...tops);
  const lowest = Math.min(...tops);
  const within = (list: string | undefined) => {
    const set = new Set(parseCpuList(list ?? ""));
    return policies.map((policy) => {
      const cpus = parseCpuList(policy.cpus ?? String(policy.id));
      return set.size > 0 && cpus.length > 0 && cpus.every((cpu) => set.has(cpu));
    });
  };
  const prime = within(topology.prime);
  const big = within(topology.big);
  const little = within(topology.little);
  const known = policies.map((_, i) => prime[i] || big[i] || little[i]);
  policies.forEach((_, i) => {
    if (prime[i]) roles[i] = "prime";
    else if (little[i] && !big[i]) roles[i] = "little";
  });
  const top = tops.indexOf(highest);
  if (!prime.some(Boolean) && !known[top] && tops.filter((t) => t === highest).length === 1) roles[top] = "prime";
  const bottom = tops.indexOf(lowest);
  if (!little.some(Boolean) && !known[bottom] && tops.length >= 3 && lowest < highest && roles[bottom] === "big") roles[bottom] = "little";
  const bigs = roles.flatMap((role, i) => (role === "big" ? [i] : [])).sort((a, b) => tops[a] - tops[b]);
  if (bigs.length >= 2) bigs.forEach((i, rank) => (roles[i] = `big${rank + 1}`));
  return roles;
}
