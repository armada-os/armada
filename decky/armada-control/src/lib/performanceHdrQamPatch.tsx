import {
  QuickAccessTab,
  afterPatch,
  createReactTreePatcher,
  findInReactTree,
  findModuleByExport,
  getReactRoot,
} from "@decky/ui";
import type { Patch } from "@decky/ui";
import {
  Component,
  createElement,
  useEffect,
  useState,
} from "react";
import type { ErrorInfo, ReactElement, ReactNode } from "react";
import { AutoHDRQamToggleControl } from "../components/HDR";
import {
  ARMADA_AUTO_HDR_QAM_MARKER,
  canDescendPerformanceComponent,
  claimPerformanceHdrProbeOwner,
  evictOldestPerformanceHdrInjection,
  findUniqueQamMenuElement,
  findUniqueQamTabsArray,
  injectPerformanceHdrControls,
  injectPerformanceHdrPanel,
  isReactClassComponent,
  restorePerformanceHdrPanel,
  releasePerformanceHdrProbeOwner,
  wrapPerformanceComponents,
} from "./performanceHdrInjection";
import type { PerformanceHdrPanelInjection } from "./performanceHdrInjection";

const QAM_BROWSER_SOURCE_TOKEN = "QuickAccessMenuBrowserView";
const QAM_EMBEDDED_SOURCE_TOKEN = "QuickAccessMenuEmbedded";
const MAX_TRACKED_QAM_TREES = 8;
const MAX_PERFORMANCE_COMPONENT_DEPTH = 4;
const MAX_PERFORMANCE_PROBES = 32;
const performanceComponentTypeIds = new WeakMap<Function, number>();
let nextPerformanceComponentTypeId = 1;

type RecordLike = Record<string, unknown>;
type QamRenderer = RecordLike & { type: unknown };

interface BoundaryState { failed: boolean }
interface ArmadaPerformancePanelProps {
  nativePanel: ReactElement;
  [ARMADA_AUTO_HDR_QAM_MARKER]: "panel";
}
interface ArmadaPerformanceProbeProps {
  nativePanel: ReactElement;
  depth: number;
  session: PerformanceProbeSession;
}
interface PerformanceProbeSession {
  disposed: boolean;
  remaining: number;
  owner?: object;
  patches: Set<Patch>;
}

class AutoHdrQamErrorBoundary extends Component<{
  children?: ReactNode;
  [ARMADA_AUTO_HDR_QAM_MARKER]?: "toggle";
}, BoundaryState> {
  state: BoundaryState = { failed: false };
  static getDerivedStateFromError(): BoundaryState { return { failed: true }; }
  componentDidCatch(error: unknown, info: ErrorInfo): void {
    console.error("[Armada Control] Performance QAM Auto HDR control failed safely", error, info);
  }
  render(): ReactNode { return this.state.failed ? null : this.props.children; }
}

function patchableElement(value: unknown): value is ReactElement & {
  type: Function;
  props: Record<string, unknown>;
} {
  const record = asRecord(value);
  return typeof record?.type === "function" &&
    !isReactClassComponent(record.type) &&
    asRecord(record.props) !== undefined;
}

function performanceComponentTypeId(type: Function): number {
  const existing = performanceComponentTypeIds.get(type);
  if (existing !== undefined) return existing;
  const assigned = nextPerformanceComponentTypeId++;
  performanceComponentTypeIds.set(type, assigned);
  return assigned;
}

function createPerformanceProbeSession(): PerformanceProbeSession {
  return {
    disposed: false,
    remaining: MAX_PERFORMANCE_PROBES,
    patches: new Set(),
  };
}

function disposePerformanceProbeSession(session: PerformanceProbeSession): void {
  if (session.disposed) return;
  session.disposed = true;
  session.patches.forEach((patch) => {
    try {
      if (!patch.hasUnpatched) patch.unpatch();
    } catch {
      // The root session is already being removed, so fail closed.
    }
  });
  session.patches.clear();
  session.owner = undefined;
}

