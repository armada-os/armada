export const ARMADA_AUTO_HDR_QAM_MARKER = "__armadaAutoHdrPerformanceInjection" as const;
export const PERFORMANCE_QAM_TITLE_TOKEN = "#QuickAccess_Tab_Perf_Title" as const;
export const ALLOW_TEARING_SETTING_TOKEN = "gamescope_allow_tearing" as const;
export const ALLOW_TEARING_LABEL_TOKEN = "#QuickAccess_Tab_Perf_EnableTearing" as const;
export const ADVANCED_VIEW_TOKEN = "#Common_Advanced_View" as const;
export const BASIC_VIEW_TOKEN = "#Common_Basic_View" as const;

const MAX_REACT_TREE_NODES = 8192;
const MAX_FINGERPRINT_VALUES = 128;

type RecordLike = Record<string, unknown>;

export interface PerformanceHdrPanelInjection {
  index: number;
  originalPanel: unknown;
  wrappedPanel: unknown;
}

export type PerformanceHdrInjectionStatus =
  | "injected"
  | "already-injected"
  | "fingerprint-mismatch"
  | "marker-conflict";

export interface PerformanceHdrInjectionResult {
  tabs: readonly unknown[];
  status: PerformanceHdrInjectionStatus;
  injection?: PerformanceHdrPanelInjection;
}

export interface PerformanceHdrRestoreResult {
  tabs: readonly unknown[];
  status: "restored" | "already-restored" | "fingerprint-mismatch" | "not-owned";
}

export interface PerformanceHdrEvictionResult {
  tabs?: unknown[];
  status: PerformanceHdrRestoreResult["status"] | "empty" | "error";
  error?: unknown;
}

export interface PerformanceHdrControlsInjectionResult {
  tree: unknown;
  status: "injected" | "already-injected" | "fingerprint-mismatch" | "partial-injection";
}

export interface PerformanceHdrComponentWrapResult {
  tree: unknown;
  status: "wrapped" | "fingerprint-mismatch";
  count?: number;
}

export interface PerformanceHdrProbeOwnership {
  owner?: object;
}

export function claimPerformanceHdrProbeOwner(
  session: PerformanceHdrProbeOwnership,
  candidate: object,
): boolean {
  if (session.owner !== undefined && session.owner !== candidate) return false;
  session.owner = candidate;
  return true;
}

export function releasePerformanceHdrProbeOwner(
  session: PerformanceHdrProbeOwnership,
  candidate: object,
): void {
  if (session.owner === candidate) session.owner = undefined;
}

export function canDescendPerformanceComponent(
  depth: number,
  maxDepth = 4,
): boolean {
  return Number.isInteger(depth) &&
    Number.isInteger(maxDepth) &&
    depth >= 0 &&
    maxDepth >= 0 &&
    depth < maxDepth;
}

function asRecord(value: unknown): RecordLike | undefined {
  return value !== null && typeof value === "object" ? value as RecordLike : undefined;
}

export function isReactClassComponent(type: unknown): boolean {
  if (typeof type !== "function") return false;
  const prototype = asRecord(type.prototype);
  return prototype !== undefined && (
    prototype.isReactComponent !== undefined ||
    typeof prototype.render === "function"
  );
}

function componentSources(type: unknown): string[] {
  const sources: string[] = [];
  const pending = [type];
  const seen = new Set<unknown>();
  while (pending.length > 0 && seen.size < 16) {
    const current = pending.pop();
    if (current === null || current === undefined || seen.has(current)) continue;
    seen.add(current);
    if (typeof current === "function") {
      try {
        sources.push(String(current));
      } catch {
        // Unreadable component sources cannot satisfy an exact fingerprint.
      }
      continue;
    }
    const wrapper = asRecord(current);
    if (wrapper?.type) pending.push(wrapper.type);
    if (wrapper?.render) pending.push(wrapper.render);
  }
  return sources;
}

