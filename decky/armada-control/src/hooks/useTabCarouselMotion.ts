import { useLayoutEffect, useRef } from "react";
import type { RefObject } from "react";
import { atBoundary, cssDuration, localRect, tabMotionFrames } from "../lib/tabCarouselMotion";
import type { TabMotionSnapshot } from "../lib/tabCarouselMotion";

export interface TabMotionView {
  shell: HTMLElement | null;
  surface: HTMLElement | null;
  icon: HTMLElement | null;
  label: HTMLElement | null;
}

export type TabMotionViews = Record<"previous" | "current" | "next" | "ghost", TabMotionView>;

export function useTabCarouselMotion(
  header: RefObject<HTMLElement | null>,
  views: RefObject<TabMotionViews>,
  leftEdge: RefObject<HTMLElement | null>,
  rightEdge: RefObject<HTMLElement | null>,
  active: string,
  labels: string,
) {
  const pending = useRef<{ target: string; direction: -1 | 1; snapshots: Map<string, TabMotionSnapshot> } | null>(null);
  const animations = useRef<Animation[]>([]);
  const generation = useRef(0);
  const lastLayout = useRef("");
  const stop = () => {
    generation.current++;
    animations.current.forEach((animation) => animation.cancel());
    animations.current = [];
    header.current?.removeAttribute("data-moving");
  };
  const coordinates = () => {
    const element = header.current!;
    const origin = element.getBoundingClientRect();
    const scale = { x: origin.width / element.offsetWidth || 1, y: origin.height / element.offsetHeight || 1 };
    return { rect: (node: HTMLElement) => localRect(node.getBoundingClientRect(), origin, scale), scale };
  };
  const layout = () => [header.current, ...Object.values(views.current).map((view) => view.shell)]
    .filter((node) => node && !node.classList.contains("armada-tab-ghost"))
    .map((node) => `${node!.offsetWidth}:${node!.offsetHeight}`).join("|");
  const read = (view: TabMotionView): TabMotionSnapshot | null => {
    if (!view.shell || !view.surface || !view.icon || !view.label || !header.current) return null;
    const window = header.current.ownerDocument.defaultView!;
    const { rect } = coordinates();
    const label = rect(view.label);
    const labelStyle = window.getComputedStyle(view.label);
    const hidden = Number.parseFloat(labelStyle.clipPath.match(/^inset\([^ ]+\s+([\d.]+)%/)?.[1] || "0") / 100;
    const moving = header.current.hasAttribute("data-moving");
    const surfaceStyle = window.getComputedStyle(moving ? view.surface : view.shell);
    return {
      surface: rect(view.surface), icon: rect(view.icon), label,
      corners: {
        borderTopLeftRadius: surfaceStyle.borderTopLeftRadius,
        borderTopRightRadius: surfaceStyle.borderTopRightRadius,
        borderBottomRightRadius: surfaceStyle.borderBottomRightRadius,
        borderBottomLeftRadius: surfaceStyle.borderBottomLeftRadius,
      },
      labelWidth: label.width * (1 - hidden), labelOpacity: Number(labelStyle.opacity),
      opacity: moving ? Number(surfaceStyle.opacity) : 1,
      background: surfaceStyle.backgroundColor, color: window.getComputedStyle(view.icon).color,
    };
  };
  const prepare = (direction: -1 | 1, target: string) => {
    // Capture the current shapes before React moves the tab slots.
    const snapshots = new Map<string, TabMotionSnapshot>();
    for (const [slot, view] of Object.entries(views.current)) {
      if (slot === "ghost" && !header.current?.hasAttribute("data-moving")) continue;
      const snapshot = read(view);
      const id = view.shell?.dataset.tabId;
      if (snapshot && id) snapshots.set(id, snapshot);
    }
    pending.current = { direction, target, snapshots };
  };

  useLayoutEffect(() => {
    const request = pending.current;
    pending.current = null;
    stop();
    const element = header.current;
    const window = element?.ownerDocument.defaultView;
    lastLayout.current = layout();
    if (!request || request.target !== active || !element || !window || !element.animate) return;
    const style = window.getComputedStyle(element);
    const duration = cssDuration(style.animationDuration);
    if (!duration || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const { rect, scale } = coordinates();
    const enteringEdge = request.direction === 1 ? rightEdge.current : leftEdge.current;
    const leavingEdge = request.direction === 1 ? leftEdge.current : rightEdge.current;
    if (!enteringEdge || !leavingEdge) return;
    const targets = Object.entries(views.current).map(([slot, view]) => ({ slot, view, snapshot: read(view) }));
    const running: Animation[] = [];
    for (const { slot, view, snapshot } of targets) {
      if (!snapshot || !view.shell) continue;
      const old = request.snapshots.get(view.shell.dataset.tabId || "");
      if (slot === "ghost" && !old) continue;
      const from = old || atBoundary(snapshot, rect(enteringEdge));
      const target = slot === "ghost" ? atBoundary(snapshot, rect(leavingEdge)) : snapshot;
      const parentScale = {
        x: view.shell.getBoundingClientRect().width / (view.shell.offsetWidth * scale.x) || 1,
        y: view.shell.getBoundingClientRect().height / (view.shell.offsetHeight * scale.y) || 1,
      };
      const frames = tabMotionFrames(from, target, parentScale, slot === "current", snapshot);
      for (const part of ["surface", "icon", "label"] as const) {
        running.push(view[part]!.animate(frames[part], { duration, easing: style.animationTimingFunction, fill: "both" }));
      }
    }
    element.setAttribute("data-moving", "");
    animations.current = running;
    const current = generation.current;
    void Promise.all(running.map((animation) => animation.finished.catch(() => {})))
      .then(() => { if (generation.current === current) stop(); });
    return stop;
  }, [active, labels]);

  useLayoutEffect(() => {
    const element = header.current;
    const window = element?.ownerDocument.defaultView;
    if (!element || !window) return;
    const observer = new window.ResizeObserver(() => {
      const next = layout();
      if (lastLayout.current !== next) stop();
      lastLayout.current = next;
    });
    observer.observe(element);
    for (const view of Object.values(views.current)) if (view.shell) observer.observe(view.shell);
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const changed = () => { if (motion.matches) stop(); };
    motion.addEventListener("change", changed);
    return () => { observer.disconnect(); motion.removeEventListener("change", changed); stop(); };
  }, []);
  return prepare;
}
