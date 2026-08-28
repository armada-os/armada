import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

const COLLAPSE_TRANSITION_MS = 200;

type CollapsePhase = "closed" | "opening" | "open" | "closing";

export function AnimatedCollapse({ isOpen, children }: {
  isOpen: boolean;
  children: ReactNode;
}) {
  const [phase, setPhase] = useState<CollapsePhase>(isOpen ? "open" : "closed");
  const [height, setHeight] = useState<number | "auto">(isOpen ? "auto" : 0);
  const innerRef = useRef<HTMLDivElement | null>(null);
  const firstRender = useRef(true);

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    setPhase(isOpen ? "opening" : "closing");
  }, [isOpen]);

  useEffect(() => {
    if (phase === "opening") {
      const raf = requestAnimationFrame(() => setHeight(innerRef.current?.scrollHeight ?? 0));
      const timeout = window.setTimeout(() => {
        setPhase("open");
        setHeight("auto");
      }, COLLAPSE_TRANSITION_MS);
      return () => {
        cancelAnimationFrame(raf);
        window.clearTimeout(timeout);
      };
    }
    if (phase === "closing") {
      setHeight(innerRef.current?.scrollHeight ?? 0);
      const raf = requestAnimationFrame(() => setHeight(0));
      const timeout = window.setTimeout(() => setPhase("closed"), COLLAPSE_TRANSITION_MS);
      return () => {
        cancelAnimationFrame(raf);
        window.clearTimeout(timeout);
      };
    }
    return undefined;
  }, [phase]);

  if (phase === "closed") return null;

  return (
    <div className="afc-collapse" style={{ maxHeight: height === "auto" ? "none" : height }}>
      <div ref={innerRef}>{children}</div>
    </div>
  );
}
