import { call } from "@decky/api";
import type { Catalog, Job, LaunchSpec, Status } from "./types";

export const getCatalog = () => call<[], Catalog>("get_catalog");
export const getStatus = () => call<[], Status>("get_status");
export const checkUpdates = (force = false) =>
  call<[boolean], Record<string, { latest: string }>>("check_updates", force);
export const installApp = (appId: string) => call<[string], Job>("install_app", appId);
export const uninstallApp = (appId: string) => call<[string], Job>("uninstall_app", appId);
export const replaceApp = (appId: string) => call<[string], Job>("replace_app", appId);
export const cancelJob = (appId: string) => call<[string], boolean>("cancel_job", appId);
export const dismissJob = (appId: string) => call<[string], void>("dismiss_job", appId);
export const prepareShortcut = (path: string) => call<[string], LaunchSpec>("prepare_shortcut", path);
export const recordShortcut = (appId: string, steamAppid: number) =>
  call<[string, number], void>("record_shortcut", appId, steamAppid);
export const clearShortcutRecord = (appId: string, keepPending = false, expected?: number) =>
  call<[string, boolean, number | null], void>("clear_shortcut", appId, keepPending, expected ?? null);
export const switchToDesktop = () => call<[], void>("switch_to_desktop");
