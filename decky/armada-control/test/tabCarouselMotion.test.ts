import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./helpers/loadModule.ts";
import * as motion from "../src/lib/tabCarouselMotion.ts";
import type { MotionRect } from "../src/lib/tabCarouselMotion.ts";

function setup() {
  const lineHeight = 22;
  const hooks: any[] = [];
  const effects = new Map<number, { dependencies: any[]; cleanup?: () => void }>();
  let cursor = 0;
  let pending: Array<() => void> = [];
  const animated: any[] = [];
  let resize!: () => void;
  const media = {
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  };
  const attributes = new Set<string>();
  const window = {
    getComputedStyle: (node: any) => ({ ...node.computed, ...node.visualStyle }),
    matchMedia: () => media,
    ResizeObserver: class { constructor(callback: () => void) { resize = callback; } observe() {} disconnect() {} },
  };
  function node(rect: MotionRect, kind: string) {
    const result: any = {
      rect, visual: null, visualStyle: {}, kind,
      dataset: {}, classList: { contains: (name: string) => kind === "ghost" && name === "armada-tab-ghost" },
      computed: { opacity: "1", color: "rgb(255, 255, 255)", backgroundColor: "transparent", clipPath: "none" },
      get offsetWidth() { return result.rect.width; },
      get offsetHeight() { return result.rect.height; },
      getBoundingClientRect: () => {
        const current = result.visual || result.rect;
        return { left: 100 + current.left, top: 80 + current.top, width: current.width, height: current.height };
      },
      animate: (frames: any[], options: any) => {
        const { promise: finished, reject } = Promise.withResolvers<void>();
        const animation: any = {
          node: result, frames, options, cancelled: false,
          finished,
          cancel: () => { animation.cancelled = true; result.visual = null; result.visualStyle = {}; reject(new Error("cancelled")); },
        };
        animated.push(animation);
        return animation;
      },
    };
    return result;
  }
  const header: any = node({ left: 0, top: 0, width: 300, height: 48 }, "header");
  header.ownerDocument = { defaultView: window };
  header.computed = { animationDuration: "0.35s", animationTimingFunction: "ease-in-out" };
  header.hasAttribute = (name: string) => attributes.has(name);
  header.setAttribute = (name: string) => attributes.add(name);
  header.removeAttribute = (name: string) => attributes.delete(name);
  function view(id: string, left: number, width: number, selected = false, ghost = false) {
    const height = selected ? lineHeight + 8 : 26;
    const shell = node({ left, top: 23 - height / 2, width, height }, ghost ? "ghost" : "button");
    shell.dataset.tabId = id;
    shell.computed.backgroundColor = selected ? "rgb(50, 50, 50)" : "transparent";
    const surface = node({ ...shell.rect }, "surface");
    const radius = `${height / 2}px`;
    const previous = !selected && !ghost && left < header.rect.width / 2;
    const next = !selected && !ghost && left > header.rect.width / 2;
    const corners = {
      borderTopLeftRadius: previous ? "0px" : radius,
      borderTopRightRadius: next ? "0px" : radius,
      borderBottomRightRadius: next ? "0px" : radius,
      borderBottomLeftRadius: previous ? "0px" : radius,
    };
    Object.assign(shell.computed, corners);
    Object.assign(surface.computed, corners);
    const icon = node({ left: left + (selected ? 8 : 4), top: 14, width: 18, height: 18 }, "icon");
    const label = node({ left: selected ? left + 30 : left + width, top: 23 - lineHeight / 2, width: selected ? width - 38 : 0, height: lineHeight }, "label");
    label.computed.opacity = selected ? "1" : "0";
    return { shell, surface, icon, label };
  }
  const views = { current: {
    previous: view("about", 43, 26), current: view("games", 70, 160, true), next: view("profiles", 231, 26),
    ghost: { shell: null, surface: null, icon: null, label: null } as any,
  } };
  const left = { current: node({ left: 16, top: 11, width: 24, height: 24 }, "edge") };
  const right = { current: node({ left: 260, top: 11, width: 24, height: 24 }, "edge") };

  const exports = loadModule("hooks/useTabCarouselMotion.ts", (id: string) => {
    if (id === "../lib/tabCarouselMotion") return motion;
    if (id === "react") return {
      useRef: (initial: any) => {
        const index = cursor++;
        if (!(index in hooks)) hooks[index] = { current: initial };
        return hooks[index];
      },
      useLayoutEffect: (callback: () => (() => void) | undefined, dependencies: any[]) => {
        const index = cursor++;
        const previous = effects.get(index);
        if (previous && dependencies.every((value, i) => Object.is(value, previous.dependencies[i]))) return;
        pending.push(() => {
          previous?.cleanup?.();
          effects.set(index, { dependencies, cleanup: callback() });
        });
      },
    };
  });
  let prepare!: (direction: number, target: string) => void;
  function render(active: string, labels = "labels") {
    cursor = 0;
    prepare = exports.useTabCarouselMotion({ current: header }, views, left, right, active, labels);
    const callbacks = pending;
    pending = [];
    callbacks.forEach((callback) => callback());
  }
  function advance() {
    prepare(1, "profiles");
    views.current = {
      previous: view("games", 43, 26), current: view("profiles", 95, 110, true), next: view("rgb", 231, 26), ghost: view("about", 0, 26, false, true),
    };
    render("profiles");
  }
  render("games");
  return {
    animated, views, header, media, render, advance, resize: () => resize(),
    prepare: (direction: number, target: string) => prepare(direction, target), view,
    unmount: () => { for (const effect of effects.values()) effect.cleanup?.(); },
  };
}

