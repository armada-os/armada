import { PanelSection } from "@decky/ui";
import { RgbLighting } from "../components/RgbLighting";
import { LoadingState } from "../components/LoadingState";
import { ButtonRow, SupportingText } from "../components/widgets";
import type { BackendState } from "../hooks/useBackendState";
import { t } from "../i18n";
import type { RgbConfig } from "../types";

export function RGB({ state }: { state: BackendState<RgbConfig | null> }) {
  if (state.loading) return <LoadingState label={t("common.loadingSettings")} />;
  if (state.error || !state.value) return <PanelSection>
    <SupportingText className="armada-note-error">{t("rgb.loadError")}: {state.error}</SupportingText>
    <ButtonRow layout="below" onClick={() => { void state.refresh(); }}>{t("common.retry")}</ButtonRow>
  </PanelSection>;
  return <RgbLighting config={state.value} setConfig={state.setValue} />;
}