function collectPrimitiveProps(
  value: unknown,
  values: string[],
  seen: Set<unknown>,
  depth: number,
): void {
  if (values.length >= MAX_FINGERPRINT_VALUES || depth > 2) return;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    values.push(String(value));
    return;
  }
  if (value === null || value === undefined || typeof value !== "object" || seen.has(value)) return;
  seen.add(value);
  if (Array.isArray(value)) {
    value.slice(0, 16).forEach((item) => collectPrimitiveProps(item, values, seen, depth + 1));
    return;
  }
  const record = value as RecordLike;
  Object.entries(record).slice(0, 32).forEach(([key, item]) => {
    if (key === "children") return;
    values.push(key);
    collectPrimitiveProps(item, values, seen, depth + 1);
  });
}

function fingerprintContains(node: unknown, tokens: readonly string[]): boolean {
  const record = asRecord(node);
  if (!record) return false;
  const values = componentSources(record.type);
  collectPrimitiveProps(record.props, values, new Set(), 0);
  return tokens.every((token) => values.some((value) => value.includes(token)));
}

function childrenOf(node: unknown): unknown[] | undefined {
  const children = asRecord(asRecord(node)?.props)?.children;
  return Array.isArray(children) ? children : undefined;
}

function markerKind(node: unknown): "toggle" | undefined {
  const marker = asRecord(asRecord(node)?.props)?.[ARMADA_AUTO_HDR_QAM_MARKER];
  return marker === "toggle" ? marker : undefined;
}

function walkKnownQamTree(root: unknown, visit: (node: RecordLike) => void): void {
  const pending: unknown[] = [root];
  const seen = new Set<unknown>();
  while (pending.length > 0 && seen.size < MAX_REACT_TREE_NODES) {
    const current = pending.pop();
    if (current === null || current === undefined || typeof current === "boolean") continue;
    if (Array.isArray(current)) {
      for (let index = current.length - 1; index >= 0; index -= 1) pending.push(current[index]);
      continue;
    }
    const node = asRecord(current);
    if (!node || seen.has(node)) continue;
    seen.add(node);
    visit(node);
    const props = asRecord(node.props);
    if (props && Object.prototype.hasOwnProperty.call(props, "children")) pending.push(props.children);
    if (node.children !== undefined) pending.push(node.children);
    if (node.child !== undefined) pending.push(node.child);
    if (node.sibling !== undefined) pending.push(node.sibling);
  }
}

export function findUniqueQamMenuElement(tree: unknown): RecordLike | undefined {
  const matches: RecordLike[] = [];
  walkKnownQamTree(tree, (node) => {
    const props = asRecord(node.props);
    if (
      typeof props?.onFocusNavActivated === "function" &&
      typeof props?.onFocusNavDeactivated === "function" &&
      node.type !== undefined
    ) matches.push(node);
  });
  return matches.length === 1 ? matches[0] : undefined;
}

export function findUniqueQamTabsArray(tree: unknown): unknown[] | undefined {
  const matches = new Set<unknown[]>();
  walkKnownQamTree(tree, (node) => {
    const tabs = asRecord(node.props)?.tabs;
    if (Array.isArray(tabs)) matches.add(tabs);
  });
  return matches.size === 1 ? matches.values().next().value : undefined;
}

function titleToken(tab: unknown): unknown {
  return asRecord(asRecord(asRecord(tab)?.title)?.props)?.locId;
}

function exactPerformanceIndices(tabs: readonly unknown[], performanceKey: unknown): number[] {
  const matches: number[] = [];
  tabs.forEach((tab, index) => {
    const descriptor = asRecord(tab);
    if (descriptor?.key === performanceKey && titleToken(tab) === PERFORMANCE_QAM_TITLE_TOKEN) {
      matches.push(index);
    }
  });
  return matches;
}

function wrapperProps(panel: unknown): RecordLike | undefined {
  return asRecord(asRecord(panel)?.props);
}

function isWrapped(panel: unknown): boolean {
  return wrapperProps(panel)?.[ARMADA_AUTO_HDR_QAM_MARKER] === "panel";
}

function originalPanel(panel: unknown): unknown {
  const props = wrapperProps(panel);
  return props && Object.prototype.hasOwnProperty.call(props, "nativePanel")
    ? props.nativePanel
    : undefined;
}

