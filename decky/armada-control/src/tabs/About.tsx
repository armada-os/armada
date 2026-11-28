import { PanelSection } from "@decky/ui";
import { ReadOnlyRow } from "../components/widgets";
import { t } from "../i18n";
import type { AboutConfig } from "../types";

export function About({ config }: { config: AboutConfig }) {
  return <PanelSection title={t("settings.system")}>
    <ReadOnlyRow label={t("settings.osVersion")} description={config.osVersion || t("common.unknown")} />
    <ReadOnlyRow label={t("settings.ablVersion")} description={config.ablVersion || t("common.unknown")} />
  </PanelSection>;
}
