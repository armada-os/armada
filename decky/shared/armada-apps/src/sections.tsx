import { ButtonItem, PanelSection, PanelSectionRow } from "@decky/ui";
import type { ReactNode } from "react";
import { AppRow, TERMINAL_PHASES } from "./components/AppRow";
import { t } from "./i18n";
import type { CatalogApp, CatalogCategory } from "./types";
import type { useAppManager } from "./useAppManager";

type Manager = ReturnType<typeof useAppManager>;

// Sections come from the catalog; "other" is the engine's own, for installed
// apps whose section the catalog no longer shows.
export function categoryTitle(category: CatalogCategory, locale: string): string {
  if (category.id === "other") return t("categories.other");
  if (typeof category.name === "string") return category.name;
  return category.name[locale] || category.name.en || category.id;
}

// A mask filled with the text color, so the icon follows focus like the label.
export function categoryIcon(category: CatalogCategory): ReactNode {
  if (!category.icon.startsWith("data:image/svg+xml;")) return null;
  const mask = `url("${category.icon}") no-repeat center / contain`;
  return (
    <span
      style={{ display: "block", flex: "none", width: 20, height: 20, opacity: 0.9,
               backgroundColor: "currentColor", mask, WebkitMask: mask }}
    />
  );
}

export function AppRows({ manager, apps }: { manager: Manager; apps: CatalogApp[] }) {
  const { jobs, status, updates, openMenu } = manager;
  return <>{apps.map((app) => (
    <AppRow
      key={app.id}
      app={app}
      job={jobs.get(app.id) || null}
      info={status?.installed?.[app.id] || null}
      updateAvailable={updates[app.id] != null}
      onMenu={() => openMenu(app)}
    />
  ))}</>;
}

// One catalog section: a back button and its apps.
export function SectionScreen({ manager, category }: { manager: Manager; category: CatalogCategory }) {
  return (
    <PanelSection title={categoryTitle(category, manager.locale)}>
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={() => manager.setView(null)}>{t("common.back")}</ButtonItem>
      </PanelSectionRow>
      <AppRows manager={manager} apps={manager.categoryApps(category.id)} />
    </PanelSection>
  );
}

// The panel's first screen: one row per section, with any active job's
// progress, then whatever the plugin adds below.
export function SectionMenu({ manager, title, children }: { manager: Manager; title: string; children?: ReactNode }) {
  const { catalog, jobs, locale, setView, categoryApps } = manager;
  return (
    <PanelSection title={title}>
      {catalog?.notice && <PanelSectionRow><div>{catalog.notice}</div></PanelSectionRow>}
      {(catalog?.categories || []).map((category) => {
        const activeJob = categoryApps(category.id)
          .map((app) => jobs.get(app.id))
          .find((job) => job && !TERMINAL_PHASES.includes(job.phase));
        const state = activeJob ? (activeJob.percent != null ? `${activeJob.percent}%` : "...") : "";
        return (
          <PanelSectionRow key={category.id}>
            <ButtonItem layout="below" onClick={() => setView(category.id)}>
              <div className="armada-store-row">
                {categoryIcon(category)}
                <div className="armada-store-row-text">
                  <div className="armada-store-row-name">{categoryTitle(category, locale)}</div>
                </div>
                {state && <div className="armada-store-row-state">{state}</div>}
              </div>
            </ButtonItem>
          </PanelSectionRow>
        );
      })}
      {children}
    </PanelSection>
  );
}
