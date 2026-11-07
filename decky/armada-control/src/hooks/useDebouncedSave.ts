import { useCallback, useEffect, useRef } from "react";
import type { MutableRefObject, Dispatch, SetStateAction } from "react";
import type { Config, Tweaks } from "../types";
import { queueConfigSave, registerPendingConfigSave } from "../lib/configSaveQueue";
import { configFieldRevision, configPathChanged } from "../lib/configMutation";

export type SaveNow = (update: (current: Tweaks) => Tweaks) => Promise<Config>;

export interface SaveRecovery {
  config: Config;
  saved: Config;
}

interface DebouncedSaveOptions {
  config: Config | null;
  snapshot: MutableRefObject<string>;
  save: (value: Tweaks, baseline: Tweaks) => Promise<{ tweaks: Tweaks }>;
  setConfig: Dispatch<SetStateAction<Config | null>>;
  onError?: (error: unknown) => Config | SaveRecovery | void | Promise<Config | SaveRecovery | void>;
  delay?: number;
}

const equal = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);
const isRecord = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);

// Apply saved changes only where a newer local edit has not replaced the baseline.
function reconcile<T>(before: T, saved: T, current: T, changed: (path: string[]) => boolean = () => false, path: string[] = []): T {
  if (equal(before, saved)) return current;
  if (equal(before, current) && !changed(path)) return saved;
  if (!isRecord(saved) || !isRecord(current) || (!isRecord(before) && before !== undefined)) return current;
  const baseline: Record<string, unknown> = isRecord(before) ? before : {};
  const next: Record<string, unknown> = { ...current };
  for (const key of new Set([...Object.keys(baseline), ...Object.keys(saved)])) {
    const hadBefore = Object.prototype.hasOwnProperty.call(baseline, key);
    const hasSaved = Object.prototype.hasOwnProperty.call(saved, key);
    const hasCurrent = Object.prototype.hasOwnProperty.call(current, key);
    if (!hasSaved) {
      if (hadBefore && hasCurrent && equal(baseline[key], current[key]) && !changed([...path, key])) delete next[key];
    } else if (!hasCurrent) {
      if (!hadBefore && !changed([...path, key])) Object.defineProperty(next, key, { value: saved[key], enumerable: true, writable: true, configurable: true });
    } else {
      Object.defineProperty(next, key, { value: reconcile(baseline[key], saved[key], current[key], changed, [...path, key]), enumerable: true, writable: true, configurable: true });
    }
  }
  return next as T;
}

export function useDebouncedSave(options: DebouncedSaveOptions): SaveNow {
  const latest = useRef(options);
  latest.current = options;
  const currentConfig = useRef(options.config);
  currentConfig.current = options.config;
  const timer = useRef<number | undefined>(undefined);
  const owner = useRef({});
  const manualPending = useRef(0);
  const failed = useRef<{ value: string; revision: number } | null>(null);
  const mounted = useRef(true);
  const clearTimer = () => {
    if (timer.current !== undefined) window.clearTimeout(timer.current);
    timer.current = undefined;
    registerPendingConfigSave(owner.current, null);
  };
  const schedule = () => {
    clearTimer();
    const config = currentConfig.current;
    const { snapshot, delay = 900 } = latest.current;
    if (!mounted.current || manualPending.current || !config || !snapshot.current) return;
    const value = JSON.stringify(config.tweaks);
    // Retry a failed value only after a new edit or an explicit save.
    if (value === snapshot.current || (value === failed.current?.value
      && configFieldRevision(latest.current.setConfig, "tweaks") === failed.current.revision)) return;
    const flush = () => {
      clearTimer();
      const request = queueConfigSave(async () => {
        try { return await persist(); } catch (error) {
          if (manualPending.current) return;
          const baseline = currentConfig.current;
          const recovered = await latest.current.onError?.(error);
          if (recovered) {
            const { snapshot } = latest.current;
            const current = currentConfig.current;
            const config = "config" in recovered ? recovered.config : recovered;
            const saved = "saved" in recovered ? recovered.saved : recovered;
            currentConfig.current = current && baseline ? {
              ...current,
              tweaks: reconcile(baseline.tweaks, config.tweaks, current.tweaks),
            } : config;
            snapshot.current = JSON.stringify(saved.tweaks);
          }
        }
      });
      void request.finally(schedule).catch(() => {});
    };
    registerPendingConfigSave(owner.current, flush);
    timer.current = window.setTimeout(flush, delay);
  };
  const persist = async (update?: (current: Tweaks) => Tweaks): Promise<Config> => {
    const config = currentConfig.current;
    if (!config) throw new Error("Configuration is unavailable");
    const { snapshot, save, setConfig } = latest.current;
    const baseline = config.tweaks;
    const submitted = update ? update(JSON.parse(JSON.stringify(baseline))) : baseline;
    const serialized = JSON.stringify(submitted);
    const revision = configFieldRevision(setConfig, "tweaks");
    if (!update && serialized === snapshot.current) return config;
    let saved: { tweaks: Tweaks };
    try {
      saved = await save(submitted, JSON.parse(snapshot.current || JSON.stringify(baseline)));
    } catch (error) {
      if (!update) failed.current = { value: serialized, revision };
      throw error;
    }
    snapshot.current = JSON.stringify(saved.tweaks);
    failed.current = null;
    const apply = (stored: Config | null) => {
      if (!stored) return stored;
      const value = reconcile(baseline, saved.tweaks, stored.tweaks, (path) => configPathChanged(setConfig, "tweaks", revision, path));
      const next = value === stored.tweaks ? stored : { ...stored, tweaks: value };
      currentConfig.current = next;
      return next;
    };
    const next = apply(currentConfig.current) || { ...config, ...saved };
    if (mounted.current) setConfig(apply);
    return next;
  };
  const saveNow = useCallback<SaveNow>((update) => {
    clearTimer();
    manualPending.current++;
    const request = queueConfigSave(() => persist(update));
    return request.finally(() => {
      manualPending.current--;
      failed.current = null;
      schedule();
    });
  }, []);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearTimer();
      const current = currentConfig.current;
      const { snapshot } = latest.current;
      if (current && snapshot.current && JSON.stringify(current.tweaks) !== snapshot.current) {
        void queueConfigSave(() => persist()).catch((error) => latest.current.onError?.(error)).catch(() => {});
      }
    };
  }, []);
  const value = options.config?.tweaks;
  useEffect(() => {
    schedule();
    return clearTimer;
  }, [value]);
  return saveNow;
}
