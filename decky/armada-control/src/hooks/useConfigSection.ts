import { useCallback, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";
import { configFieldRevision, readAfterPendingConfigMutations, recordConfigFieldRead } from "../lib/configMutation";
import { mergeConfigSection } from "../lib/configSections";
import type { Config } from "../types";
import { useBackendState } from "./useBackendState";
import { waitForPendingApplies } from "./useDebouncedApply";

export interface ConfigSectionState {
  error: string;
  loading: boolean;
  refresh: () => Promise<void>;
}

export function useConfigSection<T extends Partial<Config>>(config: Config | null, setConfig: Dispatch<SetStateAction<Config | null>>, read: () => Promise<T>, fields: readonly (keyof Config)[], active = false): ConfigSectionState {
  const latest = useRef(config);
  latest.current = config;
  const load = useCallback(async (isCurrent: () => boolean) => {
    const baseline = latest.current;
    if (!baseline) return null;
    // Capture intent before waiting so late reads cannot undo newer edits.
    const revisions = new Map(fields.map((field) => [field, configFieldRevision(setConfig, field)]));
    await waitForPendingApplies();
    if (!isCurrent()) return null;
    const loaded = await readAfterPendingConfigMutations(setConfig, fields, () => isCurrent() ? read() : Promise.resolve(null));
    if (loaded === null || !isCurrent()) return null;
    for (const field of fields) {
      if (field in loaded && configFieldRevision(setConfig, field) === revisions.get(field)
        && JSON.stringify(latest.current?.[field]) === JSON.stringify(baseline[field])) {
        recordConfigFieldRead(setConfig, field, loaded[field]);
      }
    }
    setConfig((stored) => stored ? mergeConfigSection(stored, baseline, loaded, fields,
      (field) => configFieldRevision(setConfig, field) === revisions.get(field)) : stored);
    return loaded;
  }, [read, fields, setConfig]);
  return useBackendState(load, 0, !config, undefined, active, {
    observeWindow: false,
    retain: fields.every((field) => config?.[field] !== undefined),
  });
}
