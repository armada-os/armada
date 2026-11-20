import assert from "node:assert/strict";
import test from "node:test";
import type { TestContext } from "node:test";
import { captureModalFocus, registerModalFocusScope } from "../src/lib/modalFocus.ts";

function windowScopes(t: TestContext) {
  const frames: FrameRequestCallback[] = [];
  const document = { activeElement: null, defaultView: { requestAnimationFrame: (fn: FrameRequestCallback) => frames.push(fn) } } as unknown as Document;
  const calls: string[] = [];
  const focused = new Map<HTMLElement, boolean>();
  const scope = (name: string, modal = false, parent?: ReturnType<typeof captureModalFocus>) => {
    const node = { ownerDocument: document, isConnected: true, getClientRects: () => [{}], contains: () => false } as unknown as HTMLElement;
    const focus = () => { for (const element of focused.keys()) focused.set(element, element === node); };
    focused.set(node, false);
    const handle = registerModalFocusScope(node, () => { calls.push(name); focus(); return true; }, () => focused.get(node) || false, modal, parent);
    t.after(handle.dispose);
    return { ...handle, node, focus, deactivate: () => focused.set(node, false) };
  };
  return { scope, calls, flush: () => frames.splice(0).forEach((fn) => fn(0)) };
}

test("closing an editor after native dropdown navigation returns across Steam windows", (t) => {
  const qam = windowScopes(t), main = windowScopes(t);
  const panel = qam.scope("panel");
  panel.focus();
  const source = captureModalFocus();
  panel.deactivate();
  const editor = main.scope("editor", true, source);
  editor.focus();
  editor.deactivate();
  editor.dispose();
  main.flush();
  assert.deepEqual(qam.calls, []);
  qam.flush();
  assert.deepEqual(qam.calls, ["panel"]);
});

test("nested and chained confirmations return to the surviving opener", (t) => {
  const qam = windowScopes(t), main = windowScopes(t);
  const panel = qam.scope("panel");
  panel.focus();
  const source = captureModalFocus();
  panel.deactivate();
  const editor = main.scope("editor", true, source);
  editor.focus();
  const confirmation = main.scope("confirmation", true, captureModalFocus());
  editor.deactivate();
  confirmation.dispose();
  main.flush();
  assert.deepEqual(main.calls, ["editor"]);
  const editorSource = captureModalFocus();
  editor.dispose();
  const next = main.scope("next", true, editorSource);
  qam.flush();
  assert.deepEqual(qam.calls, []);
  next.dispose();
  qam.flush();
  assert.deepEqual(qam.calls, ["panel"]);
});

test("delayed restoration cannot steal focus from a newer dialog in the returning window", (t) => {
  const qam = windowScopes(t), main = windowScopes(t);
  const panel = qam.scope("panel");
  panel.focus();
  const source = captureModalFocus();
  panel.deactivate();
  main.scope("editor", true, source).dispose();
  const newer = qam.scope("newer", true, source);
  newer.focus();
  qam.flush();
  assert.deepEqual(qam.calls, []);
  newer.dispose();
  qam.flush();
  assert.deepEqual(qam.calls, ["panel"]);
});

test("native restoration is respected and closing the panel cancels a pending fallback", (t) => {
  const app = windowScopes(t);
  const panel = app.scope("panel");
  const first = app.scope("first", true);
  first.dispose();
  panel.focus();
  app.flush();
  assert.deepEqual(app.calls, []);
  app.scope("second", true).dispose();
  panel.dispose();
  app.flush();
  assert.deepEqual(app.calls, []);
});
