import { toaster } from "@decky/api";
import { Menu, MenuItem, showContextMenu } from "@decky/ui";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import * as backend from "./backend";
import { TERMINAL_PHASES } from "./components/AppRow";
import { addToSteam, launchShortcut, removeFromSteam } from "./lib/shortcuts";
import { SIMPLIFIED_CHINESE_FONT_FAMILY } from "./styles";
import type { Catalog, CatalogApp, Job, Status } from "./types";
import { t, type TranslationKey } from "./i18n";
import { useLocale } from "./hooks/useLocale";

// Catalog, status and job handling shared by every Armada app panel: polling,
// toasts, the per-app menu, and the Steam shortcut queue the backend keeps.

// Only these two backend-authored notes are localized; any other note is shown
// verbatim so unknown backend text is never mislabeled.
const NOTE_LABELS: Record<string, TranslationKey> = {
  "Paid apps are not supported": "notes.paidAppsUnsupported",
  "Unavailable for this device or anonymous session": "notes.deviceOrSessionUnavailable",
};

// The QAM unmounts the panel whenever a menu or modal takes focus, so
// per-render state cannot survive a drill-down.
let rememberedView: string | null = null;
let catalogInFlight: Promise<void> | null = null;
let cachedCatalog: Catalog | null = null;
// Module scope: the panel remounts constantly, and AddShortcut may have run
// before a failure, so a retry would duplicate. Removal is safe to repeat.
const autoAddAttempted = new Set<string>();
const removalInFlight = new Set<string>();
// Module scope, so a panel remounting mid-call never asks twice.
const reloadsInFlight = new Set<string>();
const shortcutAdds = new Map<string, Promise<void>>();
const createdShortcuts = new Map<string, number>();

// A tag with no digits, like "nightly", is reused for every build, so the
// upload date tells builds apart.
function displayVersion(locale: string, value?: string, date?: string) {
  let version = (value || "").trim().replace(/^v(?=\d)/, "");
  const when = date ? new Date(date) : null;
  if (version && !/\d/.test(version) && when && !isNaN(when.getTime())) {
    const sameYear = when.getFullYear() === new Date().getFullYear();
    const day = when.toLocaleDateString(locale, { month: "short", day: "numeric", ...(sameYear ? {} : { year: "numeric" }) });
    version = `${version} ${day}`;
  }
  return version;
}

