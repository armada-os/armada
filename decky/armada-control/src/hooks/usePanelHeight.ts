import { staticClasses } from "@decky/ui";
import { useLayoutEffect } from "react";
import type { RefObject } from "react";
import { findScrollParent } from "../lib/scrollRegion";

export function usePanelHeight(root: RefObject<HTMLElement | null>) {
  useLayoutEffect(() => {
    const element = root.current;
    const scroller = element && findScrollParent(element);
    if (!element || !scroller) return;
    const view = element.ownerDocument.defaultView;
    const tabs = element.closest(".armada-control-tabs");
    const navigation = tabs?.querySelector<HTMLElement>(".armada-tab-navigation");
    const title = navigation?.closest('[role="tabpanel"]')?.querySelector<HTMLElement>(`.${staticClasses.Title}`);
    const update = () => {
      const viewport = scroller.getBoundingClientRect();
      const scale = (scroller.offsetHeight ? viewport.height / scroller.offsetHeight : 1) || 1;
      let start: number;
      // Native padding and focus can move the loading element during setup.
      if (tabs && navigation && title) {
        start = (title.getBoundingClientRect().bottom - viewport.top) / scale - scroller.clientTop + navigation.offsetHeight;
        for (let parent = element.parentElement; parent && parent !== tabs; parent = parent.parentElement) {
          start += parseFloat(view?.getComputedStyle(parent).paddingBlockStart || "0") || 0;
        }
      } else {
        start = (element.getBoundingClientRect().top - viewport.top) / scale + scroller.scrollTop - scroller.clientTop;
      }
      const height = Math.max(0, scroller.clientHeight - start);
      element.style.setProperty("--armada-panel-available-height", `${height}px`);
    };
    update();
    const Observer = view?.ResizeObserver || ResizeObserver;
    const observer = new Observer(update);
    for (let parent = element.parentElement; parent; parent = parent.parentElement) {
      observer.observe(parent);
      if (parent === scroller) break;
    }
    if (title) observer.observe(title);
    if (navigation) observer.observe(navigation);
    return () => {
      observer.disconnect();
      element.style.removeProperty("--armada-panel-available-height");
    };
  }, [root]);
}
