import type { ReactNode } from "react";

export function AnimatedCollapse({ isOpen, children }: {
  isOpen: boolean;
  children: ReactNode;
}) {
  // Closed controls must leave Steam's navigation tree, not just be clipped.
  return isOpen ? <div className="afc-collapse">{children}</div> : null;
}
