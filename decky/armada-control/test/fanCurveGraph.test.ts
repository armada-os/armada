import assert from "node:assert/strict";
import test from "node:test";
import { elements } from "./helpers/elements.ts";
import { loadModule } from "./helpers/loadModule.ts";
import * as fanCurve from "../src/lib/fanCurve.ts";
import { clamp } from "../src/lib/util.ts";

const GamepadButton = { BUMPER_LEFT: 5, BUMPER_RIGHT: 6, DIR_UP: 9, DIR_DOWN: 10, DIR_LEFT: 11, DIR_RIGHT: 12 };

function setup() {
  let disabled = false;
  let points = [{ temp: 40, pwm: 50 }, { temp: 70, pwm: 100 }];
  const writes: typeof points[] = [];
  const slots: any[] = [];
  let cursor = 0;
  let dirty = false;
  let pendingEffects: Array<() => void> = [];
  let tree: any;
  const svg = { getBoundingClientRect: () => ({ left: 0, top: 0, width: 280, height: 170 }) };
  const react = {
    useRef: (value: any) => {
      const index = cursor++;
      slots[index] ??= { current: value };
      return slots[index];
    },
    useState: (value: any) => {
      const index = cursor++;
      if (!(index in slots)) slots[index] = value;
      return [slots[index], (next: any) => {
        const value = typeof next === "function" ? next(slots[index]) : next;
        if (!Object.is(slots[index], value)) { slots[index] = value; dirty = true; }
      }];
    },
    useMemo: (callback: () => any) => { cursor++; return callback(); },
    useEffect: (callback: () => void, dependencies: any[]) => {
      const index = cursor++;
      if (slots[index] && dependencies.every((value, i) => Object.is(value, slots[index][i]))) return;
      slots[index] = dependencies;
      pendingEffects.push(callback);
    },
  };

  const exports = loadModule("components/FanCurveGraph.tsx", (id: string) => {
    if (id === "react") return react;
    if (id === "@decky/ui") return { Focusable: "Focusable", GamepadButton };
    if (id === "../i18n") return { t: (key: string) => key };
    if (id === "../lib/fanCurve") return fanCurve;
    if (id === "../lib/util") return { clamp };
  });
  function render() {
    do {
      dirty = false;
      cursor = 0;
      tree = exports.FanCurveGraph({ points, disabled, onChange: (next: typeof points) => { writes.push(next); points = next; } });
      elements(tree).find((element) => element.type === "svg").props.ref.current = svg;
      const effects = pendingEffects;
      pendingEffects = [];
      effects.forEach((callback) => callback());
    } while (dirty);
  }
  render();
  return {
    render, writes,
    setPoints: (next: typeof points) => { points = next; render(); },
    root: () => tree.props,
    circles: () => elements(tree).filter((element) => element.props?.className === "armada-fan-graph-hit-target"),
    disable: (value: boolean) => { disabled = value; render(); },
  };
}

function button(button: number) {
  const event = { detail: { button }, prevented: false, stopped: false, preventDefault() { this.prevented = true; }, stopPropagation() { this.stopped = true; } };
  return event;
}

function pointer() {
  let captured = false;
  let captures = 0;
  let releases = 0;
  return {
    currentTarget: {
      setPointerCapture: () => { captured = true; captures++; },
      hasPointerCapture: () => captured,
      releasePointerCapture: () => { captured = false; releases++; },
    },
    pointerId: 1, clientX: 150, clientY: 70,
    captures: () => captures, releases: () => releases,
  };
}

test("controller editing contains input, respects neighboring points and exits cleanly", () => {
  const app = setup();
  app.setPoints([{ temp: 40, pwm: 0 }, { temp: 40, pwm: 100 }, { temp: 90, pwm: 255 }]);
  app.root().onOKButton();
  app.render();
  const up = button(GamepadButton.DIR_UP);
  app.root().onGamepadDirection(up);
  app.render();
  assert.equal(up.prevented && up.stopped, true);
  assert.deepEqual({ ...app.writes.at(-1)![0] }, { temp: 40, pwm: 5 });
  app.root().onGamepadDirection(button(GamepadButton.DIR_RIGHT));
  assert.equal(app.writes.length, 1);
  const next = button(GamepadButton.BUMPER_RIGHT);
  app.root().onButtonDown(next);
  app.render();
  assert.equal(next.prevented && next.stopped, true);
  app.root().onGamepadDirection(button(GamepadButton.DIR_DOWN));
  assert.deepEqual({ ...app.writes.at(-1)![1] }, { temp: 40, pwm: 95 });
  app.root().onCancelButton(button(2));
  app.render();
  assert.equal(app.root().onGamepadDirection, undefined);
});

test("pointer drafts commit on release and cancellation never writes the draft", () => {
  const app = setup();
  const committed = pointer();
  app.circles()[0].props.onPointerDown(committed);
  app.circles()[0].props.onPointerMove(committed);
  assert.equal(app.writes.length, 0);
  app.circles()[0].props.onPointerUp(committed);
  assert.equal(committed.releases(), 1);
  assert.notEqual(app.writes[0][0].temp, 40);
  const cancelled = pointer();
  app.circles()[0].props.onPointerDown(cancelled);
  app.circles()[0].props.onPointerMove(cancelled);
  app.circles()[0].props.onPointerCancel(cancelled);
  assert.equal(cancelled.releases(), 1);
  assert.equal(app.writes.length, 1);
  app.disable(true);
  app.circles()[0].props.onPointerDown(pointer());
  app.root().onOKButton();
  app.render();
  assert.equal(app.root().onGamepadDirection, undefined);
});

test("interrupted pointer edits release capture instead of replacing the current curve", () => {
  for (const interrupt of [
    (app: ReturnType<typeof setup>) => app.disable(true),
    (app: ReturnType<typeof setup>) => app.setPoints([{ temp: 35, pwm: 0 }, { temp: 70, pwm: 130 }]),
  ]) {
    const app = setup();
    const event = pointer();
    app.circles()[0].props.onPointerDown(event);
    app.circles()[0].props.onPointerMove(event);
    interrupt(app);
    app.circles()[0].props.onPointerUp(event);
    assert.equal(event.releases(), 1);
    assert.equal(app.writes.length, 0);
  }
});
