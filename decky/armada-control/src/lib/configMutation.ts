import type { Dispatch, SetStateAction } from "react";
import type { Config } from "../types";

type ConfigSetter = Dispatch<SetStateAction<Config | null>>;

interface PendingValue<T> {
  confirmed: T;
  revision: number;
  tail: Promise<void>;
}

interface MutationOptions {
  optimistic?: boolean;
  read?: () => Promise<Partial<Config>>;
}

// Field edits also invalidate reads when a choice changes away and back.
interface FieldMutation {
  revision: number;
  tail: Promise<void>;
  acceptedRead?: { revision: number; value: unknown };
  changedPaths: Map<string, number>;
}

const pendingMutations = new WeakMap<ConfigSetter, Map<keyof Config, FieldMutation>>();

function fieldMutation(setConfig: ConfigSetter, field: keyof Config): FieldMutation {
  let fields = pendingMutations.get(setConfig);
  if (!fields) {
    fields = new Map();
    pendingMutations.set(setConfig, fields);
  }
  let state = fields.get(field);
  if (!state) {
    state = { revision: 0, tail: Promise.resolve(), changedPaths: new Map() };
    fields.set(field, state);
  }
  return state;
}

export function markConfigFieldChange(setConfig: ConfigSetter, field: keyof Config, paths: readonly (readonly string[])[] = [[]]): void {
  const state = fieldMutation(setConfig, field);
  state.revision++;
  for (const path of paths) state.changedPaths.set(JSON.stringify(path), state.revision);
}

export function configPathChanged(setConfig: ConfigSetter, field: keyof Config, since: number, path: readonly string[]): boolean {
  const state = pendingMutations.get(setConfig)?.get(field);
  if (!state) return false;
  for (const [serialized, revision] of state.changedPaths) {
    if (revision <= since) continue;
    const changed: string[] = JSON.parse(serialized);
    if (changed.every((key, index) => index >= path.length || path[index] === key)) return true;
  }
  return false;
}

export function configFieldRevision(setConfig: ConfigSetter, field: keyof Config): number {
  return pendingMutations.get(setConfig)?.get(field)?.revision || 0;
}

export function recordConfigFieldRead<K extends keyof Config>(setConfig: ConfigSetter, field: K, value: Config[K]): void {
  const state = fieldMutation(setConfig, field);
  state.acceptedRead = { revision: state.revision, value };
}

export async function readAfterPendingConfigMutations<T>(setConfig: ConfigSetter, fields: readonly (keyof Config)[], read: () => Promise<T>): Promise<T> {
  for (;;) {
    const tails = fields.map((field) => pendingMutations.get(setConfig)?.get(field)?.tail);
    await Promise.all(tails);
    if (fields.every((field, index) => pendingMutations.get(setConfig)?.get(field)?.tail === tails[index])) return read();
  }
}

export function createConfigMutation<K extends keyof Config>(
  field: K,
  apply: (value: NonNullable<Config[K]>) => Promise<NonNullable<Config[K]>>,
  { optimistic = true, read }: MutationOptions = {},
) {
  // The parent owns config, so pending changes must survive closing and reopening a tab.
  const owners = new WeakMap<ConfigSetter, PendingValue<NonNullable<Config[K]>>>();
  return (config: Config, setConfig: ConfigSetter, value: NonNullable<Config[K]>, onError?: (error: unknown) => void) => {
    const confirmed = config[field];
    if (confirmed === undefined || confirmed === null) return Promise.reject(new Error("Configuration is unavailable"));
    const mutation = fieldMutation(setConfig, field);
    let state = owners.get(setConfig);
    if (!state) {
      state = { confirmed, revision: 0, tail: Promise.resolve() };
      owners.set(setConfig, state);
    }
    // A completed refresh becomes the rollback baseline for the next write.
    const accepted = mutation.acceptedRead;
    if (accepted?.revision === mutation.revision && accepted.value !== undefined && accepted.value !== null) {
      state.confirmed = accepted.value as NonNullable<Config[K]>;
    }
    mutation.revision++;
    const current = state;
    const revision = ++current.revision;
    const show = (next: NonNullable<Config[K]>) => setConfig((stored) => stored && revision === current.revision
      ? { ...stored, [field]: next } : stored);
    if (optimistic) show(value);
    const request = current.tail.then(async () => {
      try {
        current.confirmed = await apply(value);
      } catch (error) {
        if (read) {
          try {
            const recovered = (await read())[field];
            if (recovered !== undefined && recovered !== null) current.confirmed = recovered;
          } catch {}
        }
        if (revision === current.revision) onError?.(error);
      } finally {
        show(current.confirmed);
      }
    });
    current.tail = request.catch(() => {});
    mutation.tail = current.tail;
    return request;
  };
}
