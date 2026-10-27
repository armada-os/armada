import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject, SetStateAction } from "react";

type BackendRead<T> = (isCurrent: () => boolean) => Promise<T>;

export interface BackendState<T> {
  value: T | null;
  setValue: (next: SetStateAction<T | null>) => void;
  error: string;
  loading: boolean;
  refresh: () => Promise<void>;
}

export function useBackendState<T>(read: BackendRead<T>, interval = 0, paused = false, host?: RefObject<HTMLElement | null>, active = true,
  { observeWindow = true, retain = true } = {}): BackendState<T> {
  const [state, updateState] = useState<{ read: BackendRead<T>; value: T | null }>(() => ({ read, value: null }));
  const value = state.read === read ? state.value : null;
  const [failure, setFailure] = useState({ read, message: "", settled: false });
  const currentValue = useRef(value);
  currentValue.current = value;
  const reader = useRef(read);
  reader.current = read;
  const revision = useRef(0);
  const mounted = useRef(true);
  const settings = useRef({ paused, retain });
  settings.current = { paused, retain };
  const setValue = useCallback((next: SetStateAction<T | null>) => {
    if (!mounted.current || reader.current !== read) return;
    const result = typeof next === "function" ? (next as (current: T | null) => T | null)(currentValue.current) : next;
    if (Object.is(result, currentValue.current)) return;
    revision.current += 1;
    currentValue.current = result;
    updateState({ read, value: result });
    setFailure({ read, message: "", settled: true });
  }, [read]);
  const refresh = useCallback(async () => {
    if (settings.current.paused || !mounted.current || reader.current !== read) return;
    const request = ++revision.current;
    const isCurrent = () => mounted.current && !settings.current.paused && reader.current === read && request === revision.current;
    setFailure((current) => ({ read, message: "", settled: settings.current.retain && current.read === read && current.settled }));
    try {
      const next = await read(isCurrent);
      if (isCurrent()) {
        currentValue.current = next;
        updateState({ read, value: next });
        setFailure({ read, message: "", settled: true });
      }
    } catch (error) {
      if (isCurrent()) setFailure({ read, message: String(error), settled: true });
    }
  }, [read]);
  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => {
      mounted.current = false;
      revision.current += 1;
    };
  }, [refresh, paused]);
  useEffect(() => {
    if (!observeWindow || !active || paused) return;
    const view = host?.current?.ownerDocument.defaultView || window;
    const document = view.document;
    const visibleRefresh = () => { if (!document.hidden) void refresh(); };
    const timer = interval > 0 ? view.setInterval(visibleRefresh, interval) : undefined;
    view.addEventListener("focus", visibleRefresh);
    document.addEventListener("visibilitychange", visibleRefresh);
    return () => {
      view.clearInterval(timer);
      view.removeEventListener("focus", visibleRefresh);
      document.removeEventListener("visibilitychange", visibleRefresh);
    };
  }, [refresh, interval, host, active, paused, observeWindow]);
  const wasActive = useRef(active);
  useEffect(() => {
    const entered = active && !wasActive.current;
    wasActive.current = active;
    if (entered && failure.read === read && failure.settled) void refresh();
  }, [active, refresh]);
  return { value, setValue, error: failure.read === read ? failure.message : "", loading: failure.read !== read || !failure.settled, refresh };
}
