import { toaster } from "@decky/api";
import { PanelSection } from "@decky/ui";
import type { Dispatch, SetStateAction } from "react";
import { getConfig, setSleepLogsEnabled, setSshEnabled } from "../backend";
import { LoadingState } from "../components/LoadingState";
import { ButtonRow, ReadOnlyRow, SupportingText, ToggleRow } from "../components/widgets";
import type { BackendState } from "../hooks/useBackendState";
import { readAfterPendingApplies } from "../hooks/useDebouncedApply";
import { t } from "../i18n";
import type { AboutConfig, Config, SleepLogsStatus } from "../types";
import { createConfigMutation } from "../lib/configMutation";

const saveSshEnabled = createConfigMutation("sshEnabled", setSshEnabled, { read: getConfig });

export function About({ config, setConfig, state, saving, setSaving }: {
  config: Config & AboutConfig;
  setConfig: Dispatch<SetStateAction<Config | null>>;
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
    <div>
      <PanelSection title={t("settings.system")}>
        <ReadOnlyRow label={t("settings.osVersion")} description={config.osVersion || t("common.unknown")} />
        <ReadOnlyRow label={t("settings.ablVersion")} description={config.ablVersion || t("common.unknown")} />
      </PanelSection>
      <PanelSection title={t("about.localLogs")}>
        {error ? <SupportingText className="armada-note-error">{t("about.loadingError")}: {error}</SupportingText> : null}
        {error ? <ButtonRow layout="below" onClick={() => { void refresh(); }}>{t("common.retry")}</ButtonRow> : null}
        {logs ? <>
          <ReadOnlyRow label={t("about.logDirectory")} description={logs.directory || t("common.unknown")} />
          <ToggleRow
            label={t("settings.sleepLogs")}
            description={t("about.sleepLogsDescription")}
            value={logs.enabled}
            disabled={saving}
            onChange={(enabled) => { void setEnabled(enabled); }}
          />
        </> : null}
      </PanelSection>
      <PanelSection title={t("about.developerSettings")}>
        <ToggleRow label={t("settings.enableSsh")} value={config.sshEnabled} onChange={(enabled) => saveSshEnabled(config, setConfig, enabled)} />
      </PanelSection>
    </div>
  );
}
