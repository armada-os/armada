import { routerHook } from "@decky/api";
import type { RoutePatch } from "@decky/api";
import { afterPatch, createReactTreePatcher } from "@decky/ui";
import { Component, createElement, useEffect, useRef, useState } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { HDRBrightnessControl, HDRToggleControl } from "../components/HDR";
import {
  ARMADA_HDR_INJECTION_MARKER,
  DISPLAY_SETTINGS_ROUTE,
  SETTINGS_ROOT_ROUTE,
  findAdvancedDisplayComponent,
  findDisplaySettingsContentComponent,
  injectAdvancedDisplayHdrControls,
} from "./displayHdrInjection";
import { RouteRenderPatchRegistry } from "./displayHdrRoutePatchLifecycle";
import {
  SYSTEM_PERF_STORE_BOOTSTRAP_POLL_MS,
  shouldKeepSystemPerfStoreBootstrap,
} from "./systemPerfStoreBootstrap";

const DIRECT_DISPLAY_ROUTE_PATCH_MARKER = Symbol.for(
  "armada-control.direct-display-hdr-route-patch.v1",
);
const SETTINGS_ROOT_ROUTE_PATCH_MARKER = Symbol.for(
  "armada-control.settings-root-hdr-route-patch.v1",
);

interface InjectionMarkerProps {
  [ARMADA_HDR_INJECTION_MARKER]?: "toggle" | "brightness";
}

interface NativeBrightnessBootstrapProps extends InjectionMarkerProps {
  nativeBrightnessControl?: ReactNode;
}

interface BoundaryState {
  failed: boolean;
}

class HdrControlErrorBoundary extends Component<{ children: ReactNode }, BoundaryState> {
  state: BoundaryState = { failed: false };

  static getDerivedStateFromError(): BoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: unknown, info: ErrorInfo): void {
    console.error("[Armada Control] Display HDR control failed safely", error, info);
  }

  render(): ReactNode {
    return this.state.failed ? null : this.props.children;
  }
}

function SafeNativeHdrToggle(_: InjectionMarkerProps) {
  return (
    <HdrControlErrorBoundary>
      <HDRToggleControl />
    </HdrControlErrorBoundary>
  );
}

function currentSystemPerfStore(): unknown {
  try {
    return typeof window === "undefined" ? undefined : window.SystemPerfStore;
  } catch {
    return undefined;
  }
}

/**
 * Steam creates SystemPerfStore from a hook in its native brightness control.
 * Give that hook one bounded chance to run, then remove the hidden control so
 * its own subscriptions cannot outlive bootstrap.
 */
function NativeSystemPerfStoreBootstrap({ children }: { children: ReactNode }) {
  const startedAtRef = useRef(Date.now());
  const [active, setActive] = useState(() =>
    shouldKeepSystemPerfStoreBootstrap(currentSystemPerfStore(), 0),
  );

  useEffect(() => {
    if (!active) return;

    const refresh = () => {
      const keepMounted = shouldKeepSystemPerfStoreBootstrap(
        currentSystemPerfStore(),
        Date.now() - startedAtRef.current,
      );
      if (!keepMounted) setActive(false);
      return keepMounted;
    };

    // Child effects run before this parent effect. In the normal path Steam's
    // hook has already created the store, so no polling timer is needed.
    if (!refresh()) return;

    const timer = window.setInterval(refresh, SYSTEM_PERF_STORE_BOOTSTRAP_POLL_MS);
    return () => window.clearInterval(timer);
  }, [active]);

  if (!active) return null;
  return (
    <HdrControlErrorBoundary>
      <div aria-hidden="true" style={{ display: "none" }}>
        {children}
      </div>
    </HdrControlErrorBoundary>
  );
}

function SafeNativeHdrBrightness({ nativeBrightnessControl }: NativeBrightnessBootstrapProps) {
  return (
    <>
      {/* Steam creates window.SystemPerfStore lazily inside this native
          component's hook. Mount it only for the bounded bootstrap window. */}
      {nativeBrightnessControl !== undefined && (
        <NativeSystemPerfStoreBootstrap>
          {nativeBrightnessControl}
        </NativeSystemPerfStoreBootstrap>
      )}
      <HdrControlErrorBoundary>
        <HDRBrightnessControl />
      </HdrControlErrorBoundary>
    </>
  );
}

function isPatchableElement(value: unknown): value is { type: Function; props: Record<string, unknown> } {
  if (value === null || typeof value !== "object") return false;
  const element = value as { type?: unknown; props?: unknown };
  return typeof element.type === "function" && element.props !== null && typeof element.props === "object";
}

/**
 * Installs a reversible patch for Steam's exact Display settings route. All
 * nested matching is fail-closed against the current Valve component shape.
 */
