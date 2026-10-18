import { FileSelectionType, openFilePicker, toaster } from "@decky/api";
import { Button, ButtonItem, Focusable, GamepadButton, Menu, MenuItem, PanelSection, PanelSectionRow, TextField, showContextMenu } from "@decky/ui";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import * as backend from "./backend";
import { AppRow, TERMINAL_PHASES } from "./components/AppRow";
import { categoryIcons, searchIcon } from "./icons";
import { addToSteam, launchShortcut, removeFromSteam } from "./lib/shortcuts";
import { AndroidPages } from "./lib/android";
import { SIMPLIFIED_CHINESE_FONT_FAMILY, styles } from "./styles";
import type { Catalog, CatalogApp, Job, Status } from "./types";
import { t, type TranslationKey } from "./i18n";
import { useLocale } from "./hooks/useLocale";

const SECTIONS = [
  { key: "emulators", title: "categories.emulators" },
  { key: "applications", title: "categories.applications" },
  { key: "android", title: "categories.android" },
  { key: "plugins", title: "categories.plugins" },
] as const;

// Only these two backend-authored notes are localized; any other note is shown
// verbatim so unknown backend text is never mislabeled.
const NOTE_LABELS: Record<string, TranslationKey> = {
  "Paid apps are not supported": "notes.paidAppsUnsupported",
  "Unavailable for this device or anonymous session": "notes.deviceOrSessionUnavailable",
};

