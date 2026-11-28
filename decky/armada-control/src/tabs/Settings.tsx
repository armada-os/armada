import { toaster } from "@decky/api";
import { PanelSection } from "@decky/ui";
import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  getBottomScreenActive,
  getConfig,
  setBottomScreenBrightness as applyBottomScreenBrightness,
  setBottomScreenEnabled as applyBottomScreenEnabled,
  setDesktopMode as applyDesktopMode,
  setMtpEnabled as applyMtpEnabled,
  setSshEnabled as applySshEnabled,
  setSwipeGesturesEnabled as applySwipeGesturesEnabled,
} from "../backend";
import { SectionDescription, SelectEdit, SliderEdit, ToggleRow } from "../components/widgets";
import { useDebouncedApply } from "../hooks/useDebouncedApply";
import { t, translateLabel } from "../i18n";
import { createConfigMutation, markConfigFieldChange } from "../lib/configMutation";
import type { AboutConfig, Config, ExperimentalConfig } from "../types";

const saveMtpEnabled = createConfigMutation("mtpEnabled", applyMtpEnabled, { read: getConfig });
const saveBottomScreenEnabled = createConfigMutation("bottomScreenEnabled", applyBottomScreenEnabled, { read: getConfig });
const saveDesktopMode = createConfigMutation("desktopMode", applyDesktopMode, { read: getConfig });
const saveSshEnabled = createConfigMutation("sshEnabled", applySshEnabled, { read: getConfig });
const saveSwipeGesturesEnabled = createConfigMutation("swipeGesturesEnabled", applySwipeGesturesEnabled, { read: getConfig, optimistic: false });

export function Settings({ config, setConfig }: {
  config: Config & ExperimentalConfig & AboutConfig;
  setConfig: Dispatch<SetStateAction<Config | null>>;
}) {
  const [swipeGesturesSaving, setSwipeGesturesSaving] = useState(false);
  const updateBottomScreenBrightness = useDebouncedApply(
    async () => (await getConfig()).bottomScreenBrightness,
    (value) => setConfig((current) => current ? { ...current, bottomScreenBrightness: value } : current),
    applyBottomScreenBrightness,
    t("settings.bottomScreenBrightnessError"),
    150,
  );
  const setBottomScreenBrightness = (value: number) => {
    markConfigFieldChange(setConfig, "bottomScreenBrightness");
    updateBottomScreenBrightness(value);
  };

  useEffect(() => {
    if (!config.bottomScreenBrightnessSupported) return;
    let cancelled = false;
    const refresh = async () => {
      try {
        const active = await getBottomScreenActive();
        if (!cancelled) {
          markConfigFieldChange(setConfig, "bottomScreenActive");
          setConfig((current) => current && current.bottomScreenActive !== active
            ? { ...current, bottomScreenActive: active } : current);
        }
      } catch (error) {
        if (!cancelled) setConfig((current) => current && current.bottomScreenActive
          ? { ...current, bottomScreenActive: false } : current);
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [config.bottomScreenBrightnessSupported, setConfig]);

  const setMtpEnabled = (enabled: boolean) => saveMtpEnabled(config, setConfig, enabled);
  const setSwipeGesturesEnabled = async (enabled: boolean) => {
    if (swipeGesturesSaving) return;
    setSwipeGesturesSaving(true);
    try {
      await saveSwipeGesturesEnabled(config, setConfig, enabled, (error) => {
        toaster.toast({ title: t("settings.swipeGesturesError"), body: String(error) });
      });
    } finally {
      setSwipeGesturesSaving(false);
    }
  };
  const setBottomScreenEnabled = (enabled: boolean) => saveBottomScreenEnabled(config, setConfig, enabled, (error) => {
    toaster.toast({ title: t("settings.bottomScreenError"), body: String(error) });
  });
  const setDesktopMode = (value: string) => saveDesktopMode(config, setConfig, value, (error) => {
    toaster.toast({ title: t("settings.desktopModeError"), body: String(error) });
  });


  return (
    <>
      <PanelSection title={t("settings.general")}>
        <ToggleRow label={t("settings.enableSsh")} value={config.sshEnabled} onChange={(enabled) => saveSshEnabled(config, setConfig, enabled)} />
        <ToggleRow
          label={t("settings.usbFileTransfer")}
          description={config.mtpEnabled ? t("settings.enabledUntilShutdown") : t("settings.usbDescription")}
          value={!!config.mtpEnabled}
          onChange={setMtpEnabled}
        />
        <ToggleRow
          label={t("settings.swipeGestures")}
          description={t("settings.swipeGesturesDescription")}
          value={config.swipeGesturesEnabled}
          disabled={swipeGesturesSaving}
          onChange={setSwipeGesturesEnabled}
        />
      </PanelSection>
      {(config.desktopModes?.length || 0) > 1 ? (
        <PanelSection title={t("settings.desktopMode")}>
          <SectionDescription>{t("settings.desktopDescription")}</SectionDescription>
          <SelectEdit
            value={config.desktopMode || "desktop"}
            options={(config.desktopModes || []).map((option) => ({ ...option, label: translateLabel(option.label) }))}
            onChange={setDesktopMode}
          />
        </PanelSection>
      ) : null}
      {config.bottomScreenSupported ? (
        <PanelSection title={t("settings.dualScreenTitle")}>
          <SectionDescription>{t("settings.dualScreenDescription")}</SectionDescription>
          <ToggleRow
            label={t("settings.bottomScreen")}
            description={t("settings.bottomScreenDescription")}
            value={!!config.bottomScreenEnabled}
            onChange={setBottomScreenEnabled}
          />
          {config.bottomScreenBrightnessSupported && config.bottomScreenActive ? (
            <SliderEdit
              label={t("settings.bottomScreenBrightness")}
              value={config.bottomScreenBrightness}
              min={0}
              max={100}
              step={1}
              onChange={setBottomScreenBrightness}
            />
          ) : null}
        </PanelSection>
      ) : null}
    </>
  );
}