test("rapid reversal captures in-flight shapes and restores the departing tab from its moving ghost", () => {
  const app = setup();
  app.advance();
  const oldAnimations = [...app.animated];
  const moving = app.views.current.previous;
  moving.surface.visual = { left: 59, top: 9, width: 93, height: 28 };
  moving.surface.visualStyle = {
    borderTopLeftRadius: "7px", borderTopRightRadius: "16px",
    borderBottomRightRadius: "15px", borderBottomLeftRadius: "6px",
  };
  moving.icon.visual = { left: 66, top: 14, width: 18, height: 18 };
  moving.label.visual = { left: 87, top: 12, width: 60, height: 22 };
  moving.label.visualStyle = { opacity: ".5" };
  app.views.current.ghost.surface.visual = { left: 28, top: 10, width: 26, height: 26 };
  app.prepare(-1, "games");
  app.views.current = {
    previous: app.view("about", 43, 26), current: app.view("games", 70, 160, true), next: app.view("profiles", 231, 26), ghost: app.view("rgb", 0, 26, false, true),
  };
  app.render("games");
  const currentSurface = app.animated.slice(oldAnimations.length).filter((entry) => entry.node.kind === "surface")[1];
  assert.equal(currentSurface.frames[0].width, "93px");
  assert.equal(currentSurface.frames[0].transform, "translate(-11px, 1px)");
  assert.equal(currentSurface.frames[0].borderTopLeftRadius, "7px");
  assert.equal(currentSurface.frames[0].borderTopRightRadius, "16px");
  assert.equal(currentSurface.frames[0].borderBottomRightRadius, "15px");
  assert.equal(currentSurface.frames[0].borderBottomLeftRadius, "6px");
  const previousSurface = app.animated.slice(oldAnimations.length).filter((entry) => entry.node.kind === "surface")[0];
  assert.equal(previousSurface.frames[0].transform, "translate(-15px, 0px)");
  assert.ok(oldAnimations.every((entry) => entry.cancelled));
  app.unmount();
});

test("reduced motion, locale changes and responsive layout changes settle without delaying tab content", () => {
  const app = setup();
  app.media.matches = true;
  app.advance();
  assert.equal(app.animated.length, 0);
  assert.equal(app.header.hasAttribute("data-moving"), false);
  app.media.matches = false;
  app.prepare(-1, "games");
  app.render("games");
  assert.equal(app.header.hasAttribute("data-moving"), true);
  app.render("games", "Config. de jogos|Perfis|RGB");
  assert.equal(app.header.hasAttribute("data-moving"), false);
  app.prepare(1, "profiles");
  app.render("profiles", "Config. de jogos|Perfis|RGB");
  app.views.current.current.shell.rect.width = 140;
  app.resize();
  assert.equal(app.header.hasAttribute("data-moving"), false);
  app.unmount();
});
