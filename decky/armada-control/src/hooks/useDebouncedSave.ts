import { useEffect, useRef } from "react";
import type { MutableRefObject, Dispatch, SetStateAction } from "react";
import type { Config } from "../types";
import { createDebouncedSave } from "../lib/settingsSave";

interface DebouncedSaveOptions {
  config: Config | null;
  field: "power" | "tweaks";
  snapshot: MutableRefObject<string>;
  save: (value: any) => Promise<Config>;
  setConfig: Dispatch<SetStateAction<Config | null>>;
  onError?: (error: unknown) => void;
  delay?: number;
}

export function useDebouncedSave(options: DebouncedSaveOptions) {
  const { config, field, snapshot, save, setConfig, delay = 900 } = options;
  const value = config ? (config as any)[field] : undefined;
  const mounted = useRef(false);
  const latest = useRef(options);
  latest.current = options;
  const writer = useRef<ReturnType<typeof createDebouncedSave<any, Config>> | null>(null);
  useEffect(() => {
    if (!config || !snapshot.current) return;
    if (!writer.current) {
      writer.current = createDebouncedSave({
        snapshot: () => snapshot.current,
        save,
        delay,
        onSaved(next, submitted) {
          snapshot.current = JSON.stringify(next[field]);
          if (!mounted.current) return;
          setConfig((stored) => {
            if (!stored || JSON.stringify(stored[field]) !== submitted) return stored;
            return { ...stored, [field]: next[field] };
          });
        },
        onError(error, submitted) {
          if (mounted.current && JSON.stringify(latest.current.config?.[field]) === submitted) {
            latest.current.onError?.(error);
          }
        },
      });
    }
    writer.current.update(value);
  }, [value]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      // Closing the QAM must commit the last edit, not cancel its debounce.
      void writer.current?.flush();
    };
  }, []);
}
