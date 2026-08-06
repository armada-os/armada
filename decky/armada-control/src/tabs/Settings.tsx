import { ButtonItem, Field, PanelSection } from "@decky/ui";
import type { Dispatch, SetStateAction } from "react";
import {
  setButtonLayout as saveButtonLayout,
  setControllerType as applyControllerType,
  setSshEnabled as applySshEnabled,
} from "../backend";
import { openCalibration } from "../components/Calibration";
import { SelectEdit, ToggleRow } from "../components/widgets";
import {
  applySteamButtonLayout,
  beginSteamControllerTypeChange,
  restoreSteamControllerType,
} from "../lib/steamButtonLayout";
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
    if (value === previous) {
      return;
    }
    setConfig((current) => (current ? { ...current, controllerType: value } : current));
    beginSteamControllerTypeChange(value);
    try {
      const applied = await applyControllerType(value);
      setConfig((current) => (current ? { ...current, controllerType: applied } : current));
    } catch (error) {
      restoreSteamControllerType(previous);
      setConfig((current) => (current ? { ...current, controllerType: previous } : current));
    }
  };
  const setButtonLayout = async (value: string) => {
    const previous = config.buttonLayout || "auto";
    setConfig((current) => (current ? { ...current, buttonLayout: value } : current));
    try {
      const applied = await saveButtonLayout(value);
      applySteamButtonLayout(applied.resolved);
      setConfig((current) => (current ? {
        ...current,
        buttonLayout: applied.value,
        resolvedButtonLayout: applied.resolved,
      } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, buttonLayout: previous } : current));
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
        <SelectEdit
          label="Button layout"
          value={config.buttonLayout || "auto"}
          options={config.buttonLayouts || []}
          onChange={setButtonLayout}
        />
        <ButtonItem layout="below" onClick={openCalibration}>Launch Calibration</ButtonItem>
      </PanelSection>
      <PanelSection title="System">
        <ToggleRow label="Enable SSH" value={!!config.sshEnabled} onChange={setSshEnabled} />
        <Field label="OS Version" description={config.osVersion || "unknown"} />
        <Field label="ABL Version" description={config.ablVersion || "unknown"} />
      </PanelSection>
    </>
  );
}
