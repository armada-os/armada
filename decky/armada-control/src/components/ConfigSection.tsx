import { PanelSection } from "@decky/ui";
import type { ReactNode } from "react";
import type { ConfigSectionState } from "../hooks/useConfigSection";
import { t } from "../i18n";
import type { Config } from "../types";
import { LoadingState } from "./LoadingState";
import { ButtonRow, SupportingText } from "./widgets";

export function ConfigSection<T extends Partial<Config>>({ config, state, loaded, children }: {
  config: Config;
  state: ConfigSectionState;
  loaded: (current: Config) => current is Config & T;
  children: (current: Config & T) => ReactNode;
}) {
  const { error, refresh, loading } = state;
  if (loading) return <LoadingState label={t("common.loadingSettings")} />;
  return <>
    {error || !loaded(config) ? <PanelSection>
      <div role="alert"><SupportingText className="armada-note-error">{t("common.loadError")}{error ? `: ${error}` : ""}</SupportingText></div>
      <ButtonRow layout="below" onClick={() => { void refresh(); }}>{t("common.retry")}</ButtonRow>
    </PanelSection> : null}
    {loaded(config) ? children(config) : null}
  </>;
}