function ArmadaPerformanceProbe({
  nativePanel,
  depth,
  session,
}: ArmadaPerformanceProbeProps) {
  const [owned] = useState(() => {
    if (
      session.disposed ||
      session.remaining <= 0 ||
      !patchableElement(nativePanel)
    ) return undefined;
    session.remaining -= 1;
    const holder = { type: nativePanel.type };
    const transformTree = (tree: unknown): unknown => {
        if (session.disposed) return tree;
        const toggle = createElement(
          AutoHdrQamErrorBoundary,
          {
            key: "armada-autohdr-toggle-boundary",
            [ARMADA_AUTO_HDR_QAM_MARKER]: "toggle",
          },
          createElement(AutoHDRQamToggleControl),
        );
        const result = injectPerformanceHdrControls(tree, toggle);
        if (result.status === "injected" || result.status === "already-injected") {
          if (!claimPerformanceHdrProbeOwner(session, holder)) return tree;
          return result.tree;
        }
        if (result.status === "partial-injection") {
          console.warn(
            "[Armada Control] Performance QAM AutoHDR inner placement skipped: partial-injection",
          );
          return tree;
        }
        if (canDescendPerformanceComponent(depth, MAX_PERFORMANCE_COMPONENT_DEPTH)) {
          const deeper = wrapPerformanceComponents(tree, (element, index) =>
            createElement(ArmadaPerformanceProbe, {
              key: `armada-autohdr-performance-probe-${depth + 1}-${index}-${performanceComponentTypeId(element.type as Function)}`,
              nativePanel: element as unknown as ReactElement,
              depth: depth + 1,
              session,
            }));
          if (deeper.status === "wrapped") return deeper.tree;
        }
        console.warn(
          `[Armada Control] Performance QAM AutoHDR inner placement skipped: ${result.status}`,
        );
        return tree;
      };
    const patch = afterPatch(
      holder,
      "type",
      (_args: unknown[], tree: unknown) => transformTree(tree),
    );
    session.patches.add(patch);
    return { holder, patch };
  });

  useEffect(() => () => {
    if (!owned) return;
    try {
      if (!owned.patch.hasUnpatched) owned.patch.unpatch();
    } catch (error) {
      console.warn("[Armada Control] Could not release Performance QAM AutoHDR inner patch", error);
    } finally {
      session.patches.delete(owned.patch);
      releasePerformanceHdrProbeOwner(session, owned.holder);
    }
  }, [owned, session]);

  return owned
    ? { ...nativePanel, type: owned.holder.type } as ReactElement
    : nativePanel;
}

function ArmadaPerformancePanel({ nativePanel }: ArmadaPerformancePanelProps) {
  const [session] = useState(createPerformanceProbeSession);
  useEffect(() => () => disposePerformanceProbeSession(session), [session]);
  return createElement(ArmadaPerformanceProbe, {
    key: patchableElement(nativePanel)
      ? `armada-autohdr-performance-probe-0-${performanceComponentTypeId(nativePanel.type)}`
      : "armada-autohdr-performance-probe-0-unpatchable",
    nativePanel,
    depth: 0,
    session,
  });
}

function asRecord(value: unknown): RecordLike | undefined {
  return value !== null && typeof value === "object" ? value as RecordLike : undefined;
}

function rendererSourceIncludes(value: unknown, token: string): boolean {
  const type = asRecord(value)?.type;
  if (typeof type !== "function") return false;
  try { return String(type).includes(token); } catch { return false; }
}

function uniqueRenderers(module: unknown, token: string): QamRenderer[] {
  const record = asRecord(module);
  if (!record) return [];
  return Array.from(new Set(Object.values(record).filter(
    (value): value is QamRenderer => rendererSourceIncludes(value, token),
  )));
}

function replaceArrayContents(target: unknown[], replacement: readonly unknown[]): void {
  target.splice(0, target.length, ...replacement);
}

function rebindCurrentQamFiber(renderer: QamRenderer): void {
  try {
    const rootElement = document.getElementById("root");
    if (!rootElement) return;
    const root = getReactRoot(rootElement);
    const fiber = root && findInReactTree(root, (node) => node?.elementType === renderer);
    const nextType = fiber?.elementType?.type;
    if (!fiber || nextType === undefined) return;
    fiber.type = nextType;
    if (fiber.alternate) fiber.alternate.type = nextType;
  } catch (error) {
    console.warn("[Armada Control] Could not rebind the active Performance QAM renderer", error);
  }
}

