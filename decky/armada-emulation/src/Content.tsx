import { PanelSection, PanelSectionRow } from "@decky/ui";
import { SectionMenu, SectionScreen } from "./armada-apps/sections";
import { styles } from "./armada-apps/styles";
import { t } from "./armada-apps/i18n";
import { useAppManager } from "./armada-apps/useAppManager";

export function Content() {
  const manager = useAppManager("Armada Emulation");
  const { locale, fontClass, catalog, message, view } = manager;

  if (!catalog) {
    return (
      <div className={fontClass} lang={locale}>
        <style>{styles}</style>
        <PanelSection title="Armada Emulation">
          <PanelSectionRow>
            <div>{message ?? t("common.loading")}</div>
          </PanelSectionRow>
        </PanelSection>
      </div>
    );
  }

  const section = catalog.categories.find((entry) => entry.id === view);
  return (
    <div className={fontClass} lang={locale}>
      <style>{styles}</style>
      {section
        ? <SectionScreen manager={manager} category={section} />
        : <SectionMenu manager={manager} title="Armada Emulation" />}
    </div>
  );
}
