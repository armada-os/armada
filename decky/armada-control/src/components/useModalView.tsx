import { useLayoutEffect, useState, useSyncExternalStore } from "react";
import type { ReactElement, ReactNode } from "react";

interface ModalViewSource {
  getSnapshot: () => ReactNode;
  subscribe: (listener: () => void) => () => void;
  publish: (content: ReactNode) => void;
}

function createSource(content: ReactNode): ModalViewSource {
  let snapshot = content;
  const listeners = new Set<() => void>();
  return {
    getSnapshot: () => snapshot,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },
    publish: (next) => {
      if (Object.is(snapshot, next)) return;
      snapshot = next;
      for (const listener of listeners) listener();
    },
  };
}

function ModalView({ source }: { source: ModalViewSource }) {
  return useSyncExternalStore(source.subscribe, source.getSnapshot, source.getSnapshot);
}

// Decky dialogs render separately, so publish content without replacing their native root.
export function useModalView(content: ReactNode): ReactElement {
  const [view] = useState(() => {
    const source = createSource(content);
    return { source, element: <ModalView source={source} /> };
  });
  useLayoutEffect(() => { view.source.publish(content); }, [view, content]);
  return view.element;
}