/** Places contextual AutoHDR controls at exact native Performance anchors. */
export function registerPerformanceHdrQamPatch(): () => void {
  const warned = new Set<string>();
  const patches: Patch[] = [];
  const activeInjections = new Map<unknown[], PerformanceHdrPanelInjection>();
  const warnOnce = (key: string, message: string, detail?: unknown) => {
    if (warned.has(key)) return;
    warned.add(key);
    console.warn(`[Armada Control] ${message}`, detail ?? "");
  };

  let qamModule: unknown;
  try {
    qamModule = findModuleByExport((moduleExport) =>
      rendererSourceIncludes(moduleExport, QAM_BROWSER_SOURCE_TOKEN));
  } catch (error) {
    warnOnce("module-search", "Performance QAM Auto HDR injection skipped: module lookup failed", error);
    return () => {};
  }
  const browser = uniqueRenderers(qamModule, QAM_BROWSER_SOURCE_TOKEN);
  const embedded = uniqueRenderers(qamModule, QAM_EMBEDDED_SOURCE_TOKEN);
  if (browser.length !== 1 || embedded.length > 1) {
    warnOnce("renderer-fingerprint", "Performance QAM Auto HDR injection skipped: renderer fingerprint mismatch");
    return () => {};
  }
  const renderers = [...browser, ...embedded];

  const patchHandler = createReactTreePatcher(
    [(tree: unknown) => {
      const menu = findUniqueQamMenuElement(tree);
      if (!menu) warnOnce("menu-fingerprint", "Performance QAM Auto HDR injection skipped: menu fingerprint mismatch");
      return menu;
    }],
    (_args: unknown[], tree: unknown) => {
      try {
        const tabs = findUniqueQamTabsArray(tree);
        if (!tabs) {
          warnOnce("tabs-fingerprint", "Performance QAM Auto HDR injection skipped: tab descriptor mismatch");
          return tree;
        }
        const result = injectPerformanceHdrPanel(
          tabs,
          QuickAccessTab.Perf,
          (nativePanel) => createElement(ArmadaPerformancePanel, {
            nativePanel: nativePanel as ReactElement,
            [ARMADA_AUTO_HDR_QAM_MARKER]: "panel",
          }),
        );
        if (result.status === "injected") replaceArrayContents(tabs, result.tabs);
        if (result.injection) {
          activeInjections.delete(tabs);
          activeInjections.set(tabs, result.injection);
          while (activeInjections.size > MAX_TRACKED_QAM_TREES) {
            const eviction = evictOldestPerformanceHdrInjection(
              activeInjections,
              QuickAccessTab.Perf,
            );
            if (eviction.status === "empty") break;
            if (eviction.status !== "restored" && eviction.status !== "already-restored") {
              warnOnce(
                `eviction-${eviction.status}`,
                `Could not restore an evicted Performance QAM panel: ${eviction.status}`,
                eviction.error,
              );
            }
          }
        }
        if (result.status === "fingerprint-mismatch" || result.status === "marker-conflict") {
          warnOnce(`descriptor-${result.status}`, `Performance QAM Auto HDR injection skipped: ${result.status}`);
        }
      } catch (error) {
        warnOnce("render-error", "Performance QAM Auto HDR injection failed safely", error);
      }
      return tree;
    },
    "ArmadaPerformanceQamAutoHDR",
  );

  try {
    renderers.forEach((renderer) => patches.push(afterPatch(renderer, "type", patchHandler)));
    renderers.forEach(rebindCurrentQamFiber);
  } catch (error) {
    warnOnce("patch-error", "Performance QAM Auto HDR renderer patch failed safely", error);
    patches.reverse().forEach((patch) => {
      try {
        if (!patch.hasUnpatched) patch.unpatch();
      } catch (rollbackError) {
        warnOnce("rollback-error", "Could not roll back a partial Performance QAM patch", rollbackError);
      }
    });
    renderers.forEach(rebindCurrentQamFiber);
    return () => {};
  }

  let removed = false;
  return () => {
    if (removed) return;
    removed = true;
    activeInjections.forEach((injection, tabs) => {
      try {
        const result = restorePerformanceHdrPanel(tabs, QuickAccessTab.Perf, injection);
        if (result.status === "restored") replaceArrayContents(tabs, result.tabs);
      } catch (error) {
        warnOnce("restore-error", "Could not restore a Performance QAM panel safely", error);
      }
    });
    activeInjections.clear();
    patches.reverse().forEach((patch) => {
      try { if (!patch.hasUnpatched) patch.unpatch(); }
      catch (error) { warnOnce("unpatch-error", "Could not remove the Performance QAM Auto HDR patch", error); }
    });
    renderers.forEach(rebindCurrentQamFiber);
  };
}