export function injectPerformanceHdrPanel(
  tabs: readonly unknown[],
  performanceKey: unknown,
  createWrappedPanel: (nativePanel: unknown) => unknown,
): PerformanceHdrInjectionResult {
  if (!Array.isArray(tabs)) return { tabs, status: "fingerprint-mismatch" };
  const indices = exactPerformanceIndices(tabs, performanceKey);
  if (indices.length !== 1) return { tabs, status: "fingerprint-mismatch" };
  const index = indices[0];
  const descriptor = asRecord(tabs[index]);
  if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, "panel")) {
    return { tabs, status: "fingerprint-mismatch" };
  }
  const markedPanels = tabs.filter((tab) => isWrapped(asRecord(tab)?.panel));
  const currentPanel = descriptor.panel;
  if (isWrapped(currentPanel)) {
    const original = originalPanel(currentPanel);
    if (markedPanels.length !== 1 || original === undefined) {
      return { tabs, status: "marker-conflict" };
    }
    return {
      tabs,
      status: "already-injected",
      injection: { index, originalPanel: original, wrappedPanel: currentPanel },
    };
  }
  if (markedPanels.length !== 0 || currentPanel === undefined || currentPanel === null) {
    return { tabs, status: markedPanels.length ? "marker-conflict" : "fingerprint-mismatch" };
  }
  let wrappedPanel: unknown;
  try {
    wrappedPanel = createWrappedPanel(currentPanel);
  } catch {
    return { tabs, status: "fingerprint-mismatch" };
  }
  if (!isWrapped(wrappedPanel) || originalPanel(wrappedPanel) !== currentPanel) {
    return { tabs, status: "marker-conflict" };
  }
  const nextTabs = tabs.slice();
  nextTabs[index] = { ...descriptor, panel: wrappedPanel };
  return {
    tabs: nextTabs,
    status: "injected",
    injection: { index, originalPanel: currentPanel, wrappedPanel },
  };
}

export function restorePerformanceHdrPanel(
  tabs: readonly unknown[],
  performanceKey: unknown,
  injection: PerformanceHdrPanelInjection,
): PerformanceHdrRestoreResult {
  if (!Array.isArray(tabs)) return { tabs, status: "fingerprint-mismatch" };
  const indices = exactPerformanceIndices(tabs, performanceKey);
  if (indices.length !== 1) return { tabs, status: "fingerprint-mismatch" };
  const index = indices[0];
  const descriptor = asRecord(tabs[index]);
  if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, "panel")) {
    return { tabs, status: "fingerprint-mismatch" };
  }
  if (descriptor.panel === injection.originalPanel) return { tabs, status: "already-restored" };
  if (descriptor.panel !== injection.wrappedPanel) return { tabs, status: "not-owned" };
  const nextTabs = tabs.slice();
  nextTabs[index] = { ...descriptor, panel: injection.originalPanel };
  return { tabs: nextTabs, status: "restored" };
}

/** Restores and forgets the least-recently-used owned QAM tree. */
export function evictOldestPerformanceHdrInjection(
  activeInjections: Map<unknown[], PerformanceHdrPanelInjection>,
  performanceKey: unknown,
): PerformanceHdrEvictionResult {
  const oldest = activeInjections.entries().next().value as
    | [unknown[], PerformanceHdrPanelInjection]
    | undefined;
  if (!oldest) return { status: "empty" };
  const [tabs, injection] = oldest;
  try {
    const result = restorePerformanceHdrPanel(tabs, performanceKey, injection);
    if (result.status === "restored") tabs.splice(0, tabs.length, ...result.tabs);
    return { tabs, status: result.status };
  } catch (error) {
    return { tabs, status: "error", error };
  } finally {
    activeInjections.delete(tabs);
  }
}

function cloneReplacingNode(
  root: unknown,
  target: unknown,
  replacement: unknown,
): { tree: unknown; replacements: number } {
  if (root === target) return { tree: replacement, replacements: 1 };
  if (Array.isArray(root)) {
    let replacements = 0;
    const next = root.map((child) => {
      const result = cloneReplacingNode(child, target, replacement);
      replacements += result.replacements;
      return result.tree;
    });
    return { tree: replacements ? next : root, replacements };
  }
  const record = asRecord(root);
  const props = asRecord(record?.props);
  if (!record || !props || !Object.prototype.hasOwnProperty.call(props, "children")) {
    return { tree: root, replacements: 0 };
  }
  const result = cloneReplacingNode(props.children, target, replacement);
  if (result.replacements === 0) return { tree: root, replacements: 0 };
  return {
    tree: { ...record, props: { ...props, children: result.tree } },
    replacements: result.replacements,
  };
}

