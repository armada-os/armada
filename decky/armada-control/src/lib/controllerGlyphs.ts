import {
  Router,
  findSP,
  getGamepadNavigationTrees,
} from "@decky/ui";

export const CONTROLLER_GLYPH_PROFILE_STYLESHEETS = {
  "AYN Odin 3": [
    "themes/armada/ayn-retroid-buttons.css",
    "themes/ayn/odin-3.css",
  ],
} as const;

export type ControllerGlyphVariant =
  keyof typeof CONTROLLER_GLYPH_PROFILE_STYLESHEETS;
export type ControllerGlyphStyle = "Monochrome" | "Rainbow";

export const CONTROLLER_GLYPH_STYLES = [
  "Monochrome",
  "Rainbow",
] as const satisfies readonly ControllerGlyphStyle[];

const RAINBOW_STYLESHEET =
  "themes/ayn/odin-3-colored-face-buttons.css";
const PLUGIN_THEME_URL = new URL(
  "./controller-theme/",
  import.meta.url,
);
const LINK_ATTRIBUTE = "data-armada-controller-glyph-theme";
const RECONCILE_INTERVAL_MS = 1000;

type ActiveTheme = {
  variant: ControllerGlyphVariant;
  style: ControllerGlyphStyle;
  urls: readonly string[];
};

let activeTheme: ActiveTheme | undefined;
let reconcileTimer: ReturnType<typeof setInterval> | undefined;
const managedDocuments = new Set<Document>();

export function normalizeControllerGlyphStyle(
  value: unknown,
): ControllerGlyphStyle {
  return typeof value === "string" && value.trim().toLowerCase() === "rainbow"
    ? "Rainbow"
    : "Monochrome";
}

export function supportsControllerGlyphVariant(
  value: unknown,
): value is ControllerGlyphVariant {
  return value === "AYN Odin 3";
}

export function supportsControllerButtonStyle(
  variant: unknown,
): variant is ControllerGlyphVariant {
  return supportsControllerGlyphVariant(variant);
}

export function getControllerGlyphStylesheets(
  variant: ControllerGlyphVariant,
  style: unknown = "Monochrome",
): readonly string[] {
  const stylesheets: string[] = [
    ...CONTROLLER_GLYPH_PROFILE_STYLESHEETS[variant],
  ];
  if (normalizeControllerGlyphStyle(style) === "Rainbow") {
    stylesheets.push(RAINBOW_STYLESHEET);
  }
  return stylesheets;
}

function collectDocuments(): Set<Document> {
  const documents = new Set<Document>();
  const addDocument = (candidate: Document | null | undefined) => {
    try {
      if (candidate?.head) {
        documents.add(candidate);
      }
    } catch {
      // Steam windows can disappear while their documents are discovered.
    }
  };
  const addWindow = (candidate: Window | null | undefined) => {
    try {
      addDocument(candidate?.document);
    } catch {
      // Steam windows can disappear while their documents are discovered.
    }
  };

  if (typeof document !== "undefined") {
    addDocument(document);
  }

  try {
    const store = Router.WindowStore;
    addWindow(store?.GamepadUIMainWindowInstance?.BrowserWindow);
    for (const steamWindow of store?.SteamUIWindows ?? []) {
      addWindow(steamWindow.BrowserWindow);
    }
    for (const overlayWindow of store?.OverlayWindows ?? []) {
      addWindow(overlayWindow.BrowserWindow);
    }
  } catch {
    // Steam may still be creating its main, SP, or QAM window.
  }

  try {
    addWindow(findSP());
  } catch {
    // The SP window may not have a navigation tree yet.
  }

  try {
    const trees = getGamepadNavigationTrees();
    const treeList = Array.isArray(trees)
      ? trees
      : trees && typeof trees === "object"
        ? Object.values(trees)
        : [];
    for (const tree of treeList) {
      addDocument(
        ((tree as any)?.m_Root?.m_element?.ownerDocument ??
          (tree as any)?.Root?.Element?.ownerDocument) as
          | Document
          | undefined,
      );
    }
  } catch {
    // SP and QAM navigation trees are rebuilt as routes and overlays change.
  }

  return documents;
}

function linksIn(target: Document): HTMLLinkElement[] {
  try {
    return [
      ...target.querySelectorAll<HTMLLinkElement>(
        `link[${LINK_ATTRIBUTE}]`,
      ),
    ];
  } catch {
    return [];
  }
}

function clearDocument(target: Document): void {
  try {
    for (const link of linksIn(target)) {
      link.remove();
    }
  } catch {
    // Cleanup is best effort if Steam destroys the window concurrently.
  }
}

function reconcileDocument(
  target: Document,
  urls: readonly string[],
): void {
  try {
    const existing = linksIn(target);
    if (
      existing.length === urls.length &&
      existing.every((link, index) => link.href === urls[index])
    ) {
      return;
    }

    clearDocument(target);
    for (const url of urls) {
      const link = target.createElement("link");
      link.rel = "stylesheet";
      link.href = url;
      link.setAttribute(LINK_ATTRIBUTE, "");
      link.onerror = () => {
        console.warn(
          `[Armada Control] Failed to load controller glyph stylesheet: ${url}`,
        );
      };
      target.head.appendChild(link);
    }
  } catch {
    // The next reconciliation covers windows still being constructed.
  }
}

function reconcileControllerGlyphTheme(): void {
  if (!activeTheme) {
    return;
  }
  for (const target of collectDocuments()) {
    managedDocuments.add(target);
    reconcileDocument(target, activeTheme.urls);
  }
}

function ensureReconcileTimer(): void {
  if (reconcileTimer !== undefined) {
    return;
  }
  reconcileTimer = setInterval(
    reconcileControllerGlyphTheme,
    RECONCILE_INTERVAL_MS,
  );
}

export function clearControllerGlyphTheme(): void {
  activeTheme = undefined;
  if (reconcileTimer !== undefined) {
    clearInterval(reconcileTimer);
    reconcileTimer = undefined;
  }

  for (const target of collectDocuments()) {
    managedDocuments.add(target);
  }
  for (const target of managedDocuments) {
    clearDocument(target);
  }
  managedDocuments.clear();
}

export function applyControllerGlyphTheme(
  variant: unknown,
  style: unknown = "Monochrome",
): boolean {
  if (!supportsControllerGlyphVariant(variant)) {
    clearControllerGlyphTheme();
    return false;
  }

  const normalizedStyle = normalizeControllerGlyphStyle(style);
  const urls = getControllerGlyphStylesheets(variant, normalizedStyle).map(
    (stylesheet) => new URL(stylesheet, PLUGIN_THEME_URL).href,
  );
  if (
    activeTheme?.variant === variant &&
    activeTheme.style === normalizedStyle
  ) {
    reconcileControllerGlyphTheme();
    return true;
  }

  for (const target of managedDocuments) {
    clearDocument(target);
  }
  activeTheme = {
    variant,
    style: normalizedStyle,
    urls,
  };
  reconcileControllerGlyphTheme();
  ensureReconcileTimer();
  return true;
}
