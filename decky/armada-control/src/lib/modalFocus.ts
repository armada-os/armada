export interface ModalFocusTarget {
  element: HTMLElement;
  takeFocus: () => boolean;
  hasFocus: () => boolean;
  parent?: ModalFocusTarget;
}

interface WindowScopes {
  entries: ModalFocusTarget[];
  version: number;
}

const registered = new Set<ModalFocusTarget>();
const windows = new WeakMap<Document, WindowScopes>();
const visible = (scope: ModalFocusTarget) => scope.element.isConnected && scope.element.getClientRects().length > 0;

export function captureModalFocus(): ModalFocusTarget | undefined {
  const visibleScopes = [...registered].filter(visible);
  return visibleScopes.filter((scope) => scope.hasFocus()).pop()
    || visibleScopes.filter((scope) => scope.element.contains(scope.element.ownerDocument.activeElement)).pop()
    || (visibleScopes.length === 1 ? visibleScopes[0] : undefined);
}

// Steam can lose the opener when a reset removes its row while a dialog closes.
export function registerModalFocusScope(element: HTMLElement, takeFocus: () => boolean, hasFocus: () => boolean, modal = false, returnFocus?: ModalFocusTarget) {
  const document = element.ownerDocument;
  let state = windows.get(document);
  if (!state) {
    state = { entries: [], version: 0 };
    windows.set(document, state);
  }
  const owner = state;
  const parent = returnFocus || owner.entries.filter(visible).slice(-1)[0];
  const scope: ModalFocusTarget = { element, takeFocus, hasFocus, parent };
  registered.add(scope);
  owner.entries.push(scope);
  owner.version++;
  return {
    dispose() {
      const index = owner.entries.indexOf(scope);
      if (index < 0) return;
      registered.delete(scope);
      owner.entries.splice(index, 1);
      const version = ++owner.version;
      if (!modal || !parent) return;
      let source: ModalFocusTarget | undefined = parent;
      while (source && !registered.has(source)) source = source.parent;
      const sourceState = source && windows.get(source.element.ownerDocument);
      const sourceVersion = sourceState?.version;
      // QAM lives in a separate window, whose frame resumes when Steam reveals it.
      source?.element.ownerDocument.defaultView?.requestAnimationFrame(() => {
        if (version !== owner.version || sourceVersion !== sourceState?.version) return;
        let target: ModalFocusTarget | undefined = parent;
        while (target && (!registered.has(target) || !visible(target))) target = target.parent;
        // Steam can deactivate a navigation tree without sending a blur event.
        if (!target || target.hasFocus()) return;
        target.takeFocus();
      });
    },
  };
}
