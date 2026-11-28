import assert from "node:assert/strict";
import test from "node:test";
import * as scrollRegion from "../src/lib/scrollRegion.ts";

import { loadModule } from "./helpers/loadModule.ts";

const { revealModalFocus, revealModalStart } = loadModule("lib/modalScroll.ts", { "./scrollRegion": scrollRegion });

class TestElement {
  parentElement: TestElement | null;
  children: TestElement[] = [];
  ownerDocument: any;
  classes: Set<string>;
  overflowY: string;
  top: number;
  scale: number;
  clientHeight: number;
  clientTop = 0;
  offsetHeight: number;
  scrollHeight = 1600;
  scrollTop = 0;
  pendingAnimation: number | undefined;
  calls: ScrollToOptions[] = [];

  constructor(document: any, options: { parent?: TestElement; className?: string; top?: number; height?: number; overflow?: string; scale?: number } = {}) {
    this.ownerDocument = document;
    this.parentElement = options.parent || null;
    this.parentElement?.children.push(this);
    this.classes = new Set((options.className || "").split(" "));
    this.overflowY = options.overflow || "visible";
    this.top = options.top || 0;
    this.scale = options.scale || this.parentElement?.scale || 1;
    this.clientHeight = options.height || 80;
    this.offsetHeight = this.clientHeight;
  }

  matches(selector: string) {
    return selector.split(",").some((value) => value.trim() === "*" || this.classes.has(value.trim().slice(1)));
  }

  closest(selector: string): TestElement | null {
    for (let element: TestElement | null = this; element; element = element.parentElement) {
      if (element.matches(selector)) return element;
    }
    return null;
  }

  contains(target: TestElement) {
    for (let element: TestElement | null = target; element; element = element.parentElement) {
      if (element === this) return true;
    }
    return false;
  }

  querySelectorAll(selector: string): TestElement[] {
    return this.children.flatMap((child) => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]);
  }

  getBoundingClientRect() {
    let offset = 0;
    for (let element = this.parentElement; element; element = element.parentElement) offset += element.scrollTop;
    const top = 20 + (this.top - offset) * this.scale;
    return { top, bottom: top + this.clientHeight * this.scale, height: this.clientHeight * this.scale };
  }

  scrollTo(options: ScrollToOptions) {
    this.calls.push({ ...options });
    this.scrollTop = Math.max(0, options.top || 0);
    if (options.behavior === "instant") this.pendingAnimation = undefined;
  }
}

function setup(scale = 1) {
  const document: any = {
    body: {}, documentElement: {},
    defaultView: { getComputedStyle: (element: TestElement) => ({ overflowY: element.overflowY }) },
  };
  const outside = new TestElement(document, { height: 800, overflow: "auto", scale });
  const modal = new TestElement(document, { parent: outside, className: "armada-control-dialog", height: 400, overflow: "auto" });
  const boundary = new TestElement(document, { parent: modal });
  const add = (options: ConstructorParameters<typeof TestElement>[1] = {}) => new TestElement(document, { parent: boundary, ...options });
  return { document, outside, modal, boundary, add };
}

function reveal(boundary: TestElement | null, target: TestElement | undefined, fieldSelector = ".native-field") {
  return revealModalFocus(boundary as unknown as HTMLElement | null, target as unknown as HTMLElement | undefined, fieldSelector);
}

function start(target: TestElement | null) {
  return revealModalStart(target as unknown as HTMLElement | null);
}

test("rapid modal navigation reveals whole labels and cancels the previous scroll", () => {
  const { modal, boundary, outside, add } = setup(1.5);
  const last = add({ className: "native-field", top: 600, height: 100 });
  const input = add({ parent: last, top: 640, height: 20 });
  reveal(boundary, input);
  assert.equal(last.getBoundingClientRect().bottom, modal.getBoundingClientRect().bottom);
  modal.pendingAnimation = 600;
  const first = add({ className: "native-field", top: 80, height: 100 });
  reveal(boundary, first);
  assert.equal(first.getBoundingClientRect().top, modal.getBoundingClientRect().top);
  assert.equal(modal.pendingAnimation, undefined);
  assert.deepEqual(outside.calls, []);
});

test("nested modal scrolling stays inside the active dialog", () => {
  const { document, outside } = setup();
  const position = new TestElement(document, { parent: outside, className: "armada-control-dialog-position", height: 300, overflow: "auto" });
  const modal = new TestElement(document, { parent: position, className: "armada-control-dialog" });
  const boundary = new TestElement(document, { parent: modal });
  const body = new TestElement(document, { parent: boundary, height: 300, overflow: "auto" });
  const field = new TestElement(document, { parent: body, className: "native-field", top: 600, height: 60 });
  assert.equal(reveal(boundary, field), true);
  assert.ok(body.scrollTop > 0);
  assert.deepEqual(position.calls, []);
  assert.equal(start(boundary), true);
  assert.equal(body.scrollTop, 0);
  assert.deepEqual(position.calls, []);
});

test("footer focus does not scroll the modal position", () => {
  const { document, outside } = setup();
  const position = new TestElement(document, { parent: outside, className: "armada-control-dialog-position", height: 400, overflow: "auto" });
  const modal = new TestElement(document, { parent: position, className: "armada-control-dialog", height: 400 });
  const boundary = new TestElement(document, { parent: modal });
  const footer = new TestElement(document, { parent: boundary, className: "armada-control-dialog-footer", top: 350, height: 40 });
  assert.equal(reveal(boundary, footer), true);
  assert.deepEqual(position.calls, []);
});

test("panel scrolling reveals trailing space without hiding an oversized field's label", () => {
  const { modal, add } = setup(1.5);
  modal.scrollHeight = 738;
  const last = add({ top: 600 });
  scrollRegion.revealScrollRegion(modal as any, last as any, 140, true);
  assert.equal(modal.scrollTop, modal.scrollHeight - modal.clientHeight);
  assert.ok(last.getBoundingClientRect().top >= 140);
  const oversized = add({ top: 500, height: 500 });
  scrollRegion.revealScrollRegion(modal as any, oversized as any, 140, true);
  assert.equal(oversized.getBoundingClientRect().top, 140);
});

test("native scroll ownership and responsive padding survive updates and cleanup", () => {
  const { document, modal, boundary } = setup();
  assert.equal(scrollRegion.findScrollParent(boundary as any), modal);
  assert.equal(scrollRegion.findScrollParent({ ownerDocument: document, parentElement: document.body } as any), null);
  const values = new Map<string, string>();
  const element: any = {
    ownerDocument: { defaultView: { getComputedStyle: () => ({ scrollPaddingTop: "calc(10% + 2px)", scrollPaddingBottom: "16px" }) } },
    style: { getPropertyValue: (key: string) => values.get(key) || "", getPropertyPriority: () => "",
      setProperty: (key: string, value: string) => values.set(key, value), removeProperty: (key: string) => values.delete(key) },
  };
  const padding = scrollRegion.bindScrollPadding(element);
  padding.set("top", 48);
  padding.set("top", 60);
  assert.equal(values.get("scroll-padding-top"), "max(calc(10% + 2px), 60px)");
  padding.restore();
  assert.equal(values.size, 0);
  const next = scrollRegion.bindScrollPadding(element);
  next.set("top", 48);
  element.style.setProperty("scroll-padding-top", "72px");
  next.restore();
  assert.equal(values.get("scroll-padding-top"), "72px");
});
