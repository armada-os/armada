import { toaster } from "@decky/api";
import { ButtonItem, Field, PanelSection } from "@decky/ui";
import { useEffect, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  setAblAutoEnabled as applyAblAutoEnabled,
  setBottomScreenBrightness as applyBottomScreenBrightness,
  setBottomScreenEnabled as applyBottomScreenEnabled,
  setControllerType as applyControllerType,
  setSoftwareDimEnabled as applySoftwareDimEnabled,
  setSoftwareDimPercent as applySoftwareDimPercent,
  setMtpEnabled as applyMtpEnabled,
  setDesktopMode as applyDesktopMode,
  setSleepMode as applySleepMode,
  setSshEnabled as applySshEnabled,
} from "../backend";
import { openCalibration } from "../components/Calibration";
import { SelectEdit, SliderEdit, ToggleRow } from "../components/widgets";
import type { Config } from "../types";

const BOTTOM_SCREEN_BRIGHTNESS_DELAY_MS: number = 150;
const SOFTWARE_DIM_PERCENT_DELAY_MS: number = 150;

export function Settings({ config, setConfig }: {
  config: Config;
  setConfig: Dispatch<SetStateAction<Config | null>>;
}) {
  const bottomScreenBrightnessTimer = useRef<number | undefined>(undefined);
  const bottomScreenBrightnessRequest = useRef<number>(0);
  const appliedBottomScreenBrightness = useRef<number>(config.bottomScreenBrightness);
  const softwareDimPercentTimer = useRef<number | undefined>(undefined);
  const softwareDimPercentRequest = useRef<number>(0);
  const appliedSoftwareDimPercent = useRef<number>(config.softwareDimPercent);

  useEffect(() => () => {
    window.clearTimeout(bottomScreenBrightnessTimer.current);
    bottomScreenBrightnessRequest.current += 1;
    window.clearTimeout(softwareDimPercentTimer.current);
    softwareDimPercentRequest.current += 1;
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
  const setSoftwareDimEnabled = async (enabled: boolean) => {
    if (enabled === !!config.softwareDimEnabled) {
      return;
    }
    setConfig((current) => (current ? { ...current, softwareDimEnabled: enabled } : current));
    try {
      const applied = await applySoftwareDimEnabled(enabled);
      setConfig((current) => (current ? { ...current, softwareDimEnabled: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, softwareDimEnabled: !enabled } : current));
      toaster.toast({ title: "Could not change software dimming", body: String(error) });
    }
  };
  const setSoftwareDimPercent = (percent: number) => {
    setConfig((current) => (current ? { ...current, softwareDimPercent: percent } : current));
    window.clearTimeout(softwareDimPercentTimer.current);
    const request = ++softwareDimPercentRequest.current;
    softwareDimPercentTimer.current = window.setTimeout(async () => {
      try {
        const applied = await applySoftwareDimPercent(percent);
        if (request !== softwareDimPercentRequest.current) return;
        appliedSoftwareDimPercent.current = applied;
        setConfig((current) => (current ? { ...current, softwareDimPercent: applied } : current));
      } catch (error) {
        if (request !== softwareDimPercentRequest.current) return;
        setConfig((current) => (current ? {
          ...current,
          softwareDimPercent: appliedSoftwareDimPercent.current,
        } : current));
        toaster.toast({ title: "Could not change software dimming range", body: String(error) });
      }
    }, SOFTWARE_DIM_PERCENT_DELAY_MS);
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
      toaster.toast({ title: "Could not change bottom screen", body: String(error) });
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
        toaster.toast({ title: "Could not change bottom-screen brightness", body: String(error) });
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
      toaster.toast({ title: "Could not change desktop mode", body: String(error) });
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
      toaster.toast({ title: "Could not change sleep mode", body: String(error) });
    }
  };
  return (
    <>
      <PanelSection title="Controller">
        <SelectEdit
          label="Emulation"
          value={config.controllerType || "deck-uhid"}
          options={config.controllerTypes || []}
          onChange={setControllerType}
        />
        <ButtonItem layout="below" onClick={openCalibration}>Launch Calibration</ButtonItem>
      </PanelSection>
      <PanelSection title="System">
        <SelectEdit
          label="Sleep Mode"
          value={config.sleepMode || "s2idle"}
          options={config.sleepModes || []}
          onChange={setSleepMode}
        />
        <ToggleRow label="Enable SSH" value={!!config.sshEnabled} onChange={setSshEnabled} />
        <Field label="OS Version" description={config.osVersion || "unknown"} />
        <Field label="ABL Version" description={config.ablVersion || "unknown"} />
      </PanelSection>
      <PanelSection title="Experimental">
        <ToggleRow
          label="Software Dimming"
          description="On some panels, very low hardware brightness causes a visible green tint. This keeps hardware brightness above a safe minimum and uses software dimming to cover the range below it."
          value={!!config.softwareDimEnabled}
          onChange={setSoftwareDimEnabled}
        />
        {!!config.softwareDimEnabled && (
          <SliderEdit
            label="Software Dimming Range"
            value={config.softwareDimPercent}
            min={0}
            max={50}
            step={1}
            onChange={setSoftwareDimPercent}
          />
        )}
        {config.bottomScreenSupported && (
          <>
            <ToggleRow
              label="Bottom Screen"
              description="Run Plasma Mobile on the second display"
              value={!!config.bottomScreenEnabled}
              onChange={setBottomScreenEnabled}
            />
            {config.bottomScreenBrightnessSupported && (
              <SliderEdit
                label="Bottom Screen Brightness"
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
            label="Desktop Mode"
            value={config.desktopMode || "desktop"}
            options={config.desktopModes || []}
            onChange={setDesktopMode}
          />
        )}
        <ToggleRow
          label="USB File Transfer"
          description={config.mtpEnabled ? "Enabled until shutdown" : undefined}
          value={!!config.mtpEnabled}
          onChange={setMtpEnabled}
        />
        <ToggleRow
          label="Automatic ABL Updates"
          description="Updates during shutdown"
          value={!!config.ablAutoEnabled}
          onChange={setAblAutoEnabled}
        />
      </PanelSection>
    </>
  );
}
