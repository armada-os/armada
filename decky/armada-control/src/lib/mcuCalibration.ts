export type StickOverlay = {
  dots: boolean[];
  pendingIndex: number | null;
};

const COMPASS_INDEX: Record<string, number> = {
  up: 0,
  "up-right": 1,
  right: 2,
  "down-right": 3,
  down: 4,
  "down-left": 5,
  left: 6,
  "up-left": 7,
};

export function centerOverlay(
  covered: string[] | undefined,
  pending: string | null | undefined,
): StickOverlay {
  const dots = Array<boolean>(8).fill(false);
  for (const name of covered || []) {
    if (name in COMPASS_INDEX) dots[COMPASS_INDEX[name]] = true;
  }
  return { dots, pendingIndex: pending && pending in COMPASS_INDEX ? COMPASS_INDEX[pending] : null };
}

export function rangeProgress(p: {
  turns?: number; turnGoal?: number; coveredHeadings?: number; headingGoal?: number;
  coveredSectors?: number; sectorGoal?: number;
}): number {
  return Math.max(0, Math.min(1, (p.turns || 0) / (p.turnGoal || 4),
    (p.coveredHeadings || 0) / (p.headingGoal || 8),
    (p.coveredSectors || 0) / (p.sectorGoal || 72)));
}
