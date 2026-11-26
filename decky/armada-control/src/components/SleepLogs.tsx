import { toaster } from "@decky/api";
import { PanelSection } from "@decky/ui";
import type { Dispatch, SetStateAction } from "react";
import { setSleepLogsEnabled } from "../backend";
import { LoadingState } from "./LoadingState";
import { ButtonRow, ReadOnlyRow, SupportingText, ToggleRow } from "./widgets";
import type { BackendState } from "../hooks/useBackendState";
import { readAfterPendingApplies } from "../hooks/useDebouncedApply";
import { t } from "../i18n";
import type { SleepLogsStatus } from "../types";

export function SleepLogs({ state, saving, setSaving }: {
  state: BackendState<SleepLogsStatus>;
  saving: boolean;
  setSaving: Dispatch<SetStateAction<boolean>>;
}) {
  const { value: logs, setValue: setLogs, error, refresh, loading } = state;

  const setEnabled = async (enabled: boolean) => {
    if (!logs || saving) return;
    setSaving(true);
    try {
      const saved = await readAfterPendingApplies(() => setSleepLogsEnabled(enabled));
      setLogs((current) => current ? { ...current, enabled: saved } : current);
    } catch (error) {
      toaster.toast({ title: t("settings.sleepLogsError"), body: String(error) });
    } finally {
      setSaving(false);
    }
  };

  if (loading || (!logs && !error)) return <LoadingState label={t("common.loadingSettings")} />;

  return (
      <PanelSection title={t("settings.localLogs")}>
        {error ? <SupportingText className="armada-note-error">{t("settings.logsLoadingError")}: {error}</SupportingText> : null}
        {error ? <ButtonRow layout="below" onClick={() => { void refresh(); }}>{t("common.retry")}</ButtonRow> : null}
        {logs ? <>
          <ReadOnlyRow label={t("settings.logDirectory")} description={logs.directory || t("common.unknown")} />
          <ToggleRow
            label={t("settings.sleepLogs")}
            description={t("settings.sleepLogsDescription")}
            value={logs.enabled}
            disabled={saving}
            onChange={(enabled) => { void setEnabled(enabled); }}
          />
        </> : null}
      </PanelSection>
  );
}
