import { ButtonItem, Field, PanelSection } from "@decky/ui";
import type { Dispatch, SetStateAction } from "react";
import {
  setControllerType as applyControllerType,
  setSshEnabled as applySshEnabled,
  setTouchscreenMode as applyTouchscreenMode,
} from "../backend";
import { openCalibration } from "../components/Calibration";
import { SelectEdit, ToggleRow } from "../components/widgets";
import type { Config } from "../types";

export function Settings({ config, setConfig }: {
  config: Config;
  setConfig: Dispatch<SetStateAction<Config | null>>;
}) {
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
  const setTouchscreenMode = async (enabled: boolean) => {
    const previous = config.touchscreenMode || "direct";
    const value = enabled ? "trackpad" : "direct";
    setConfig((current) => (current ? { ...current, touchscreenMode: value } : current));
    try {
      const applied = await applyTouchscreenMode(value);
      setConfig((current) => (current ? { ...current, touchscreenMode: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, touchscreenMode: previous } : current));
    }
  };
  return (
    <>
      <PanelSection title="Input">
        <ToggleRow
          label="Touchscreen Trackpad"
          description="Move with one finger, tap to left-click, or tap with two fingers to right-click."
          value={config.touchscreenMode === "trackpad"}
          onChange={setTouchscreenMode}
        />
      </PanelSection>
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
        <ToggleRow label="Enable SSH" value={!!config.sshEnabled} onChange={setSshEnabled} />
        <Field label="OS Version" description={config.osVersion || "unknown"} />
      </PanelSection>
    </>
  );
}
