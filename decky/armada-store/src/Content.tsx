import { FileSelectionType, openFilePicker } from "@decky/api";
import { Button, ButtonItem, Focusable, GamepadButton, PanelSection, PanelSectionRow, TextField } from "@decky/ui";
import { useState } from "react";
import * as backend from "./armada-apps/backend";
import { addIcon, searchIcon } from "./armada-apps/icons";
import { addToSteam } from "./armada-apps/lib/shortcuts";
import { AppRows, SectionMenu, SectionScreen, categoryTitle } from "./armada-apps/sections";
import { styles } from "./armada-apps/styles";
import type { CatalogApp } from "./armada-apps/types";
import { t } from "./armada-apps/i18n";
import { useAppManager } from "./armada-apps/useAppManager";
import { AndroidPages } from "./lib/android";

let androidText = "";
let androidScreen: "home" | "category" | "search" = "home";
const androidFeeds = [
  { data: "APPLICATION", label: "android.popular" },
  { data: "GAME", label: "android.games" },
  { data: "TOOLS", label: "android.tools" },
  { data: "VIDEO_PLAYERS", label: "android.media" },
  { data: "COMMUNICATION", label: "android.communication" },
  { data: "added", label: "android.installedApps" },
] as const;
const androidCache = new Map<string, AndroidPages>();
let androidSearch = { query: "", category: "APPLICATION", pager: new AndroidPages(), loaded: false, busy: false, message: "" };

