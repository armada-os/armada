import type { TranslationKey } from "../locales/en";

// Last result written by armada-update to /var/lib/armada/update-status.json.
export interface UpdateStatus {
  result: string;
  time?: number;
  version?: string;
  needed_bytes?: number;
  reserve_bytes?: number;
  available_bytes?: number;
}

export interface UpdateNotice {
  key: TranslationKey;
  size: string;
  toast: boolean;
}

const MESSAGES = new Map<string, TranslationKey>([
  ["no_space", "update.noSpace"],
  ["apply_failed", "update.applyFailed"],
  ["bad_metadata", "update.checkFailed"],
  ["error", "update.checkFailed"],
  ["remote_unreachable", "update.unreachable"],
]);

// Rounded up so freeing the shown amount is always enough.
const gigabytes = (bytes: number) => `${(Math.ceil(bytes / 1e8) / 10).toFixed(1)} GB`;

export function updateNotice(status: UpdateStatus | null | undefined): UpdateNotice | null {
  const key = status && MESSAGES.get(status.result);
  if (!key) return null;
  const missing = (status.needed_bytes ?? 0) + (status.reserve_bytes ?? 0) - (status.available_bytes ?? 0);
  // Short network outages are common on handhelds; keep them out of toasts.
  return { key, size: gigabytes(Math.max(missing, 0)), toast: status.result !== "remote_unreachable" };
}
