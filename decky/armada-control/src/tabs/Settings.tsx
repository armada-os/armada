import { ButtonItem, Field, PanelSection } from "@decky/ui";
import type { Dispatch, SetStateAction } from "react";
import {
  setAblAutoEnabled as applyAblAutoEnabled,
  setControllerType as applyControllerType,
  setMtpEnabled as applyMtpEnabled,
  setSshEnabled as applySshEnabled,
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
        <ToggleRow label="Enable SSH" value={!!config.sshEnabled} onChange={setSshEnabled} />
        <Field label="OS Version" description={config.osVersion || "unknown"} />
        <Field label="ABL Version" description={config.ablVersion || "unknown"} />
      </PanelSection>
      <PanelSection title="Experimental">
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