export function Content() {
  const manager = useAppManager("Armada Store");
  const { locale, fontClass, catalog, status, message, view, setView, run, toast, refreshCatalog } = manager;
  const [searchText, setSearchText] = useState(androidText);
  const [, redrawAndroid] = useState(0);

  // Steam's own "Add a Non-Steam Game" browse button does nothing on the ARM
  // client (ValveSoftware/steam-for-linux#9447).
  const addNonSteamGame = () => {
    const home = catalog?.home || "/var/home/armada";
    openFilePicker(FileSelectionType.FILE, home, true, true)
      .then((result) => {
        const path = result.realpath || result.path;
        if (!path) return;
        backend.prepareShortcut(path)
          .then((launch) => addToSteam(launch).then(() => toast(launch.name, t("notifications.addedToSteam"))))
          .catch((error) => toast(t("notifications.couldNotAdd"), String(error)));
      })
      .catch(() => {});
  };

  const searchAndroid = async (next = false, category = "") => {
    if (androidSearch.busy || (!next && !category && !searchText.trim())) return;
    if (!next) {
      androidScreen = category ? "category" : "search";
      if (category) {
        androidText = "";
        setSearchText("");
      }
    }
    if (category === "added") {
      androidSearch = { ...androidSearch, category, loaded: true, message: "" };
      redrawAndroid((value) => value + 1);
      return;
    }
    if (next && androidSearch.pager.next()) {
      androidSearch.message = "";
      redrawAndroid((value) => value + 1);
      return;
    }
    const query = next ? androidSearch.query : category ? "" : searchText.trim();
    if (!category && !query) return;
    const cached = !next && category ? androidCache.get(category) : undefined;
    if (cached) {
      cached.index = 0;
      androidSearch = { ...androidSearch, category, query, pager: cached, loaded: true, message: "" };
      redrawAndroid((value) => value + 1);
      return;
    }
    const page = next ? androidSearch.pager.cursors[0] : undefined;
    if (next && !page) return;
    androidSearch = { ...androidSearch, category, query, pager: next ? androidSearch.pager : new AndroidPages(),
      loaded: false, busy: true, message: category ? t("android.loading") : t("android.searching") };
    redrawAndroid((value) => value + 1);
    try {
      const result = await backend.searchAndroid(query, page, category || undefined);
      const pager = next ? androidSearch.pager : new AndroidPages();
      const previousLength = pager.pages.length;
      pager.append(result.ids, result.pages, page);
      if (next && pager.pages.length > previousLength) pager.index = previousLength;
      androidSearch = { ...androidSearch, category, query, pager, loaded: true,
        message: result.ids.length ? "" : t("android.noMatchingApps") };
      if (category) androidCache.set(category, pager);
      await refreshCatalog(true);
    } catch (error) {
      androidSearch.loaded = true;
      androidSearch.message = String(error);
    } finally {
      androidSearch.busy = false;
      redrawAndroid((value) => value + 1);
    }
  };

  const androidBack = () => {
    if (androidScreen === "home") setView(null);
    else {
      androidScreen = "home";
      androidText = "";
      setSearchText("");
      redrawAndroid((value) => value + 1);
    }
  };

  const addLocalApk = () => {
    openFilePicker(FileSelectionType.FILE, catalog?.home || "/var/home/armada", true, true)
      .then((result) => {
        const path = result.realpath || result.path;
        if (path) run(backend.importAndroid(path).then(async () => {
          await refreshCatalog(true);
          searchAndroid(false, "added");
        }));
      }).catch(() => {});
  };

  if (!catalog) {
    return (
      <div className={fontClass} lang={locale}>
        <style>{styles}</style>
        <PanelSection title="Armada Store">
          <PanelSectionRow>
            <div>{message ?? t("common.loading")}</div>
          </PanelSectionRow>
        </PanelSection>
      </div>
    );
  }

  const section = catalog.categories.find((entry) => entry.id === view);
  if (section && section.id !== "android") {
    return (
      <div className={fontClass} lang={locale}>
        <style>{styles}</style>
        <SectionScreen manager={manager} category={section} />
      </div>
    );
  }
  if (section) {
    const androidApps = catalog.apps.filter((app) => app.category === "android");
    const filtering = androidScreen === "category" && !!searchText.trim();
    const androidIds = filtering ? androidSearch.pager.pages.flat() : androidSearch.pager.ids;
    const apps = androidScreen === "home" ? []
      : (androidSearch.category === "added" ? androidApps.filter((app) => status?.installed?.[app.id]?.installed || status?.shortcuts?.[app.id] != null)
        : androidIds.map((id) => androidApps.find((app) => app.id === id)).filter((app): app is CatalogApp => !!app))
        .filter((app) => !filtering || app.name.toLocaleLowerCase().includes(searchText.trim().toLocaleLowerCase()));
    const androidFeed = androidFeeds.find((entry) => entry.data === androidSearch.category);
    const androidTitle = androidScreen === "home" ? categoryTitle(section, locale) : androidScreen === "search" ? t("android.searchResults")
      : androidFeed ? t(androidFeed.label) : undefined;
    return (
      <div className={fontClass} lang={locale}>
        <style>{styles}</style>
        <Focusable onButtonDown={(event) => {
          if (event.detail.button === GamepadButton.BUMPER_LEFT) {
            event.stopPropagation();
            if (!event.detail.is_repeat) androidBack();
          }
        }} actionDescriptionMap={{ [GamepadButton.BUMPER_LEFT]: t("common.back") }}>
          <PanelSection>
            <PanelSectionRow><ButtonItem layout="below" onClick={androidBack}>{t("common.back")}</ButtonItem></PanelSectionRow>
          </PanelSection>
          <PanelSection title={androidTitle}>
              <PanelSectionRow>
                <div className="armada-store-search">
                  <span aria-hidden="true">{searchIcon}</span>
                  <TextField {...{ placeholder: t("android.searchPlaceholder") }}
                    aria-label={androidScreen === "category" ? t("android.filterList") : t("android.searchApps")}
                    value={searchText} onChange={(event) => {
                      androidText = event.target.value;
                      setSearchText(androidText);
                    }} onKeyDown={(event) => {
                      if (event.key === "Enter" && androidScreen !== "category") searchAndroid(false);
                    }} />
                </div>
              </PanelSectionRow>
              {androidScreen === "home" ? <PanelSectionRow>
                <ButtonItem layout="below" disabled={androidSearch.busy}
                  onClick={addLocalApk}>{t("android.addLocalApk")}</ButtonItem>
              </PanelSectionRow> : androidSearch.message && <PanelSectionRow><div>{androidSearch.message}</div></PanelSectionRow>}
              {filtering && !apps.length && <PanelSectionRow><div>{t("android.noMatchesInList")}</div></PanelSectionRow>}
              {filtering && <PanelSectionRow>
                <ButtonItem layout="below" disabled={androidSearch.busy}
                  onClick={() => searchAndroid(false)}>{t("android.searchAll")}</ButtonItem>
              </PanelSectionRow>}
            <AppRows manager={manager} apps={apps} />
            {androidScreen !== "home" && !filtering && androidSearch.category !== "added" && androidSearch.loaded &&
              <PanelSectionRow><Focusable style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Button style={{ flex: 1 }} disabled={androidSearch.busy || androidSearch.pager.index === 0}
                  onClick={() => { androidSearch.pager.previous(); androidSearch.message = ""; redrawAndroid((value) => value + 1); }}>{t("android.previous")}</Button>
                <span>{t("android.page", { page: androidSearch.pager.index + 1 })}</span>
                <Button style={{ flex: 1 }} disabled={androidSearch.busy || !androidSearch.pager.canNext}
                  onClick={() => searchAndroid(true, androidSearch.category)}>{t("android.next")}</Button>
              </Focusable></PanelSectionRow>}
          </PanelSection>
          {androidScreen === "home" && <PanelSection title={t("android.categories")}>
            <PanelSectionRow><div style={{ opacity: 0.65 }}>{t("android.browseByCategory")}</div></PanelSectionRow>
            {androidFeeds.map((feed) => <PanelSectionRow key={feed.data}>
              <ButtonItem layout="below" disabled={androidSearch.busy}
                onClick={() => searchAndroid(false, feed.data)}>{t(feed.label)}</ButtonItem>
            </PanelSectionRow>)}
          </PanelSection>}
        </Focusable>
      </div>
    );
  }

  return (
    <div className={fontClass} lang={locale}>
      <style>{styles}</style>
      <SectionMenu manager={manager} title="Armada Store">
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={addNonSteamGame}>
            <div className="armada-store-row">
              {addIcon}
              <div className="armada-store-row-text">
                <div className="armada-store-row-name">{t("actions.addNonSteamGame")}</div>
              </div>
            </div>
          </ButtonItem>
        </PanelSectionRow>
      </SectionMenu>
    </div>
  );
}
