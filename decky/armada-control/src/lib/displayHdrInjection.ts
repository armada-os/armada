export const ARMADA_HDR_INJECTION_MARKER = "__armadaHdrDisplayInjection" as const;
export const DISPLAY_SETTINGS_ROUTE = "/settings/display" as const;
export const SETTINGS_ROOT_ROUTE = "/settings" as const;

const ADVANCED_HEADER_TOKEN = "#Settings_Display_Advanced_Header";
const HDR_TOGGLE_LABEL_TOKEN = "#Settings_HDR_Enable";
const HDR_TOGGLE_SETTING_TOKEN = "gamescope_hdr_enabled";
const HDR_BRIGHTNESS_LABEL_TOKEN = "#Settings_HDR_SDRContentBrightness";
const MAX_TREE_NODES = 4096;

type TreeNode = {
  type?: unknown;
  props?: Record<string, unknown>;
  [key: string]: unknown;
};

export type HdrInjectionKind = "toggle" | "brightness";

export type HdrInjectionStatus =
  | "injected"
  | "already-injected"
  | "fingerprint-mismatch"
  | "partial-injection";

export interface HdrInjectionResult {
  tree: unknown;
  status: HdrInjectionStatus;
}

export type HdrBrightnessReplacementFactory = (nativeBrightnessControl: unknown) => unknown;

function asTreeNode(value: unknown): TreeNode | undefined {
  return value !== null && typeof value === "object" ? value as TreeNode : undefined;
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
        sources.push(Function.prototype.toString.call(current));
      } catch {
        // A component with an unreadable source cannot satisfy the fingerprint.
      }
      const patch = (current as unknown as {
        __deckyPatch?: { original?: unknown };
      }).__deckyPatch;
      if (patch?.original) pending.push(patch.original);
      continue;
    }

    if (typeof current === "object") {
      const wrapped = current as { type?: unknown; render?: unknown };
      if (wrapped.type) pending.push(wrapped.type);
      if (wrapped.render) pending.push(wrapped.render);
    }
  }

  return sources;
}

function componentSourceContains(node: unknown, tokens: readonly string[]): boolean {
  const type = asTreeNode(node)?.type;
  if (!type) return false;
  return componentSources(type).some((source) => tokens.every((token) => source.includes(token)));
}

function walkKnownSettingsTree(tree: unknown, visit: (node: TreeNode) => void): void {
  const pending: unknown[] = [tree];
  const seen = new Set<unknown>();

  while (pending.length > 0 && seen.size < MAX_TREE_NODES) {
    const current = pending.pop();
    if (current === null || current === undefined || typeof current === "boolean") continue;

    if (Array.isArray(current)) {
      for (let index = current.length - 1; index >= 0; index -= 1) {
        pending.push(current[index]);
      }
      continue;
    }

    const node = asTreeNode(current);
    if (!node || seen.has(node)) continue;
    seen.add(node);
    visit(node);

    const children = node.props?.children;
    if (children !== undefined) pending.push(children);
    const propPages = node.props?.pages;
    if (propPages !== undefined) pending.push(propPages);
    if (node.pages !== undefined) pending.push(node.pages);
    if (node.content !== undefined) pending.push(node.content);
  }
}

/**
 * Finds the Display page content React element in Steam's Settings shell.
 * Only the exact current route is accepted, and it must occur once.
 */
export function findDisplaySettingsContentComponent(tree: unknown): TreeNode | undefined {
  const matches: TreeNode[] = [];
  walkKnownSettingsTree(tree, (node) => {
    if (node.route !== DISPLAY_SETTINGS_ROUTE) return;
    const content = asTreeNode(node.content);
    if (content?.type) matches.push(content);
  });
  return matches.length === 1 ? matches[0] : undefined;
}

/**
 * Finds Valve's Display > Advanced component by its localization token. The
 * match must be unique; ambiguity is treated as a Steam layout change.
 */
export function findAdvancedDisplayComponent(tree: unknown): TreeNode | undefined {
  const matches: TreeNode[] = [];
  walkKnownSettingsTree(tree, (node) => {
    if (componentSourceContains(node, [ADVANCED_HEADER_TOKEN])) matches.push(node);
  });
  return matches.length === 1 ? matches[0] : undefined;
}

function markerKind(node: unknown): HdrInjectionKind | undefined {
  const value = asTreeNode(node)?.props?.[ARMADA_HDR_INJECTION_MARKER];
  return value === "toggle" || value === "brightness" ? value : undefined;
}

function matchingIndices(children: unknown[], predicate: (child: unknown) => boolean): number[] {
  const matches: number[] = [];
  children.forEach((child, index) => {
    if (predicate(child)) matches.push(index);
  });
  return matches;
}

/**
 * Replaces the two adjacent native HDR placeholders in Valve's Advanced
 * display section. It never appends to an approximate location.
 */
export function injectAdvancedDisplayHdrControls(
  tree: unknown,
  toggleControl: unknown,
  brightnessControl: unknown | HdrBrightnessReplacementFactory,
): HdrInjectionResult {
  const root = asTreeNode(tree);
  const children = root?.props?.children;
  if (!root || typeof root.props?.label !== "string" || !Array.isArray(children)) {
    return { tree, status: "fingerprint-mismatch" };
  }

  const markerIndices = matchingIndices(children, (child) => markerKind(child) !== undefined);
  if (markerIndices.length > 0) {
    const kinds = markerIndices.map((index) => markerKind(children[index]));
    const complete = markerIndices.length === 2 &&
      kinds.includes("toggle") && kinds.includes("brightness") &&
      markerIndices[1] === markerIndices[0] + 1;
    return {
      tree,
      status: complete ? "already-injected" : "partial-injection",
    };
  }

  const toggleIndices = matchingIndices(children, (child) => {
    const props = asTreeNode(child)?.props;
    return props?.bAdvanced === true && componentSourceContains(
      child,
      [HDR_TOGGLE_LABEL_TOKEN, HDR_TOGGLE_SETTING_TOKEN],
    );
  });
  const brightnessIndices = matchingIndices(children, (child) => componentSourceContains(
    child,
    [HDR_BRIGHTNESS_LABEL_TOKEN],
  ));

  if (
    children.length < 6 || children.length > 20 ||
    toggleIndices.length !== 1 || brightnessIndices.length !== 1 ||
    brightnessIndices[0] !== toggleIndices[0] + 1
  ) {
    return { tree, status: "fingerprint-mismatch" };
  }

  const nextChildren = children.slice();
  nextChildren[toggleIndices[0]] = toggleControl;
  nextChildren[brightnessIndices[0]] = typeof brightnessControl === "function"
    ? brightnessControl(children[brightnessIndices[0]])
    : brightnessControl;

  return {
    tree: {
      ...root,
      props: {
        ...root.props,
        children: nextChildren,
      },
    },
    status: "injected",
  };
}
