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

const OPPOSITE_DIRECTIONS: Record<string, string> = {
  up: "down",
  down: "up",
  left: "right",
  right: "left",
  "up-left": "down-right",
  "up-right": "down-left",
  "down-left": "up-right",
  "down-right": "up-left",
};

function displayDirection(stick: "left" | "right", name: string): string | undefined {
  if (!(name in COMPASS_INDEX)) return undefined;
  return stick === "right" ? OPPOSITE_DIRECTIONS[name] : name;
}

export function centerOverlay(
  stick: "left" | "right",
  covered: string[] | undefined,
  pending: string | null | undefined,
): StickOverlay {
  const dots = Array<boolean>(8).fill(false);
  for (const name of covered || []) {
    const display = displayDirection(stick, name);
    if (display) dots[COMPASS_INDEX[display]] = true;
  }
  const pendingDisplay = pending ? displayDirection(stick, pending) : undefined;
  return { dots, pendingIndex: pendingDisplay ? COMPASS_INDEX[pendingDisplay] : null };
}