// The QAM unmounts the panel whenever a menu or modal takes focus, so
// per-render state cannot survive a drill-down.
let rememberedView: string | null = null;
let cachedCatalog: Catalog | null = null;
// Module scope: the panel remounts constantly, and AddShortcut may have run
// before a failure, so a retry would duplicate. Removal is safe to repeat.
const autoAddAttempted = new Set<string>();
const removalInFlight = new Set<string>();
const shortcutAdds = new Map<string, Promise<void>>();
const createdShortcuts = new Map<string, number>();
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
  const locale = useLocale();
  const fontClass = locale === "zh-CN" ? "armada-store-zh-cn" : undefined;
  // Context menus render outside this tree, and the QAM unmounts Content while
  // a menu has focus, so the zh class never reaches MenuItem text. Inline the
  // family on just the visible label.
  const menuText = (text: string) => (
    <span lang={locale} style={locale === "zh-CN" ? { fontFamily: SIMPLIFIED_CHINESE_FONT_FAMILY } : undefined}>
      {text}
    </span>
  );
  const [catalog, setCatalogState] = useState<Catalog | null>(cachedCatalog);
  const [status, setStatus] = useState<Status | null>(null);
  const [updates, setUpdates] = useState<Record<string, { latest: string }>>({});
  const [view, setViewState] = useState<string | null>(rememberedView);
  const [message, setMessage] = useState<string | null>(null);
  const [searchText, setSearchText] = useState(androidText);
  const [, redrawAndroid] = useState(0);
  const setCatalog = useCallback((next: Catalog | null) => {
    cachedCatalog = next;
    setCatalogState(next);
  }, []);
  const setView = useCallback((next: string | null) => {
    rememberedView = next;
    setViewState(next);
  }, []);
  const prevJobs = useRef(new Map<string, Job>());
  const unmounted = useRef(false);
  const statusInFlight = useRef(false);
  const refreshCatalog = useCallback(async () => {
    const next = await backend.getCatalog();
    cachedCatalog = next;
    if (!unmounted.current) setCatalog(next);
  }, [setCatalog]);

  const refreshStatus = useCallback(async () => {
    if (statusInFlight.current) return;
    statusInFlight.current = true;
    try {
      const next = await backend.getStatus();
      if (!unmounted.current) setStatus(next);
    } catch (error) {
    } finally {
      statusInFlight.current = false;
    }
  }, []);

  useEffect(() => {
    unmounted.current = false;
    backend.getCatalog()
      .then((data) => {
        if (!unmounted.current) setCatalog(data);
      })
      .catch((error) => {
        if (!unmounted.current) setMessage(String(error));
      });
    refreshStatus();
    backend.checkUpdates()
      .then((available) => {
        if (!unmounted.current) setUpdates(available);
      })
      .catch(() => {});
    const timer = window.setInterval(refreshStatus, 1000);
    return () => {
      unmounted.current = true;
      window.clearInterval(timer);
    };
  }, [refreshStatus]);

  const toast = useCallback((title: string, body?: string) => {
    try {
      toaster.toast({ title, body });
    } catch (error) {
    }
  }, []);

  useEffect(() => {
    if (!status || !catalog) return;
    let installFinished = false;
    for (const job of status.jobs) {
      const prev = prevJobs.current.get(job.appId);
      if (!prev || TERMINAL_PHASES.includes(prev.phase) || !TERMINAL_PHASES.includes(job.phase)) continue;
      const app = catalog.apps.find((entry) => entry.id === job.appId);
      if (!app) continue;
      if (job.phase === "error") {
        toast(app.name, job.error || t("common.failed"));
      } else if (job.phase === "done") {
        if (job.action !== "uninstall") {
          installFinished = true;
          toast(app.name, t("common.installed"));
        } else {
          toast(app.name, t("common.uninstalled"));
        }
      }
    }
    prevJobs.current = new Map(status.jobs.map((job) => [job.appId, job]));
    if (installFinished) {
      refreshCatalog().catch(() => {});
      // Latest tags stay cached; only the installed-version comparison reruns,
      // so a just-applied update clears its badge immediately.
      backend.checkUpdates()
        .then((available) => {
          if (!unmounted.current) setUpdates(available);
        })
        .catch(() => {});
    }
  }, [status, catalog, toast]);

  const jobs = useMemo(() => {
    const map = new Map<string, Job>();
    for (const job of status?.jobs || []) map.set(job.appId, job);
    return map;
  }, [status]);

  const run = useCallback((work: Promise<unknown>, onDone?: () => void) => {
    work
      .then(() => {
        onDone?.();
        refreshStatus();
      })
      .catch((error) => toast("Armada Store", String(error)));
  }, [refreshStatus, toast]);

  const addToSteamFlow = async (app: CatalogApp) => {
    const pending = shortcutAdds.get(app.id);
    if (pending) return pending;
    const work = (async () => {
      const appid = await addToSteam(app.launch, status?.shortcuts?.[app.id] ?? createdShortcuts.get(app.id),
        (id) => createdShortcuts.set(app.id, id));
      await backend.recordShortcut(app.id, appid);
    })();
    shortcutAdds.set(app.id, work);
    try {
      await work;
    } finally {
      shortcutAdds.delete(app.id);
    }
  };

  // A replacement queues while its old shortcut still exists. Dropping that one
  // is its own phase so a failure retries, leaving the queued add in place.
  const dropOldShortcut = async (appId: string, previous: number) => {
    try {
      removeFromSteam(previous);
      createdShortcuts.delete(appId);
      await backend.clearShortcutRecord(appId, true, previous);
    } finally {
      removalInFlight.delete(appId);
    }
  };

  // The backend keeps the pending list until a shortcut is recorded, so an
  // install that finished with the panel closed is still picked up later.
  useEffect(() => {
    if (!status || !catalog) return;
    const pending = status.pending || [];
    if (pending.some((id) => !catalog.apps.some((app) => app.id === id))) {
      refreshCatalog().catch(() => {});
    }
    for (const appId of autoAddAttempted) {
      // Off the queue: a later install or replacement gets a fresh attempt.
      if (!pending.includes(appId)) autoAddAttempted.delete(appId);
    }
    for (const appId of pending) {
      const app = catalog.apps.find((entry) => entry.id === appId);
      if (!app || !app.launch) continue;
      if (!status.installed?.[app.id]?.installed) continue;
      const previous = status.shortcuts?.[app.id];
      if (previous != null) {
        if (removalInFlight.has(app.id)) continue;
        removalInFlight.add(app.id);
        dropOldShortcut(app.id, previous).then(refreshStatus, () => {});
        continue;
      }
      if (autoAddAttempted.has(app.id)) continue;
      autoAddAttempted.add(app.id);
      run(addToSteamFlow(app), () => toast(app.name, t("notifications.addedToSteam")));
    }
  }, [status, catalog]);

  const removeFromSteamFlow = async (app: CatalogApp, appid: number) => {
    removeFromSteam(appid);
    createdShortcuts.delete(app.id);
    await backend.clearShortcutRecord(app.id);
  };

  // Best-effort shortcut removal: on failure the record survives, so the menu
  // keeps offering "Remove from Steam" even after the app itself is gone.
  const uninstallFlow = async (app: CatalogApp, shortcut: number | undefined) => {
    if (shortcut != null) {
      try {
        removeFromSteam(shortcut);
        createdShortcuts.delete(app.id);
        await backend.clearShortcutRecord(app.id);
      } catch (error) {
      }
    }
    await backend.uninstallApp(app.id);
  };

  const openMenu = (app: CatalogApp) => {
    const job = jobs.get(app.id) || null;
    const active = !!job && !TERMINAL_PHASES.includes(job.phase);
    const installed = !!status?.installed?.[app.id]?.installed;
    const conflicts = status?.installed?.[app.id]?.conflicts || [];
    const shortcut = status?.shortcuts?.[app.id];
    const items: ReactNode[] = [];
    if (active) {
      items.push(<MenuItem key="cancel" onSelected={() => run(backend.cancelJob(app.id))}>{menuText(t("common.cancel"))}</MenuItem>);
    } else {
      if (job?.phase === "error") {
        items.push(<MenuItem key="dismiss" onSelected={() => run(backend.dismissJob(app.id))}>{menuText(t("actions.dismissError"))}</MenuItem>);
      }
      // A desktop-only tool must not be launched from game mode even if an
      // older install left a Steam shortcut behind.
      const launchable = installed && !app.desktopOnly;
      if (shortcut != null && launchable) {
        items.push(
          <MenuItem
            key="play"
            onSelected={() => {
              try {
                launchShortcut(shortcut);
              } catch (error) {
                toast("Armada Store", String(error));
              }
            }}
          >
            {menuText(t("actions.launch"))}
          </MenuItem>,
        );
      }
      if (shortcut == null && app.launch && launchable) {
        items.push(
          <MenuItem key="add-steam" onSelected={() => run(addToSteamFlow(app), () => toast(app.name, t("notifications.addedToSteam")))}>
            {menuText(t("actions.addToSteam"))}
          </MenuItem>,
        );
      }
      const update = installed ? updates[app.id] : undefined;
      if (conflicts.length) {
        // Installing alongside would leave two copies and two shortcuts, so
        // this replaces the Install action rather than sitting next to it.
        const kind = conflicts[0].type === "appimage" ? "AppImage" : "Flatpak";
        items.push(
          <MenuItem key="replace" onSelected={() => run(backend.replaceApp(app.id))}>
            {menuText(t("actions.replaceVersion", { kind }))}
          </MenuItem>,
        );
      } else if ((!installed || update) && app.canInstall !== false) {
        // Not the resolved tag: half of them are "nightly" or a commit hash,
        // and no version is shown to compare against anyway.
        items.push(
          <MenuItem key="install" onSelected={() => run(backend.installApp(app.id))}>
            {menuText(installed ? t("actions.updateLatest") : t("actions.install"))}
          </MenuItem>,
        );
      }
      if (!installed && app.canInstall === false && app.note) {
        items.push(<MenuItem key="unavailable" disabled>{menuText(NOTE_LABELS[app.note] ? t(NOTE_LABELS[app.note]) : app.note)}</MenuItem>);
      }
      if (app.desktopOnly && installed) {
        items.push(
          <MenuItem key="desktop" onSelected={() => run(backend.switchToDesktop())}>
            {menuText(t("actions.switchToDesktop"))}
          </MenuItem>,
        );
      }
      if (shortcut != null) {
        // Offered whenever a shortcut record exists, even after uninstall,
        // so a stranded shortcut can always be cleaned up.
        items.push(
          <MenuItem
            key="remove-steam"
            onSelected={() => run(removeFromSteamFlow(app, shortcut), () => toast(app.name, t("notifications.removedFromSteam")))}
          >
            {menuText(t("actions.removeFromSteam"))}
          </MenuItem>,
        );
      }
      if (installed && app.hasConfig) {
        items.push(
          <MenuItem
            key="reset-config"
            tone="destructive"
            onSelected={() => run(backend.resetConfig(app.id), () => toast(app.name, t("notifications.configurationReset")))}
          >
            {menuText(t("actions.resetConfiguration"))}
          </MenuItem>,
        );
      }
      if (installed && app.installType !== "system") {
        items.push(
          <MenuItem key="uninstall" tone="destructive" onSelected={() => run(uninstallFlow(app, shortcut), () => { refreshCatalog().catch(() => {}); })}>
            {menuText(app.imported ? t("actions.removeFromStore") : t("actions.uninstall"))}
          </MenuItem>,
        );
      }
    }
    showContextMenu(<Menu label={app.name}>{items}</Menu>);
  };

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
      await refreshCatalog();
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
          await refreshCatalog();
          searchAndroid(false, "added");
        }));
      }).catch(() => {});
  };

  const categoryApps = (key: string) =>
    (cachedCatalog?.apps || catalog?.apps || [])
      .filter((app) => app.category === key)
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));

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

  const section = SECTIONS.find((entry) => entry.key === view);
  if (section) {
    const androidApps = (cachedCatalog?.apps || catalog.apps).filter((app) => app.category === "android");
    const filtering = androidScreen === "category" && !!searchText.trim();
    const androidIds = filtering ? androidSearch.pager.pages.flat() : androidSearch.pager.ids;
    const apps = section.key !== "android" ? categoryApps(section.key)
      : androidScreen === "home" ? []
      : (androidSearch.category === "added" ? androidApps.filter((app) => status?.installed?.[app.id]?.installed || status?.shortcuts?.[app.id] != null)
        : androidIds.map((id) => androidApps.find((app) => app.id === id)).filter((app): app is CatalogApp => !!app))
        .filter((app) => !filtering || app.name.toLocaleLowerCase().includes(searchText.trim().toLocaleLowerCase()));
    const androidFeed = androidFeeds.find((entry) => entry.data === androidSearch.category);
    const androidTitle = androidScreen === "home" ? t(section.title) : androidScreen === "search" ? t("android.searchResults")
      : androidFeed ? t(androidFeed.label) : undefined;
    return (
      <div className={fontClass} lang={locale}>
        <style>{styles}</style>
        <Focusable onButtonDown={(event) => {
          if (section.key === "android" && event.detail.button === GamepadButton.BUMPER_LEFT) {
            event.stopPropagation();
            if (!event.detail.is_repeat) androidBack();
          }
        }} actionDescriptionMap={section.key === "android" ? { [GamepadButton.BUMPER_LEFT]: t("common.back") } : undefined}>
          {section.key === "android" && <PanelSection>
            <PanelSectionRow><ButtonItem layout="below" onClick={androidBack}>{t("common.back")}</ButtonItem></PanelSectionRow>
          </PanelSection>}
          <PanelSection title={section.key === "android" ? androidTitle : t(section.title)}>
            {section.key !== "android" && <PanelSectionRow>
              <ButtonItem layout="below" onClick={() => setView(null)}>{t("common.back")}</ButtonItem>
            </PanelSectionRow>}
            {section.key === "android" && <>
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
            </>}
            {apps.map((app) => (
              <AppRow
                key={app.id}
                app={app}
                job={jobs.get(app.id) || null}
                info={status?.installed?.[app.id] || null}
                updateAvailable={updates[app.id] != null}
                onMenu={() => openMenu(app)}
              />
            ))}
            {section.key === "android" && androidScreen !== "home" && !filtering && androidSearch.category !== "added" && androidSearch.loaded &&
              <PanelSectionRow><Focusable style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Button style={{ flex: 1 }} disabled={androidSearch.busy || androidSearch.pager.index === 0}
                  onClick={() => { androidSearch.pager.previous(); androidSearch.message = ""; redrawAndroid((value) => value + 1); }}>{t("android.previous")}</Button>
                <span>{t("android.page", { page: androidSearch.pager.index + 1 })}</span>
                <Button style={{ flex: 1 }} disabled={androidSearch.busy || !androidSearch.pager.canNext}
                  onClick={() => searchAndroid(true, androidSearch.category)}>{t("android.next")}</Button>
              </Focusable></PanelSectionRow>}
          </PanelSection>
          {section.key === "android" && androidScreen === "home" && <PanelSection title={t("android.categories")}>
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
      <PanelSection title="Armada Store">
        {SECTIONS.map(({ key, title }) => {
          const apps = categoryApps(key);
          const activeJob = apps
            .map((app) => jobs.get(app.id))
            .find((job) => job && !TERMINAL_PHASES.includes(job.phase));
          const state = activeJob ? (activeJob.percent != null ? `${activeJob.percent}%` : "...") : "";
          return (
            <PanelSectionRow key={key}>
              <ButtonItem layout="below" onClick={() => setView(key)}>
                <div className="armada-store-row">
                  {categoryIcons[key] || categoryIcons.applications}
                  <div className="armada-store-row-text">
                    <div className="armada-store-row-name">{t(title)}</div>
                  </div>
                  {state && <div className="armada-store-row-state">{state}</div>}
                </div>
              </ButtonItem>
            </PanelSectionRow>
          );
        })}
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={addNonSteamGame}>
            <div className="armada-store-row">
              {categoryIcons.add}
              <div className="armada-store-row-text">
                <div className="armada-store-row-name">{t("actions.addNonSteamGame")}</div>
              </div>
            </div>
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    </div>
  );
}