function directParentsOf(
  tree: unknown,
  child: unknown,
): Array<{ node: RecordLike; children: unknown[]; scalar: boolean }> {
  const matches: Array<{
    node: RecordLike;
    children: unknown[];
    scalar: boolean;
  }> = [];
  walkKnownQamTree(tree, (node) => {
    const props = asRecord(node.props);
    if (!props || !Object.prototype.hasOwnProperty.call(props, "children")) return;
    if (Array.isArray(props.children)) {
      props.children.forEach((candidate) => {
        if (candidate === child) {
          matches.push({ node, children: props.children as unknown[], scalar: false });
        }
      });
    } else if (props.children === child) {
      matches.push({ node, children: [child], scalar: true });
    }
  });
  return matches;
}

function cloneParentWithInsertions(
  parent: RecordLike,
  insertions: ReadonlyMap<unknown, unknown>,
): RecordLike | undefined {
  const props = asRecord(parent.props);
  if (!props || !Object.prototype.hasOwnProperty.call(props, "children")) {
    return undefined;
  }
  const children = Array.isArray(props.children)
    ? props.children
    : [props.children];
  const next: unknown[] = [];
  children.forEach((child) => {
    next.push(child);
    const control = insertions.get(child);
    if (control !== undefined) next.push(control);
  });
  return {
    ...parent,
    props: { ...props, children: next },
  };
}

function directInsertionLocation(
  tree: unknown,
  anchor: unknown,
): { parent: RecordLike; anchor: unknown } | undefined {
  const anchorParents = directParentsOf(tree, anchor);
  if (anchorParents.length !== 1) return undefined;
  const anchorParent = anchorParents[0];
  if (!anchorParent.scalar) {
    return { parent: anchorParent.node, anchor };
  }
  const ownerParents = directParentsOf(tree, anchorParent.node);
  if (ownerParents.length !== 1) return undefined;
  return {
    parent: ownerParents[0].node,
    anchor: anchorParent.node,
  };
}

function cloneReplacingNodes(
  root: unknown,
  replacements: ReadonlyMap<unknown, unknown>,
): { tree: unknown; replacements: number } {
  const ownReplacement = replacements.has(root) ? 1 : 0;
  const current = ownReplacement ? replacements.get(root) : root;
  if (Array.isArray(current)) {
    let count = ownReplacement;
    const next = current.map((child) => {
      const result = cloneReplacingNodes(child, replacements);
      count += result.replacements;
      return result.tree;
    });
    return { tree: count ? next : current, replacements: count };
  }
  const record = asRecord(current);
  const props = asRecord(record?.props);
  if (!record || !props || !Object.prototype.hasOwnProperty.call(props, "children")) {
    return { tree: current, replacements: ownReplacement };
  }
  const result = cloneReplacingNodes(props.children, replacements);
  if (result.replacements === 0) {
    return { tree: current, replacements: ownReplacement };
  }
  return {
    tree: { ...record, props: { ...props, children: result.tree } },
    replacements: ownReplacement + result.replacements,
  };
}

/**
 * Wraps one unambiguous function-component leaf so a caller can inspect the
 * next rendered layer. This is intentionally bounded by the caller.
 */