export function registerDisplayHdrRoutePatch(): () => void {
  const routeWrapperPatches = new RouteRenderPatchRegistry();
  const warned = new Set<string>();

  const warnOnce = (key: string, message: string, detail?: unknown) => {
    if (warned.has(key)) return;
    warned.add(key);
    console.warn(`[Armada Control] ${message}`, detail ?? "");
  };

  const rootFinder = (key: string) => (tree: unknown) => {
    if (isPatchableElement(tree)) return tree;
    warnOnce(`${key}-root`, "HDR display injection skipped: unexpected route root");
    return undefined;
  };
  const advancedFinder = (key: string) => (tree: unknown) => {
    const advanced = findAdvancedDisplayComponent(tree);
    if (!advanced) {
      warnOnce(
        `${key}-advanced-component`,
        "HDR display injection skipped: Display > Advanced fingerprint did not match",
      );
    }
    return advanced;
  };
  const injectControls = (_args: unknown[], tree: unknown) => {
    try {
      const toggle = createElement(SafeNativeHdrToggle, {
        key: "armada-hdr-toggle",
        [ARMADA_HDR_INJECTION_MARKER]: "toggle",
      });
      const result = injectAdvancedDisplayHdrControls(
        tree,
        toggle,
        (nativeBrightnessControl) => createElement(SafeNativeHdrBrightness, {
          key: "armada-hdr-sdr-brightness",
          nativeBrightnessControl: nativeBrightnessControl as ReactNode,
          [ARMADA_HDR_INJECTION_MARKER]: "brightness",
        }),
      );
      if (result.status === "fingerprint-mismatch" || result.status === "partial-injection") {
        warnOnce(
          `display-advanced-${result.status}`,
          `HDR display injection skipped: ${result.status}`,
        );
      }
      return result.tree;
    } catch (error) {
      warnOnce("display-advanced-error", "HDR display injection failed safely", error);
      return tree;
    }
  };

  // Steam client 1783717985 registers one /settings route and stores Display
  // as a page entry. Keep a separate exact-route strategy for a future split.
  const settingsRootTreePatcher = createReactTreePatcher(
    [
      rootFinder("settings-root"),
      (tree: unknown) => {
        const displayContent = findDisplaySettingsContentComponent(tree);
        if (!displayContent) {
          warnOnce(
            "display-page-content",
            "HDR display injection skipped: exact Display page content fingerprint did not match",
          );
        }
        return displayContent;
      },
      advancedFinder("settings-root"),
    ],
    injectControls,
    "ArmadaSettingsRootDisplayHDR",
  );

  const directDisplayTreePatcher = createReactTreePatcher(
    [rootFinder("direct-display"), advancedFinder("direct-display")],
    injectControls,
    "ArmadaDirectDisplayHDR",
  );

  const createRoutePatch = (
    renderTreePatcher: ReturnType<typeof createReactTreePatcher>,
    routeMarker: symbol,
    key: string,
  ): RoutePatch => (route) => {
    try {
      const child = route.children;
      if (!isPatchableElement(child)) {
        warnOnce(`${key}-child`, "HDR display injection skipped: route child is not patchable");
        return route;
      }
      if ((child.type as unknown as Record<symbol, unknown>)[routeMarker]) return route;

      // React elements can be frozen in development builds, so patch a shallow
      // copy and leave Steam's original route element untouched.
      const patchedChild = { ...child };
      const patch = afterPatch(patchedChild, "type", renderTreePatcher);
      routeWrapperPatches.replace(key, patch, (patchKey, releaseError) => {
        warnOnce(
          `${patchKey}-replace-error`,
          "Could not release an obsolete Display HDR render patch",
          releaseError,
        );
      });
      Object.defineProperty(patchedChild.type, routeMarker, {
        configurable: true,
        value: true,
      });
      return { ...route, children: patchedChild };
    } catch (error) {
      warnOnce(`${key}-error`, "HDR display route patch failed safely", error);
      return route;
    }
  };

  const routePatches: Array<{ path: string; patch: RoutePatch }> = [
    {
      path: DISPLAY_SETTINGS_ROUTE,
      patch: createRoutePatch(
        directDisplayTreePatcher,
        DIRECT_DISPLAY_ROUTE_PATCH_MARKER,
        "direct-display-route",
      ),
    },
    {
      path: SETTINGS_ROOT_ROUTE,
      patch: createRoutePatch(
        settingsRootTreePatcher,
        SETTINGS_ROOT_ROUTE_PATCH_MARKER,
        "settings-root-route",
      ),
    },
  ];
  const registeredPatches: Array<{ path: string; patch: RoutePatch }> = [];
  routePatches.forEach(({ path, patch }) => {
    try {
      registeredPatches.push({ path, patch: routerHook.addPatch(path, patch) });
    } catch (error) {
      console.warn(`[Armada Control] Could not register Display HDR route patch for ${path}`, error);
    }
  });
  if (registeredPatches.length === 0) {
    return () => {};
  }

  let removed = false;
  return () => {
    if (removed) return;
    removed = true;
    registeredPatches.forEach(({ path, patch }) => {
      try {
        routerHook.removePatch(path, patch);
      } catch (error) {
        console.warn(`[Armada Control] Could not remove Display HDR route patch for ${path}`, error);
      }
    });
    routeWrapperPatches.releaseAll((_key, error) => {
      console.warn("[Armada Control] Could not release a Display HDR render patch", error);
    });
  };
}
