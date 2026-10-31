import { classMap, DialogBody, DialogButton, DialogButtonPrimary, DialogFooter, DialogHeader, Focusable, ModalRoot } from "@decky/ui";
import type { FocusableProps, ModalRootProps } from "@decky/ui";
import { useLayoutEffect, useRef } from "react";
import type { ComponentType, ReactNode, RefAttributes } from "react";
import { revealModalFocus, revealModalStart } from "../lib/modalScroll";
import { ArmadaStyles } from "./ArmadaStyles";
import { useModalReturnFocus } from "./modalFocusView";
import { registerModalFocusScope } from "../lib/modalFocus";

const FocusableHeading = Focusable as ComponentType<FocusableProps & RefAttributes<HTMLDivElement> & { focusable: boolean }>;

// Steam exposes focus scrolling on Focusable, not the native modal's form.
const ModalNavigation = Focusable as ComponentType<FocusableProps & RefAttributes<HTMLDivElement> & {
  navRef: RefAttributes<{ TakeFocus: () => boolean; BFocusWithin: () => boolean }>["ref"];
  scrollIntoViewWhenChildFocused: "force";
  fnScrollIntoViewHandler: (target: { Element?: HTMLElement }) => boolean;
}>;

const fieldSelector = [...new Set(classMap.map((classes) => classes.Field).filter(Boolean))]
  .map((name) => `.${name}`).join(", ");

export function ArmadaDialogFooter({ children }: { children: ReactNode }) {
  return <DialogFooter>
    <Focusable className="armada-control-dialog-footer" flow-children="row" tabIndex={-1} noFocusRing>{children}</Focusable>
  </DialogFooter>;
}

export function ArmadaDialogHeader({ children }: { children: ReactNode }) {
  const heading = useRef<HTMLDivElement>(null);
  const showStart = () => { revealModalStart(heading.current); };
  return <DialogHeader>
    <FocusableHeading ref={heading} className="armada-control-dialog-heading" focusable tabIndex={0} preferredFocus onGamepadFocus={showStart} onFocus={showStart}>{children}</FocusableHeading>
  </DialogHeader>;
}

export function ArmadaModalRoot({ children, className = "", modalClassName = "", ...props }: ModalRootProps) {
  const returnFocus = useModalReturnFocus();
  const boundary = useRef<HTMLDivElement>(null);
  const navigation = useRef<{ TakeFocus: () => boolean; BFocusWithin: () => boolean }>(null);
  useLayoutEffect(() => {
    const modal = boundary.current?.closest<HTMLElement>(".armada-control-dialog");
    if (!modal) return;
    const scope = registerModalFocusScope(modal, () => navigation.current?.TakeFocus() || false, () => navigation.current?.BFocusWithin() || false, true, returnFocus);
    return () => scope.dispose();
  }, [returnFocus]);
  return (
    <ModalRoot
      {...props}
      className={["armada-control-dialog", className].filter(Boolean).join(" ")}
      modalClassName={["armada-control-dialog-position", modalClassName].filter(Boolean).join(" ")}
    >
      <ArmadaStyles />
      <ModalNavigation
        ref={boundary}
        navRef={navigation}
        className="armada-control-dialog-scroll"
        flow-children="column"
        tabIndex={-1}
        noFocusRing
        scrollIntoViewWhenChildFocused="force"
        fnScrollIntoViewHandler={(target) => revealModalFocus(boundary.current, target.Element, fieldSelector)}
      >{children}</ModalNavigation>
    </ModalRoot>
  );
}

export function ArmadaConfirmModal({ title, description, confirmText, cancelText, onConfirm, closeModal, closeBeforeConfirm = false }: {
  title: ReactNode;
  description: ReactNode;
  confirmText: ReactNode;
  cancelText: ReactNode;
  onConfirm: () => void;
  closeModal?: () => void;
  closeBeforeConfirm?: boolean;
}) {
  const confirm = () => {
    if (closeBeforeConfirm) closeModal?.();
    onConfirm();
    if (!closeBeforeConfirm) closeModal?.();
  };
  // Close-first confirmations handle submit dismissal before running their action.
  return <ArmadaModalRoot closeModal={closeBeforeConfirm ? undefined : closeModal} onCancel={closeModal} onOK={closeBeforeConfirm ? confirm : onConfirm}>
    <ArmadaDialogHeader>{title}</ArmadaDialogHeader>
    <DialogBody>{description}</DialogBody>
    <ArmadaDialogFooter>
      <DialogButtonPrimary onClick={confirm}>{confirmText}</DialogButtonPrimary>
      <DialogButton onClick={closeModal}>{cancelText}</DialogButton>
    </ArmadaDialogFooter>
  </ArmadaModalRoot>;
}
