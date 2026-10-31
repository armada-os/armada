export interface MotionRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface TabMotionSnapshot {
  surface: MotionRect;
  corners: {
    borderTopLeftRadius: string;
    borderTopRightRadius: string;
    borderBottomRightRadius: string;
    borderBottomLeftRadius: string;
  };
  icon: MotionRect;
  label: MotionRect;
  labelWidth: number;
  labelOpacity: number;
  opacity: number;
  background: string;
  color: string;
}

export function localRect(rect: MotionRect, origin: MotionRect, scale: { x: number; y: number }): MotionRect {
  return {
    left: (rect.left - origin.left) / scale.x,
    top: (rect.top - origin.top) / scale.y,
    width: rect.width / scale.x,
    height: rect.height / scale.y,
  };
}

export function atBoundary(snapshot: TabMotionSnapshot, edge: MotionRect): TabMotionSnapshot {
  const centered = (rect: MotionRect) => ({
    ...rect,
    left: edge.left + (edge.width - rect.width) / 2,
    top: edge.top + (edge.height - rect.height) / 2,
  });
  const icon = centered(snapshot.icon);
  return {
    ...snapshot,
    surface: centered({ ...snapshot.surface, width: snapshot.surface.height }),
    icon,
    label: { ...centered(snapshot.label), left: icon.left + icon.width, width: 0 },
    labelWidth: 0,
    labelOpacity: 0,
    opacity: 0,
    background: "transparent",
  };
}

export function tabMotionFrames(from: TabMotionSnapshot, to: TabMotionSnapshot, scale: { x: number; y: number }, selected: boolean, base = to) {
  const translate = (start: MotionRect, end: MotionRect) =>
    `translate(${(start.left - end.left) / scale.x}px, ${(start.top - end.top) / scale.y}px)`;
  const shape = (snapshot: TabMotionSnapshot) => ({
    width: `${snapshot.surface.width / scale.x}px`,
    height: `${snapshot.surface.height / scale.y}px`,
    ...snapshot.corners,
    backgroundColor: snapshot.background,
    opacity: snapshot.opacity,
  });
  const reveal = to.label.width ? Math.min(1, from.labelWidth / to.label.width) : 0;
  return {
    surface: [
      { ...shape(from), transform: translate(from.surface, base.surface) },
      { ...shape(to), transform: translate(to.surface, base.surface) },
    ],
    icon: [
      { transform: translate(from.icon, base.icon), opacity: from.opacity, color: from.color },
      { transform: translate(to.icon, base.icon), opacity: to.opacity, color: to.color },
    ],
    label: [
      {
        transform: translate(from.label, base.label), opacity: from.labelOpacity, color: from.color,
        ...(selected ? { clipPath: `inset(0 ${100 * (1 - reveal)}% 0 0)` } : { width: `${from.labelWidth / scale.x}px` }),
      },
      {
        transform: translate(to.label, base.label), opacity: to.labelOpacity, color: to.color,
        ...(selected ? { clipPath: "inset(0 0% 0 0)" } : { width: "0px" }),
      },
    ],
  };
}

export function cssDuration(value: string): number {
  const duration = Number.parseFloat(value);
  return Number.isFinite(duration) ? Math.max(0, duration * (value.trim().endsWith("ms") ? 1 : 1000)) : 0;
}