export function wrapPerformanceComponents(
  tree: unknown,
  wrap: (element: RecordLike, index: number) => unknown,
): PerformanceHdrComponentWrapResult {
  let level: unknown[] = [tree];
  let visited = 0;
  let candidates: RecordLike[] = [];
  while (
    level.length > 0 &&
    visited < MAX_REACT_TREE_NODES &&
    candidates.length === 0
  ) {
    const next: unknown[] = [];
    const seen = new Set<unknown>();
    for (const current of level) {
      if (Array.isArray(current)) {
        next.push(...current);
        continue;
      }
      const node = asRecord(current);
      if (!node || seen.has(node)) continue;
      seen.add(node);
      visited += 1;
      if (
        typeof node.type === "function" &&
        !isReactClassComponent(node.type)
      ) {
        candidates.push(node);
        continue;
      }
      const props = asRecord(node.props);
      if (props && Object.prototype.hasOwnProperty.call(props, "children")) {
        next.push(props.children);
      }
    }
    if (candidates.length === 0) level = next;
  }
  candidates = candidates.filter((node) =>
    markerKind(node) === undefined &&
    !fingerprintContains(node, [ADVANCED_VIEW_TOKEN]) &&
    !fingerprintContains(node, [BASIC_VIEW_TOKEN]) &&
    !fingerprintContains(
      node,
      [ALLOW_TEARING_SETTING_TOKEN, ALLOW_TEARING_LABEL_TOKEN],
    ));
  if (candidates.length === 0 || candidates.length > 32) {
    return { tree, status: "fingerprint-mismatch" };
  }
  const replacements = new Map<unknown, unknown>();
  try {
    candidates.forEach((candidate, index) => {
      replacements.set(candidate, wrap(candidate, index));
    });
  } catch {
    return { tree, status: "fingerprint-mismatch" };
  }
  const replacement = cloneReplacingNodes(tree, replacements);
  return replacement.replacements === replacements.size
    ? { tree: replacement.tree, status: "wrapped", count: replacements.size }
    : { tree, status: "fingerprint-mismatch" };
}

/**
 * Inserts the AutoHDR toggle after Valve's unique Allow Tearing anchor while
 * requiring the expected Advanced View container to be present.
 */
export function injectPerformanceHdrControls(
  tree: unknown,
  toggleControl: unknown,
): PerformanceHdrControlsInjectionResult {
  const markerNodes: unknown[] = [];
  walkKnownQamTree(tree, (node) => {
    if (markerKind(node)) markerNodes.push(node);
  });
  if (markerNodes.length > 0) {
    return {
      tree,
      status: markerNodes.length === 1
        ? "already-injected"
        : "partial-injection",
    };
  }

  const advancedMatches: RecordLike[] = [];
  const tearingMatches: RecordLike[] = [];
  walkKnownQamTree(tree, (node) => {
    if (fingerprintContains(node, [ADVANCED_VIEW_TOKEN])) {
      advancedMatches.push(node);
    }
    if (fingerprintContains(node, [ALLOW_TEARING_SETTING_TOKEN, ALLOW_TEARING_LABEL_TOKEN])) {
      tearingMatches.push(node);
    }
  });
  if (
    advancedMatches.length !== 1 ||
    tearingMatches.length !== 1
  ) {
    return { tree, status: "fingerprint-mismatch" };
  }

  const advanced = advancedMatches[0];
  if (!advanced) return { tree, status: "fingerprint-mismatch" };
  let tearingUnderAdvanced = false;
  walkKnownQamTree(advanced, (node) => {
    if (node === tearingMatches[0]) tearingUnderAdvanced = true;
  });
  if (!tearingUnderAdvanced) {
    return { tree, status: "fingerprint-mismatch" };
  }
  const tearingLocation = directInsertionLocation(tree, tearingMatches[0]);
  if (!tearingLocation) {
    return { tree, status: "fingerprint-mismatch" };
  }

  const insertions = new Map<RecordLike, Map<unknown, unknown>>();
  const addInsertion = (parent: RecordLike, anchor: unknown, control: unknown) => {
    const owned = insertions.get(parent) ?? new Map<unknown, unknown>();
    if (owned.has(anchor)) return false;
    owned.set(anchor, control);
    insertions.set(parent, owned);
    return true;
  };
  if (!addInsertion(tearingLocation.parent, tearingLocation.anchor, toggleControl)) {
    return { tree, status: "fingerprint-mismatch" };
  }
  const replacements = new Map<unknown, unknown>();
  insertions.forEach((owned, parent) => {
    const replacement = cloneParentWithInsertions(parent, owned);
    if (replacement) replacements.set(parent, replacement);
  });
  const replacement = cloneReplacingNodes(tree, replacements);
  if (replacement.replacements !== replacements.size) {
    return { tree, status: "fingerprint-mismatch" };
  }
  return { tree: replacement.tree, status: "injected" };
}
