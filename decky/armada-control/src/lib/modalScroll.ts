import { isLastFocusableRegion, revealScrollRegion } from "./scrollRegion";

const modalSelector = ".armada-control-dialog";
const positionSelector = ".armada-control-dialog-position";
const headingSelector = ".armada-control-dialog-heading";
const footerSelector = ".armada-control-dialog-footer";

function isScrollRegion(element: HTMLElement) {
  const overflow = element.ownerDocument.defaultView?.getComputedStyle(element).overflowY;
  return overflow === "auto" || overflow === "scroll";
}

export function revealModalStart(target: HTMLElement | null): boolean {
  const modal = target?.closest<HTMLElement>(modalSelector);
  if (!modal) return false;
  const container = modal.closest<HTMLElement>(positionSelector) || modal;
  let handled = false;
  for (const element of [container, ...container.querySelectorAll<HTMLElement>("*")]) {
    const owned = element.contains(modal) || (modal.contains(element) && element.closest(modalSelector) === modal);
    if (!owned || element.closest(positionSelector) !== modal.closest(positionSelector) || !isScrollRegion(element)) continue;
    element.scrollTo({ top: 0, behavior: "instant" });
    handled = true;
  }
  return handled;
}

export function revealModalFocus(boundary: HTMLElement | null, target: HTMLElement | undefined, fieldSelector: string): boolean {
  const modal = boundary?.closest<HTMLElement>(modalSelector);
  if (!target || !boundary?.contains(target) || !modal || target.closest(modalSelector) !== modal) return false;
  if (target.closest(headingSelector)) return revealModalStart(target);
  const field = (fieldSelector ? target.closest<HTMLElement>(fieldSelector) : null)
    || target.closest<HTMLElement>(".DialogInputLabelGroup");
  const footer = target.closest<HTMLElement>(footerSelector);
  const region = footer || field || target;
  const visible = modal.contains(region) ? region : target;
  const revealEnd = !!footer || isLastFocusableRegion(modal, visible);
  const container = modal.closest<HTMLElement>(positionSelector) || modal;
  let handled = false;
  for (let parent = visible.parentElement; parent && container.contains(parent); parent = parent.parentElement) {
    if (!isScrollRegion(parent)) continue;
    revealScrollRegion(parent, visible, parent.getBoundingClientRect().top, revealEnd);
    handled = true;
  }
  return handled;
}
