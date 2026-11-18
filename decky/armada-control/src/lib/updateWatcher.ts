import { toaster } from "@decky/api";
import { getUpdateStatus } from "../backend";
import { t } from "../i18n";
import { updateNotice } from "./updateStatus";

const POLL_MS = 30000;

// Steam reports blocked updates as "no updates"; toast after every blocked check and once per session.
export function registerUpdateWatcher(): () => void {
  let shown: string | undefined;
  const tick = () => {
    getUpdateStatus()
      .then((status) => {
        const notice = updateNotice(status);
        const id = `${status?.result}:${status?.time}`;
        if (!notice?.toast || id === shown) return;
        shown = id;
        toaster.toast({ title: t("update.blocked"), body: t(notice.key, { size: notice.size }) });
      })
      .catch(() => {});
  };
  let timer: number | undefined;
  let stopped = false;
  // Steam drops toasts sent right after startup, so the first check waits one interval.
  Promise.resolve((window as any).App?.WaitForServicesInitialized?.())
    .catch(() => {})
    .then(() => {
      if (!stopped) timer = window.setInterval(tick, POLL_MS);
    });
  return () => {
    stopped = true;
    window.clearInterval(timer);
  };
}