export function useAppManager(title: string) {
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
  const [updates, setUpdates] = useState<Record<string, { latest: string; date?: string }>>({});
  const [view, setViewState] = useState<string | null>(rememberedView);
  const [message, setMessage] = useState<string | null>(null);
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
  // One fetch at a time, across panel reopenings, so an older reply never lands
  // after a newer one; fresh skips joining a fetch older than a backend change.
  const refreshCatalog = useCallback((fresh = false) => {
    if (!catalogInFlight || fresh) {
      const run: Promise<void> = (catalogInFlight || Promise.resolve())
        .catch(() => {})
        .then(() => backend.getCatalog())
        .then((next) => {
          cachedCatalog = next;
        })
        .finally(() => {
          if (catalogInFlight === run) catalogInFlight = null;
        });
      catalogInFlight = run;
    }
    return catalogInFlight.then(() => {
      if (!unmounted.current) setCatalog(cachedCatalog);
    });
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
    refreshCatalog()
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
  }, [refreshStatus, refreshCatalog]);

  // Each revision is fetched once: the reply can carry a newer one than status
  // has seen yet, and retrying on every render would loop until it catches up.
  const fetchedRevision = useRef<string | undefined>(undefined);
  const [catalogRetry, setCatalogRetry] = useState(0);
  const catalogRevision = status?.catalogRevision;
  useEffect(() => {
    if (!catalogRevision || catalogRevision === cachedCatalog?.revision
        || catalogRevision === fetchedRevision.current) return;
    fetchedRevision.current = catalogRevision;
    let retry: number | undefined;
    refreshCatalog()
      .then(() => {
        // Joined a fetch that started before this revision: go again shortly.
        if (cachedCatalog?.revision !== catalogRevision) throw new Error("stale catalog");
        return backend.checkUpdates();
      })
      .then((available) => {
        if (!unmounted.current) setUpdates(available);
      })
      .catch(() => {
        fetchedRevision.current = undefined;
        retry = window.setTimeout(() => setCatalogRetry((n) => n + 1), 5000);
      });
    return () => window.clearTimeout(retry);
  }, [catalogRevision, catalogRetry, refreshCatalog]);

  const toast = useCallback((title: string, body?: string) => {
    try {
      toaster.toast({ title, body });
    } catch (error) {
    }
  }, []);

  useEffect(() => {
    if (!status || !catalog) return;
    let installFinished = false;
    let uninstallFinished = false;
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
          // Steam lists compatibility tools only at startup.
          toast(app.name, app.installType === "proton" ? t("notifications.restartSteamToUse") : t("common.installed"));
        } else {
          uninstallFinished = true;
          toast(app.name, t("common.uninstalled"));
        }
      }
    }
    prevJobs.current = new Map(status.jobs.map((job) => [job.appId, job]));
    // A retired app is listed only while something of it is installed.
    if (installFinished || uninstallFinished) refreshCatalog().catch(() => {});
    if (installFinished) {
      // Latest tags stay cached; only the installed-version comparison reruns,
      // so a just-applied update clears its badge immediately.
      backend.checkUpdates()
        .then((available) => {
          if (!unmounted.current) setUpdates(available);
        })
        .catch(() => {});
    }
  }, [status, catalog, toast]);

  // Decky reloads a plugin only through its own update path; this is that
  // path's route. It is internal to Decky, and the image installs Decky's
  // latest release, so when the route fails all of Decky restarts instead.
  useEffect(() => {
    const decky = (window as unknown as { DeckyBackend?: { call: (route: string, ...args: unknown[]) => Promise<unknown> } }).DeckyBackend;
    for (const name of status?.reload || []) {
      if (reloadsInFlight.has(name)) continue;
      reloadsInFlight.add(name);
      (async () => {
        try {
          if (!decky?.call) throw new Error("no Decky backend");
          await decky.call("loader/reload_plugin", name);
          await backend.clearReload(name);
        } catch (error) {
          await backend.clearReload(name).catch(() => {});
          await backend.restartDecky().catch(() => {});
        } finally {
          reloadsInFlight.delete(name);
        }
      })();
    }
  }, [status]);

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
      .catch((error) => toast(title, String(error)));
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
    const update = installed ? updates[app.id] : undefined;
    if (installed && !active) {
      const info = status?.installed?.[app.id];
      const version = update ? displayVersion(locale, update.latest, update.date) : displayVersion(locale, info?.version, info?.date);
      // Whatever the Store cannot remove came with the image.
      const builtIn = !app.removable;
      const label = update
        ? version ? t("status.updateVersion", { version }) : t("status.update")
        : builtIn
          ? version ? t("status.builtInVersion", { version }) : t("status.builtIn")
          : version ? t("status.installedVersion", { version }) : t("common.installed");
      items.push(<MenuItem key="status" disabled>{menuText(label)}</MenuItem>);
    }
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
                toast(title, String(error));
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
      if (conflicts.length && app.canInstall !== false) {
        // Installing alongside would leave two copies and two shortcuts, so
        // this replaces the Install action rather than sitting next to it.
        const kind = conflicts[0].type === "appimage" ? "AppImage" : "Flatpak";
        items.push(
          <MenuItem key="replace" onSelected={() => run(backend.replaceApp(app.id))}>
            {menuText(t("actions.replaceVersion", { kind }))}
          </MenuItem>,
        );
      } else if ((!installed || update) && app.canInstall !== false) {
        // The status line above names the version.
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
      if (installed && app.removable) {
        items.push(
          <MenuItem key="uninstall" tone="destructive" onSelected={() => run(uninstallFlow(app, shortcut), () => { refreshCatalog().catch(() => {}); })}>
            {menuText(app.imported ? t("actions.removeFromStore") : t("actions.uninstall"))}
          </MenuItem>,
        );
      }
    }
    showContextMenu(<Menu label={app.name}>{items}</Menu>);
  };

  // Apps of one section, alphabetically.
  const categoryApps = (key: string) =>
    (catalog?.apps || [])
      .filter((app) => app.category === key)
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));

  return {
    locale, fontClass, menuText, catalog, status, updates, message, jobs, view, setView,
    run, toast, openMenu, refreshCatalog, refreshStatus, categoryApps,
  };
}
