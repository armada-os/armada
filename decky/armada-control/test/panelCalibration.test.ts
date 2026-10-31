import assert from "node:assert/strict";
import test from "node:test";
import { elements } from "./helpers/elements.ts";
import { loadModule } from "./helpers/loadModule.ts";

function setup() {
  const slots: any[] = [];
  let cursor = 0;
  const effects: Array<() => void> = [];
  let modal: any;
  let tree: any;
  let closed = 0;
  let live = 100;
  let saveResult = async () => {};
  let stepResult = async () => ({ value: 99, hz: 120.1, limit: null });
  const writes: Array<[string, number]> = [];
  const errors: any[] = [];

  const components = (names: string[]) => Object.fromEntries(names.map((name) => [name, name]));
  const exports = loadModule("components/PanelCalibration.tsx", (id: string) => {
    if (id === "@decky/api") return { toaster: { toast: (error: any) => errors.push(error) } };
    if (id === "@decky/ui") return components(["DialogBody", "DialogButton", "DialogButtonPrimary", "DialogControlsSection", "Focusable"]);
    if (id === "./ArmadaModalRoot") return components(["ArmadaModalRoot", "ArmadaDialogHeader", "ArmadaDialogFooter"]);
    if (id === "./widgets") return components(["ButtonRow", "CompactButton", "ReadOnlyRow"]);
    if (id === "./modalFocusView") return { showArmadaModal: (view: any) => { modal = view; } };
    if (id === "../i18n") return { t: (key: string) => key };
    if (id === "../backend") return {
      getPanelCalibration: async () => { return { supported: true, live: { frame_len_120: live, frame_len_60: null }, defaults: { frame_len_120: 100, frame_len_60: null } }; },
      getPanelRate: async () => ({ hz: 120, attr: "frame_len_120" }),
      calibratePanel: async () => { live = 98; },
      setPanel: async (attr: string, value: number) => { writes.push([attr, value]); live = value; },
      savePanel: () => saveResult(),
      stepPanel: async () => { const result = await stepResult(); live = result.value; return result; },
    };
    if (id === "react") return {
      useState: (initial: any) => {
        const index = cursor++;
        if (!(index in slots)) slots[index] = typeof initial === "function" ? initial() : initial;
        return [slots[index], (next: any) => { slots[index] = typeof next === "function" ? next(slots[index]) : next; }];
      },
      useRef: (initial: any) => {
        const index = cursor++;
        if (!(index in slots)) slots[index] = { current: initial };
        return slots[index];
      },
      useEffect: (effect: () => void) => {
        const index = cursor++;
        if (!(index in slots)) { slots[index] = true; effects.push(effect); }
      },
    };
  });
  const render = () => {
    cursor = 0;
    tree = modal.type({ closeModal: () => { closed++; } });
    for (const effect of effects.splice(0)) effect();
  };
  const control = (type: string, text: string) => elements(tree).find((item) => item.type === type && item.props.children === text)!.props;
  return {
    open: () => { exports.PanelCalibration({ supported: true }).props.onClick(); render(); },
    render, control, writes, errors,
    get tree() { return tree; }, get closed() { return closed; },
    saveResult: (result: () => Promise<void>) => { saveResult = result; },
    stepResult: (result: typeof stepResult) => { stepResult = result; },
    settle: async () => { await new Promise((resolve) => setImmediate(resolve)); render(); },
  };
}

test("cancel waits for an in-flight panel step and restores the opening value before closing", async () => {
  const app = setup();
  app.open();
  await app.settle();
  let release!: (result: { value: number; hz: number; limit: null }) => void;
  app.stepResult(() => new Promise((resolve) => { release = resolve; }));
  app.control("CompactButton", "+").onClick();
  app.render();
  const cancelled = app.tree.props.onCancel();
  assert.equal(app.closed, 0);
  release({ value: 99, hz: 120.1, limit: null });
  await cancelled;
  await app.settle();
  assert.deepEqual(app.writes, [["frame_len_120", 100]]);
  assert.equal(app.closed, 1);
});

test("panel save failures retain the modal and successful retry closes without cancelling", async () => {
  const app = setup();
  app.open();
  await app.settle();
  app.saveResult(async () => { throw new Error("save failed"); });
  app.control("DialogButtonPrimary", "common.save").onClick();
  app.render();
  assert.equal(app.tree.props.bCancelDisabled, true);
  await app.settle();
  assert.equal(app.closed, 0);
  assert.equal(app.errors.length, 1);
  assert.equal(app.control("DialogButtonPrimary", "common.save").disabled, false);
  app.saveResult(async () => {});
  app.control("DialogButtonPrimary", "common.save").onClick();
  await app.settle();
  assert.equal(app.closed, 1);
  assert.deepEqual(app.writes, []);
});
