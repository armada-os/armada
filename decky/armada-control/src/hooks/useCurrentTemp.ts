import { useEffect, useState } from "react";
import { getCurrentTemp } from "../backend";

const POLL_INTERVAL_MS = 3000;

export function useCurrentTemp(): number | null {
  const [temp, setTemp] = useState<number | null>(null);
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const next = await getCurrentTemp();
        if (!cancelled) setTemp(next);
      } catch {
        // Transient read failure -- skip this tick rather than surfacing an error.
      }
    };
    poll();
    const timer = window.setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);
  return temp;
}
