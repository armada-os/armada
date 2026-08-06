import { ButtonItem, Field, PanelSection } from "@decky/ui";
import type { Dispatch, SetStateAction } from "react";
import { setControllerType as applyControllerType, setSshEnabled as applySshEnabled, setVpnEnabled as applyVpnEnabled, setVpnProfile as applyVpnProfile } from "../backend";
import { openCalibration } from "../components/Calibration";
import { openVpnImport } from "../components/VpnImport";
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
  const setVpnEnabled = async (enabled: boolean) => {
    if (enabled === !!config.vpnEnabled) {
      return;
    }
    setConfig((current) => (current ? { ...current, vpnEnabled: enabled } : current));
    try {
      const applied = await applyVpnEnabled(enabled);
      setConfig((current) => (current ? { ...current, vpnEnabled: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, vpnEnabled: !enabled } : current));
    }
  };
  const setVpnProfile = async (value: string) => {
    const previous = config.vpnProfile || "1";
    setConfig((current) => (current ? { ...current, vpnProfile: value } : current));
    try {
      const applied = await applyVpnProfile(value);
      setConfig((current) => (current ? { ...current, vpnProfile: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, vpnProfile: previous } : current));
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
        <ToggleRow label="Enable VPN" value={!!config.vpnEnabled} onChange={setVpnEnabled} />
        <SelectEdit
          label="VPN Profile"
          value={config.vpnProfile || "1"}
          options={[{ data: "1", label: "Profile 1" }, { data: "2", label: "Profile 2" }]}
          onChange={setVpnProfile}
        />
        <ButtonItem layout="below" onClick={() => openVpnImport()}>Import VPN config</ButtonItem>
        <Field label="OS Version" description={config.osVersion || "unknown"} />
        <Field label="ABL Version" description={config.ablVersion || "unknown"} />
      </PanelSection>
    </>
  );
}
