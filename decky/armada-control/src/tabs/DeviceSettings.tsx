import { toaster } from "@decky/api";
import { PanelSection } from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { getDeviceConfig, setChargingFanPwm as applyChargingFanPwm } from "../backend";
import { LoadingState } from "../components/LoadingState";
import { PanelCalibration } from "../components/PanelCalibration";
import { RgbLighting } from "../components/RgbLighting";
import { ButtonRow, SliderEdit, SupportingText, ToggleRow } from "../components/widgets";
import type { BackendState } from "../hooks/useBackendState";
import { useDebouncedApply } from "../hooks/useDebouncedApply";
import { t } from "../i18n";
import { getLowPowerDownloadSettings, setLowPowerDownloadsEnabled, setLowPowerDownloadsOnBattery, subscribeLowPowerDownloadSettings } from "../lib/lowPowerDownloads";
import { markConfigFieldChange } from "../lib/configMutation";
import { percentToPwm, pwmToPercent } from "../lib/fanCurve";
import type { Config, DeviceConfig, RgbConfig } from "../types";

export function DeviceSettings({ config, setConfig, rgbState }: {
  config: Config & DeviceConfig;
  setConfig: Dispatch<SetStateAction<Config | null>>;
  rgbState: BackendState<RgbConfig | null>;
}) {
  const { value: rgb, setValue: setRgbConfig, loading: rgbLoading, error: rgbError, refresh: refreshRgb } =
    rgbState;
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

  if (config.rgbSupported && rgbLoading) return <LoadingState label={t("common.loadingSettings")} />;

  const rgbFailure = config.rgbSupported && rgbError ? <PanelSection>
    <SupportingText className="armada-note-error">{t("rgb.loadError")}: {rgbError}</SupportingText>
    <ButtonRow layout="below" onClick={() => { void refreshRgb(); }}>{t("common.retry")}</ButtonRow>
  </PanelSection> : null;

  return <div>
    {rgbFailure}
    {config.rgbSupported && rgb ? <RgbLighting config={rgb} setConfig={setRgbConfig} /> : null}
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
  </div>;
}
