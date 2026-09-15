import { toaster } from "@decky/api";
import { ButtonItem, Field, PanelSection } from "@decky/ui";
import { useEffect, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  setAblAutoEnabled as applyAblAutoEnabled,
  setBottomScreenBrightness as applyBottomScreenBrightness,
  setBottomScreenEnabled as applyBottomScreenEnabled,
  setControllerType as applyControllerType,
  setTrackpadEnabled as applyTrackpadEnabled,
  setTrackpadSettings as applyTrackpadSettings,
  setMtpEnabled as applyMtpEnabled,
  setDesktopMode as applyDesktopMode,
  setSleepMode as applySleepMode,
  setSshEnabled as applySshEnabled,
} from "../backend";
import { openCalibration } from "../components/Calibration";
import { SelectEdit, SliderEdit, ToggleRow } from "../components/widgets";
import type { Config } from "../types";

const BOTTOM_SCREEN_BRIGHTNESS_DELAY_MS: number = 150;
const TRACKPAD_SENSITIVITY_DELAY_MS: number = 150;

export function Settings({ config, setConfig }: {
  config: Config;
  setConfig: Dispatch<SetStateAction<Config | null>>;
}) {
  const bottomScreenBrightnessTimer = useRef<number | undefined>(undefined);
  const bottomScreenBrightnessRequest = useRef<number>(0);
  const appliedBottomScreenBrightness = useRef<number>(config.bottomScreenBrightness);
  const trackpadSensitivityTimer = useRef<number | undefined>(undefined);
  const trackpadSensitivityRequest = useRef<number>(0);
  const appliedTrackpadSensitivity = useRef<number>(config.trackpadSensitivity);

  useEffect(() => () => {
    window.clearTimeout(bottomScreenBrightnessTimer.current);
    bottomScreenBrightnessRequest.current += 1;
    window.clearTimeout(trackpadSensitivityTimer.current);
    trackpadSensitivityRequest.current += 1;
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
  const setTrackpadEnabled = async (enabled: boolean) => {
    if (enabled === !!config.trackpadEnabled) {
      return;
    }
    setConfig((current) => (current ? {
      ...current,
      trackpadEnabled: enabled,
      // The two bottom-screen modes share one DRM-leased connector.
      bottomScreenEnabled: enabled ? false : current.bottomScreenEnabled,
    } : current));
    try {
      const applied = await applyTrackpadEnabled(enabled);
      setConfig((current) => (current ? { ...current, trackpadEnabled: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, trackpadEnabled: !enabled } : current));
      toaster.toast({ title: "Could not change Trackpad", body: String(error) });
    }
  };
  const setTrackpadGlide = async (glide: boolean) => {
    const previous = !!config.trackpadGlide;
    if (glide === previous) {
      return;
    }
    setConfig((current) => (current ? { ...current, trackpadGlide: glide } : current));
    try {
      const applied = await applyTrackpadSettings(config.trackpadSensitivity, glide);
      setConfig((current) => (current ? { ...current, trackpadGlide: applied.glide } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, trackpadGlide: previous } : current));
      toaster.toast({ title: "Could not change Trackpad ball mode", body: String(error) });
    }
  };
  const setTrackpadSensitivity = (sensitivity: number) => {
    setConfig((current) => (current ? { ...current, trackpadSensitivity: sensitivity } : current));
    window.clearTimeout(trackpadSensitivityTimer.current);
    const request = ++trackpadSensitivityRequest.current;
    trackpadSensitivityTimer.current = window.setTimeout(async () => {
      try {
        const applied = await applyTrackpadSettings(sensitivity, !!config.trackpadGlide);
        if (request !== trackpadSensitivityRequest.current) return;
        appliedTrackpadSensitivity.current = applied.sensitivity;
        setConfig((current) => (current ? { ...current, trackpadSensitivity: applied.sensitivity } : current));
      } catch (error) {
        if (request !== trackpadSensitivityRequest.current) return;
        setConfig((current) => (current ? {
          ...current,
          trackpadSensitivity: appliedTrackpadSensitivity.current,
        } : current));
        toaster.toast({ title: "Could not change Trackpad sensitivity", body: String(error) });
      }
    }, TRACKPAD_SENSITIVITY_DELAY_MS);
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
        {config.trackpadSupported && (
          <>
            <ToggleRow
              label="Armada Trackpad"
              description="Use the second display as a touchpad for the top screen"
              value={!!config.trackpadEnabled}
              onChange={setTrackpadEnabled}
            />
            {config.trackpadEnabled && (
              <>
                <ToggleRow
                  label="Ball Mode"
                  description="Cursor keeps gliding after you lift your finger"
                  value={!!config.trackpadGlide}
                  onChange={setTrackpadGlide}
                />
                <SliderEdit
                  label="Trackpad Sensitivity"
                  value={config.trackpadSensitivity}
                  min={0.1}
                  max={5}
                  step={0.1}
                  onChange={setTrackpadSensitivity}
                />
              </>
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
