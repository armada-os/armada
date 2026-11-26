import { toaster } from "@decky/api";
import { PanelSection } from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { getConfig, getDeviceConfig, setSleepMode as applySleepMode, setChargingFanPwm as applyChargingFanPwm } from "../backend";
import { LoadingState } from "../components/LoadingState";
import { PanelCalibration } from "../components/PanelCalibration";
import { SleepLogs } from "../components/SleepLogs";
import { SectionDescription, SelectEdit, SliderEdit, ToggleRow } from "../components/widgets";
import type { BackendState } from "../hooks/useBackendState";
import { useDebouncedApply } from "../hooks/useDebouncedApply";
import { t, translateLabel } from "../i18n";
import { getLowPowerDownloadSettings, setLowPowerDownloadsEnabled, setLowPowerDownloadsOnBattery, subscribeLowPowerDownloadSettings } from "../lib/lowPowerDownloads";
import { createConfigMutation, markConfigFieldChange } from "../lib/configMutation";
import { percentToPwm, pwmToPercent } from "../lib/fanCurve";
import type { Config, DeviceConfig, ExperimentalConfig, SleepLogsStatus } from "../types";

const saveSleepMode = createConfigMutation("sleepMode", applySleepMode, { read: getConfig });

export function System({ config, setConfig, logsState, savingLogs, setSavingLogs }: {
  config: Config & DeviceConfig & ExperimentalConfig;
  setConfig: Dispatch<SetStateAction<Config | null>>;
  logsState: BackendState<SleepLogsStatus>;
  savingLogs: boolean;
  setSavingLogs: Dispatch<SetStateAction<boolean>>;
}) {
  const [downloads, setDownloads] = useState(getLowPowerDownloadSettings);
  const [saving, setSaving] = useState(false);
  const pending = useRef(false);
  const downloadIntent = useRef<{ field: "enabled" | "onBattery"; value: boolean } | null>(null);
  const mounted = useRef(true);
  const updateChargingFanPwm = useDebouncedApply(
    async () => (await getDeviceConfig()).chargingFanPwm,
    (value) => setConfig((current) => current ? { ...current, chargingFanPwm: value } : current),
    applyChargingFanPwm,
    t("settings.chargingFanSpeedError"),
    500,
  );
  const setChargingFanPwm = (value: number) => {
    markConfigFieldChange(setConfig, "chargingFanPwm");
    updateChargingFanPwm(value);
  };

  useEffect(() => {
    mounted.current = true;
    const unsubscribe = subscribeLowPowerDownloadSettings(() => {
      if (mounted.current) {
        const current = getLowPowerDownloadSettings();
        const intent = downloadIntent.current;
        setDownloads(intent ? { ...current, [intent.field]: intent.value } : current);
      }
    });
    setDownloads(getLowPowerDownloadSettings());
    return () => {
      mounted.current = false;
      unsubscribe();
    };
  }, []);

  const applyDownloads = async (field: "enabled" | "onBattery", value: boolean, apply: () => Promise<void>) => {
    if (pending.current) return;
    pending.current = true;
    downloadIntent.current = { field, value };
    setDownloads((current) => ({ ...current, [field]: value }));
    setSaving(true);
    let applied = false;
    try {
      await apply();
      applied = true;
    } catch (error) {
      toaster.toast({ title: t("settings.lowPowerDownloadsError"), body: String(error) });
    } finally {
      pending.current = false;
      downloadIntent.current = null;
      if (mounted.current) {
        const current = getLowPowerDownloadSettings();
        setDownloads(applied ? { ...current, [field]: value } : current);
        setSaving(false);
      }
    }
  };

  if (logsState.loading || (!logsState.value && !logsState.error)) return <LoadingState label={t("common.loadingSettings")} />;

  return <div>
    <PanelSection title={t("settings.downloads")}>
      <ToggleRow
        label={t("settings.lowPowerDownloads")}
        description={t("settings.lowPowerDownloadsDescription")}
        value={downloads.enabled}
        disabled={saving}
        onChange={(enabled) => { void applyDownloads("enabled", enabled, () => setLowPowerDownloadsEnabled(enabled)); }}
      />
      {downloads.enabled ? <ToggleRow
        label={t("settings.lowPowerDownloadsBattery")}
        description={t("settings.lowPowerDownloadsBatteryDescription")}
        value={downloads.onBattery}
        disabled={saving}
        onChange={(enabled) => { void applyDownloads("onBattery", enabled, () => setLowPowerDownloadsOnBattery(enabled)); }}
      /> : null}
    </PanelSection>
    {config.chargingFanSupported || config.panelCalibrationSupported ? <PanelSection title={t("settings.system")}>
      {config.chargingFanSupported ? <SliderEdit label={t("settings.chargingFanSpeed")} value={pwmToPercent(config.chargingFanPwm)} min={0} max={100} step={1} onChange={(value) => setChargingFanPwm(percentToPwm(value))} /> : null}
      <PanelCalibration supported={config.panelCalibrationSupported} />
    </PanelSection> : null}
    <PanelSection title={t("settings.sleepMode")}>
      <SectionDescription>{t("experimental.sleepDescription")}</SectionDescription>
      <SelectEdit value={config.sleepMode || "s2idle"} options={config.sleepModes.map(option => ({ ...option, label: translateLabel(option.label) }))}
        onChange={value => saveSleepMode(config, setConfig, value, error => toaster.toast({ title: t("settings.sleepModeError"), body: String(error) }))} />
    </PanelSection>
    <SleepLogs state={logsState} saving={savingLogs} setSaving={setSavingLogs} />
  </div>;
}
