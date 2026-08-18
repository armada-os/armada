import { useEffect } from "react";
import type { MutableRefObject, Dispatch, SetStateAction } from "react";
import type { Config } from "../types";

interface DebouncedSaveOptions {
  config: Config | null;
  field: "power" | "tweaks" | "rgb";
  snapshot: MutableRefObject<string>;
  save: (value: any) => Promise<Config>;
  setConfig: Dispatch<SetStateAction<Config | null>>;
  onError?: (error: unknown) => void;
  delay?: number;
}

export function useDebouncedSave(options: DebouncedSaveOptions) {
  const { config, field, snapshot, save, setConfig, onError, delay = 900 } = options;
  const value = config ? (config as any)[field] : undefined;
  useEffect(() => {
    if (!config || !snapshot.current) return;
    const current = JSON.stringify(value);
    if (current === snapshot.current) return;
    const timer = window.setTimeout(async () => {
      try {
        const saved = current;
        const next = await save(value);
        snapshot.current = JSON.stringify((next as any)[field]);
        setConfig((stored) => {
          if (!stored) return next;
          if (JSON.stringify((stored as any)[field]) !== saved) return stored;
          return { ...stored, [field]: (next as any)[field] };
        });
      } catch (error) {
        onError?.(error);
      }
    }, delay);
    return () => window.clearTimeout(timer);
  }, [value]);
}
