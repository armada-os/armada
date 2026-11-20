import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./helpers/loadModule.ts";

const modal = loadModule("components/ArmadaModalRoot.tsx", {
  "@decky/ui": { classMap: [], DialogBody: "Body", DialogButton: "Cancel", DialogButtonPrimary: "Confirm" },
  react: {}, "./modalFocusView": {}, "../lib/modalFocus": {}, "../lib/modalScroll": {}, "./ArmadaStyles": {},
});

test("confirmation buttons, native submit and Back each invoke only their intended action", () => {
  const calls: string[] = [];
  const root = modal.ArmadaConfirmModal({ onConfirm: () => calls.push("confirm"), closeModal: () => calls.push("close") });
  const [confirm, cancel] = root.props.children[2].props.children;
  confirm.props.onClick();
  assert.deepEqual(calls, ["confirm", "close"]);
  calls.length = 0;
  cancel.props.onClick();
  root.props.onCancel();
  assert.deepEqual(calls, ["close", "close"]);
  calls.length = 0;
  root.props.onOK();
  root.props.closeModal();
  assert.deepEqual(calls, ["confirm", "close"]);
  const closeFirst = modal.ArmadaConfirmModal({ onConfirm: () => calls.push("confirm"), closeModal: () => calls.push("close"), closeBeforeConfirm: true });
  for (const confirm of [closeFirst.props.children[2].props.children[0].props.onClick, closeFirst.props.onOK]) {
    calls.length = 0;
    confirm();
    assert.deepEqual(calls, ["close", "confirm"]);
  }
  assert.equal(closeFirst.props.closeModal, undefined);
});

test("shared modal opening captures its source before Steam moves focus and forwards native dismissal", () => {
  let active: unknown = { window: "QuickAccess" };
  const sourceScope = active;
  const calls: any[] = [];
  const context: any = { Provider: "ReturnFocusProvider" };
  const nativeResult = { Close: () => {}, Update: () => {} };
  const api = loadModule("components/modalFocusView.tsx", {
    "@decky/ui": { showModal: (...args: any[]) => { calls.push(args); active = { window: "Steam" }; return nativeResult; } },
    "../lib/modalFocus": { captureModalFocus: () => active },
    react: { createContext: () => context, useContext: (value: any) => value.current,
      cloneElement: (view: any, props: any) => ({ ...view, props: { ...view.props, ...props } }) },
  });
  const originalClose = () => {};
  const view = { type: "EnvVarModal", props: { initialKey: "", closeModal: originalClose } };
  const parent = {};
  const options = { bNeverPopOut: true };
  assert.equal(api.showArmadaModal(view, parent, options), nativeResult);
  const [wrapper, forwardedParent, forwardedOptions] = calls[0];
  assert.equal(wrapper.props.closeModal, originalClose);
  assert.equal(forwardedParent, parent);
  assert.equal(forwardedOptions, options);
  const closeModal = () => {};
  const rendered = wrapper.type({ ...wrapper.props, closeModal });
  assert.equal(rendered.type, "ReturnFocusProvider");
  assert.equal(rendered.props.value, sourceScope);
  assert.equal(rendered.props.children.type, "EnvVarModal");
  assert.equal(rendered.props.children.props.closeModal, closeModal);
  assert.equal(rendered.props.children.props.initialKey, "");
  context.current = sourceScope;
  assert.equal(api.useModalReturnFocus(), sourceScope);
});
