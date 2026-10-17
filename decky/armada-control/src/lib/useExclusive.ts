import { useRef, useState } from "react";

// Runs one backend action at a time and reports the busy state to the modal.
export function useExclusive(closing: boolean, onBusy: (busy: boolean) => void) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inflight = useRef(false);
  const exclusive = async (work: () => Promise<void>) => {
    if (inflight.current || closing) return;
    inflight.current = true;
    setBusy(true);
    onBusy(true);
    setError("");
    try { await work(); }
    catch (error) { setError(String(error)); }
    finally { inflight.current = false; setBusy(false); onBusy(false); }
  };
  return { exclusive, busy, error };
}
