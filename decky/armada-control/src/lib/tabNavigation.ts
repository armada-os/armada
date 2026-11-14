export function adjacentTab<T extends { id: string }>(tabs: readonly T[], active: string, direction: number): T {
  const index = Math.max(0, tabs.findIndex((tab) => tab.id === active));
  return tabs[(index + direction + tabs.length) % tabs.length];
}
