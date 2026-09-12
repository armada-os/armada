import { toaster } from "@decky/api";
import { ButtonItem, Field, PanelSection } from "@decky/ui";
import { useEffect, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  setAblAutoEnabled as applyAblAutoEnabled,
  setBottomScreenBrightness as applyBottomScreenBrightness,
  setBottomScreenEnabled as applyBottomScreenEnabled,
  setControllerType as applyControllerType,
  setMtpEnabled as applyMtpEnabled,
  setDesktopMode as applyDesktopMode,
  setSleepMode as applySleepMode,
  setSshEnabled as applySshEnabled,
} from "../backend";
import { openCalibration } from "../components/Calibration";
import { SelectEdit, SliderEdit, ToggleRow } from "../components/widgets";
import { t, translateLabel } from "../i18n";
import type { Config } from "../types";

const BOTTOM_SCREEN_BRIGHTNESS_DELAY_MS: number = 150;

export function Settings({ config, setConfig }: {
  config: Config;
  setConfig: Dispatch<SetStateAction<Config | null>>;
}) {
  const bottomScreenBrightnessTimer = useRef<number | undefined>(undefined);
  const bottomScreenBrightnessRequest = useRef<number>(0);
  const appliedBottomScreenBrightness = useRef<number>(config.bottomScreenBrightness);

  useEffect(() => () => {
    window.clearTimeout(bottomScreenBrightnessTimer.current);
    bottomScreenBrightnessRequest.current += 1;
  }, []);

  const setSshEnabled = async (enabled: boolean) => {
    if (enabled === !!config.sshEnabled) {
      return;
    }
    setConfig((current) => (current ? { ...current, sshEnabled: enabled } : current));
    try {
      const applied = await applySshEnabled(enabled);
      setConfig((current) => (current ? { ...current, sshEnabled: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, sshEnabled: !enabled } : current));
    }
  };
  const setMtpEnabled = async (enabled: boolean) => {
    if (enabled === !!config.mtpEnabled) {
      return;
    }
    setConfig((current) => (current ? { ...current, mtpEnabled: enabled } : current));
    try {
      const applied = await applyMtpEnabled(enabled);
      setConfig((current) => (current ? { ...current, mtpEnabled: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, mtpEnabled: !enabled } : current));
    }
  };
  const setControllerType = async (value: string) => {
    const previous = config.controllerType || "deck-uhid";
    setConfig((current) => (current ? { ...current, controllerType: value } : current));
    try {
      const applied = await applyControllerType(value);
      setConfig((current) => (current ? { ...current, controllerType: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, controllerType: previous } : current));
    }
  };
  const setAblAutoEnabled = async (enabled: boolean) => {
    if (enabled === !!config.ablAutoEnabled) {
      return;
    }
    setConfig((current) => (current ? { ...current, ablAutoEnabled: enabled } : current));
    try {
      const applied = await applyAblAutoEnabled(enabled);
      setConfig((current) => (current ? { ...current, ablAutoEnabled: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, ablAutoEnabled: !enabled } : current));
    }
  };
  const setBottomScreenEnabled = async (enabled: boolean) => {
    if (enabled === !!config.bottomScreenEnabled) {
      return;
    }
    setConfig((current) => (current ? { ...current, bottomScreenEnabled: enabled } : current));
    try {
      const applied = await applyBottomScreenEnabled(enabled);
      setConfig((current) => (current ? { ...current, bottomScreenEnabled: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, bottomScreenEnabled: !enabled } : current));
      toaster.toast({ title: t("Could not change bottom screen"), body: String(error) });
    }
  };
  const setBottomScreenBrightness = (brightness: number) => {
    setConfig((current) => (current ? { ...current, bottomScreenBrightness: brightness } : current));
    window.clearTimeout(bottomScreenBrightnessTimer.current);
    const request = ++bottomScreenBrightnessRequest.current;
    bottomScreenBrightnessTimer.current = window.setTimeout(async () => {
      try {
        const applied = await applyBottomScreenBrightness(brightness);
        if (request !== bottomScreenBrightnessRequest.current) return;
        appliedBottomScreenBrightness.current = applied;
        setConfig((current) => (current ? { ...current, bottomScreenBrightness: applied } : current));
      } catch (error) {
        if (request !== bottomScreenBrightnessRequest.current) return;
        setConfig((current) => (current ? {
          ...current,
          bottomScreenBrightness: appliedBottomScreenBrightness.current,
        } : current));
        toaster.toast({ title: t("Could not change bottom-screen brightness"), body: String(error) });
      }
    }, BOTTOM_SCREEN_BRIGHTNESS_DELAY_MS);
  };
  const setDesktopMode = async (value: string) => {
    const previous = config.desktopMode || "desktop";
    setConfig((current: Config | null) => (current ? { ...current, desktopMode: value } : current));
    try {
      const applied = await applyDesktopMode(value);
      setConfig((current: Config | null) => (current ? { ...current, desktopMode: applied } : current));
    } catch (error) {
      setConfig((current: Config | null) => (current ? { ...current, desktopMode: previous } : current));
      toaster.toast({ title: t("Could not change desktop mode"), body: String(error) });
    }
  }
  const setSleepMode = async (value: string) => {
    const previous = config.sleepMode || "s2idle";
    setConfig((current) => (current ? { ...current, sleepMode: value } : current));
    try {
      const applied = await applySleepMode(value);
      setConfig((current) => (current ? { ...current, sleepMode: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, sleepMode: previous } : current));
      toaster.toast({ title: t("Could not change sleep mode"), body: String(error) });
    }
  };
  return (
    <>
      <PanelSection title={t("Controller")}>
        <SelectEdit
          label={t("Emulation")}
          value={config.controllerType || "deck-uhid"}
          options={(config.controllerTypes || []).map((option) => ({ ...option, label: translateLabel(option.label) }))}
          onChange={setControllerType}
        />
        <ButtonItem layout="below" onClick={openCalibration}>{t("Launch Calibration")}</ButtonItem>
      </PanelSection>
      <PanelSection title={t("System")}>
        <SelectEdit
          label={t("Sleep Mode")}
          value={config.sleepMode || "s2idle"}
          options={(config.sleepModes || []).map((option) => ({ ...option, label: translateLabel(option.label) }))}
          onChange={setSleepMode}
        />
        <ToggleRow label={t("Enable SSH")} value={!!config.sshEnabled} onChange={setSshEnabled} />
        <Field label={t("OS Version")} description={config.osVersion || t("unknown")} />
        <Field label={t("ABL Version")} description={config.ablVersion || t("unknown")} />
      </PanelSection>
      <PanelSection title={t("Experimental")}>
        {config.bottomScreenSupported && (
          <>
            <ToggleRow
              label={t("Bottom Screen")}
              description={t("Run Plasma Mobile on the second display")}
              value={!!config.bottomScreenEnabled}
              onChange={setBottomScreenEnabled}
            />
            {config.bottomScreenBrightnessSupported && (
              <SliderEdit
                label={t("Bottom Screen Brightness")}
                value={config.bottomScreenBrightness}
                min={0}
                max={100}
                step={1}
                onChange={setBottomScreenBrightness}
              />
            )}
          </>
        )}
        {(config.desktopModes?.length || 0) > 1 && (
          <SelectEdit
            label={t("Desktop Mode")}
            value={config.desktopMode || "desktop"}
            options={(config.desktopModes || []).map((option) => ({ ...option, label: translateLabel(option.label) }))}
            onChange={setDesktopMode}
          />
        )}
        <ToggleRow
          label={t("USB File Transfer")}
          description={config.mtpEnabled ? t("Enabled until shutdown") : undefined}
          value={!!config.mtpEnabled}
          onChange={setMtpEnabled}
        />
        <ToggleRow
          label={t("Automatic ABL Updates")}
          description={t("Updates during shutdown")}
          value={!!config.ablAutoEnabled}
          onChange={setAblAutoEnabled}
        />
      </PanelSection>
    </>
  );
}
