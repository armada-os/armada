import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./helpers/loadModule.ts";
import { findScrollParent } from "../src/lib/scrollRegion.ts";

const property = "--armada-panel-available-height";

function setup({ scale = 1, scrollTop = 0, tab = false } = {}) {
  const values = new Map<string, string>([["color", "white"]]);
  const observers: Array<{ disconnected: boolean; resize: () => void }> = [];
  const document: any = { body: {}, documentElement: {} };
  document.defaultView = {
    getComputedStyle: (element: any) => element.computed,
    ResizeObserver: class {
      disconnected = false;
      resize: () => void;
      constructor(resize: () => void) { this.resize = resize; observers.push(this); }
      observe() {}
      disconnect() { this.disconnected = true; }
    },
  };
  const layout = { offset: 48, titleInset: 32, scale };
  const scroller: any = {
    ownerDocument: document, parentElement: document.body,
    computed: { overflowY: "auto" },
    clientHeight: 500, offsetHeight: 504, clientTop: 2, scrollTop,
    getBoundingClientRect: () => ({ top: 20, height: scroller.offsetHeight * layout.scale }),
  };
  const title = {
    getBoundingClientRect: () => ({ bottom: 20 + (layout.titleInset + scroller.clientTop) * layout.scale }),
  };
  const navigation = { offsetHeight: 64, closest: () => ({ querySelector: () => title }) };
  const tabs = {
    ownerDocument: document, parentElement: scroller, computed: { overflowY: "visible" },
    querySelector: () => navigation,
  };
  const wrapper: any = {
    ownerDocument: document, parentElement: tab ? tabs : scroller, computed: { overflowY: "visible", paddingBlockStart: tab ? "16px" : "0px" },
  };
  const root: any = {
    ownerDocument: document, parentElement: wrapper,
    closest: () => tab ? tabs : null,
    getBoundingClientRect: () => ({
      top: 20 + (layout.offset - scroller.scrollTop + scroller.clientTop) * layout.scale,
    }),
    style: {
      setProperty: (key: string, value: string) => { values.set(key, value); },
      removeProperty: (key: string) => { values.delete(key); },
    },
  };
  let cleanup: (() => void) | undefined;

  const exports = loadModule("hooks/usePanelHeight.ts", (id: string) => {
    if (id === "@decky/ui") return { staticClasses: { Title: "native-title" } };
    if (id === "react") return { useLayoutEffect: (effect: () => (() => void) | undefined) => { cleanup = effect(); } };
    if (id === "../lib/scrollRegion") return { findScrollParent };
  });
  exports.usePanelHeight({ current: root });
  return { values, observers, layout, scroller, navigation, cleanup: () => cleanup?.() };
}

test("standalone loading height follows native viewport resize and cleans up its measurement", () => {
  const panel = setup({ scale: 1.5, scrollTop: 120 });
  assert.equal(panel.values.get(property), "452px");
  panel.scroller.clientHeight = 620;
  panel.observers[0].resize();
  assert.equal(panel.values.get(property), "572px");
  panel.cleanup();
  assert.equal(panel.observers[0].disconnected, true);
  assert.equal(panel.values.has(property), false);
  assert.equal(panel.values.get("color"), "white");
});

test("tab loading height stays stationary while scrolling and responds to header resizing", () => {
  const panel = setup({ tab: true, scale: 1.5 });
  assert.equal(panel.values.get(property), "388px");
  panel.layout.offset = 320;
  panel.scroller.scrollTop = 240;
  panel.observers[0].resize();
  assert.equal(panel.values.get(property), "388px");
  panel.navigation.offsetHeight = 80;
  panel.scroller.clientHeight = 620;
  panel.observers[0].resize();
  assert.equal(panel.values.get(property), "492px");
  panel.cleanup();
});
