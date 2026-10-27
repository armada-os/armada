import { Spinner } from "@decky/ui";
import { useRef } from "react";
import { usePanelHeight } from "../hooks/usePanelHeight";
import { t } from "../i18n";
import { SupportingText } from "./widgets";

export function LoadingState({ label = t("common.loading") }: { label?: string }) {
  const root = useRef<HTMLDivElement>(null);
  usePanelHeight(root);
  return <div ref={root} className="armada-loading-state" role="status" aria-live="polite" aria-busy>
    <Spinner className="armada-loading-spinner" aria-hidden="true" />
    <SupportingText>{label}</SupportingText>
  </div>;
}
