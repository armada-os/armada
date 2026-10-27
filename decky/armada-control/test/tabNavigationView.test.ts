import assert from "node:assert/strict";
import test from "node:test";
import { elements as nodes } from "./helpers/elements.ts";
import { adjacentTab } from "../src/lib/tabNavigation.ts";
import { loadModule } from "./helpers/loadModule.ts";

const buttons = { BUMPER_LEFT: 5, BUMPER_RIGHT: 6, DIR_DOWN: 10 };
function setup(visible = ["games", "profiles", "about"]) {
  let active = visible[0], cursor = 0, tree: any;
  const slots: any[] = [], pending: Array<() => void> = [];
  const effects = new Map<number, { deps: any[]; cleanup?: () => void }>();
  const focus: string[] = [], motion: number[] = [];
  const inside = {}, outside = {};
  const header = { contains: (node: unknown) => node === header };
  const root = { contains: (node: unknown) => node === inside || node === header };
  const tabs = visible.map(id => ({ id, title: id, content: id }));
  const { TabNavigation } = loadModule("components/TabNavigation.tsx", {
    "@decky/ui": { Focusable: "Focusable", GamepadButton: buttons, NavEntryPositionPreferences: { FIRST: 0 } },
    react: {
      useState: (value: any) => { const index = cursor++; if (!(index in slots)) slots[index] = value; return [slots[index], (next: any) => { slots[index] = next; }]; },
      useRef: (value: any) => { const index = cursor++; return slots[index] ||= { current: value }; },
      useLayoutEffect: (effect: () => void, deps: any[]) => {
        const index = cursor++, previous = effects.get(index);
        if (previous && deps.every((value, i) => Object.is(value, previous.deps[i]))) return;
        pending.push(() => { previous?.cleanup?.(); effects.set(index, { deps, cleanup: effect() as any }); });
      },
    },
    "../i18n": { t: (key: string) => key }, "../lib/tabNavigation": { adjacentTab },
    "../lib/modalFocus": { registerModalFocusScope: () => ({ dispose() {} }) },
    "../hooks/useStickyHeader": { useStickyHeader: () => () => true },
    "../hooks/useTabCarouselMotion": { useTabCarouselMotion: () => (direction: number) => motion.push(direction) },
    "./widgets": { CompactButton: "Button" }, "./ControllerButtonHint": { ControllerButtonHint: "Hint" },
  });
  function render() {
    cursor = 0;
    tree = TabNavigation({ tabs, activeTab: active, onShowTab: (id: string) => { active = id; } });
    for (const node of nodes(tree).filter(node => node.type === "Focusable")) {
      const name = node.props.role === "navigation" ? "header" : node.props["aria-label"];
      if (node.props.ref) node.props.ref.current = name === "header" ? header : root;
      if (node.props.navRef) node.props.navRef.current = { TakeFocus: () => { focus.push(name); return true; }, BFocusWithin: () => false };
    }
    pending.splice(0).forEach(effect => effect());
  }
  render();
  return {
    render, focus, motion, get active() { return active; }, nodes: () => nodes(tree),
    header: () => nodes(tree).find(node => node.props?.role === "navigation").props,
    press(button: number, origin = "panel", prevented = false) {
      let consumed = false;
      tree.props.onButtonDown({ target: origin === "modal" ? outside : origin === "header" ? header : inside, detail: { button }, defaultPrevented: prevented,
        preventDefault: () => { consumed = true; }, stopPropagation() {} });
      render();
      return consumed;
    },
  };
}

test("bumper navigation wraps the available tabs, enters the active panel and ignores modal input", () => {
  const app = setup();
  assert.equal(app.press(buttons.BUMPER_LEFT), true);
  assert.equal(app.active, "about");
  assert.equal(app.press(buttons.BUMPER_RIGHT), true);
  assert.equal(app.active, "games");
  app.press(buttons.BUMPER_RIGHT);
  assert.equal(app.active, "profiles");
  assert.deepEqual(app.focus, ["about", "games", "profiles"]);
  assert.equal(app.nodes().filter(node => node.props?.role === "tabpanel").length, 1);
  const hints = app.nodes()[0].props.actionDescriptionMap;
  assert.equal(hints[buttons.BUMPER_RIGHT], "about");
  assert.equal(app.press(buttons.BUMPER_RIGHT, "modal"), false);
  assert.equal(app.press(buttons.BUMPER_RIGHT, "panel", true), false);
  assert.equal(app.press(buttons.DIR_DOWN), false);
  assert.equal(app.active, "profiles");
});

test("header arrows and bumpers preserve header focus until Down or activation enters its panel", () => {
  const app = setup();
  app.header().onMoveLeft();
  app.render();
  assert.equal(app.active, "about");
  app.press(buttons.BUMPER_RIGHT, "header");
  assert.equal(app.active, "games");
  assert.deepEqual(app.focus, []);
  app.header().onMoveRight();
  app.render();
  assert.equal(app.header().onMoveDown(), true);
  const panel = app.nodes().find(node => node.props?.role === "tabpanel");
  assert.equal(panel.props.focusableIfEmpty, true);
  app.nodes().find(node => node.props?.className === "armada-tab-selected").props.onClick();
  assert.deepEqual(app.focus, ["profiles", "profiles"]);
});
