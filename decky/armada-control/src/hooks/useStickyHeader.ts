import { classMap, staticClasses } from "@decky/ui";
import { useLayoutEffect } from "react";
import type { RefObject } from "react";
import { bindScrollPadding, findScrollParent, isLastFocusableRegion, revealScrollRegion } from "../lib/scrollRegion";

const fieldSelector = [...new Set(classMap.map((classes) => classes.Field).filter(Boolean))]
  .map((name) => `.${name}`).join(", ");

export function useStickyHeader(root: RefObject<HTMLDivElement | null>, header: RefObject<HTMLDivElement | null>) {
  useLayoutEffect(() => {
    const element = root.current;
    const navigation = header.current;
    const title = element?.closest('[role="tabpanel"]')?.querySelector<HTMLElement>(`.${staticClasses.Title}`);
    if (!element || !navigation) return;
    const host = element.parentElement;
    const scroller = findScrollParent(element);
    const padding = scroller ? bindScrollPadding(scroller) : null;
    // Decky's sticky title has no size token; measure it instead of fixing a height.
    const update = () => {
      const titleHeight = title?.offsetHeight || 0;
      const titleLayer = title ? parseInt(navigation.ownerDocument.defaultView?.getComputedStyle(title).zIndex || "0", 10) || 0 : 0;
      const inset = titleHeight + navigation.offsetHeight;
      // Cancel Decky's content padding so the header owns the gap.
      const contentPadding = host ? navigation.ownerDocument.defaultView?.getComputedStyle(host).paddingBlockStart : undefined;
      element.style.setProperty("--armada-native-content-padding", contentPadding || "0px");
      element.style.setProperty("--armada-native-title-height", `${titleHeight}px`);
      // Keep the native title shadow below the tab surface.
      element.style.setProperty("--armada-tab-header-layer", String(titleLayer + 1));
      element.style.setProperty("--armada-tab-scroll-inset", `${inset}px`);
      // Keep native fallback scrolling clear of the sticky header.
      padding?.set("top", inset);
    };
    update();
    // QAM renders in a different window from the plugin's JavaScript context.
    const Observer = navigation.ownerDocument?.defaultView?.ResizeObserver || ResizeObserver;
    const observer = new Observer(update);
    if (title) observer.observe(title);
    observer.observe(navigation);
    if (host) observer.observe(host, { box: "border-box" });
    return () => {
      observer.disconnect();
      padding?.restore();
      element.style.removeProperty("--armada-native-content-padding");
      element.style.removeProperty("--armada-native-title-height");
      element.style.removeProperty("--armada-tab-header-layer");
      element.style.removeProperty("--armada-tab-scroll-inset");
    };
  }, [root, header]);
  return (target: HTMLElement | undefined) => {
    const element = root.current;
    const navigation = header.current;
    if (!target || !element?.contains(target) || !navigation) return false;
    const scroller = findScrollParent(element);
    if (!scroller) return false;
    if (navigation.contains(target)) {
      scroller.scrollTo({ top: 0, behavior: "instant" });
    } else {
      const field = fieldSelector ? target.closest<HTMLElement>(fieldSelector) : null;
      const region = field && element.contains(field) ? field : target;
      const panel = target.closest<HTMLElement>(".armada-control-tab-content");
      const revealEnd = !!panel && element.contains(panel) && isLastFocusableRegion(panel, region);
      revealScrollRegion(scroller, region, navigation.getBoundingClientRect().bottom, revealEnd);
    }
    return true;
  };
}
