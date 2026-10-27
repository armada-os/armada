import { showModal } from "@decky/ui";
import type { ShowModalProps } from "@decky/ui";
import { cloneElement, createContext, useContext } from "react";
import type { ReactElement } from "react";
import { captureModalFocus } from "../lib/modalFocus";
import type { ModalFocusTarget } from "../lib/modalFocus";

const ReturnFocus = createContext<ModalFocusTarget | undefined>(undefined);

function ModalFocusView({ view, target, closeModal }: { view: ReactElement; target?: ModalFocusTarget; closeModal?: () => void }) {
  // Steam injects dismissal into the direct child of showModal.
  return <ReturnFocus.Provider value={target}>{cloneElement(view as ReactElement<{ closeModal?: () => void }>, { closeModal })}</ReturnFocus.Provider>;
}

export function showArmadaModal(view: ReactElement, parent?: EventTarget, props?: ShowModalProps) {
  const closeModal = (view as ReactElement<{ closeModal?: () => void }>).props.closeModal;
  return showModal(<ModalFocusView view={view} target={captureModalFocus()} closeModal={closeModal} />, parent, props);
}

export function useModalReturnFocus() {
  return useContext(ReturnFocus);
}
