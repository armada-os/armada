import { ButtonItem, Field, PanelSection } from "@decky/ui";
import type { Dispatch, SetStateAction } from "react";
import { setControllerType as applyControllerType, setSshEnabled as applySshEnabled } from "../backend";
import { openCalibration } from "../components/Calibration";
import { SelectEdit, ToggleRow } from "../components/widgets";
import {
  normalizeControllerGlyphStyle,
  supportsControllerButtonStyle,
} from "../lib/controllerGlyphs";
import type { Config } from "../types";

const controllerGlyphStyleOptions = [
  { data: "monochrome", label: "Monochrome" },
  { data: "rainbow", label: "Rainbow" },
];

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
  const controllerGlyphStyle = normalizeControllerGlyphStyle(
    config.tweaks?.global?.controllerGlyphStyle,
  ).toLowerCase();
  const setControllerGlyphStyle = (value: string) => {
    const style = normalizeControllerGlyphStyle(value).toLowerCase() as
      | "monochrome"
      | "rainbow";
    setConfig((current) => {
      if (!current) return current;
      return {
        ...current,
        tweaks: {
          ...current.tweaks,
          global: {
            ...current.tweaks.global,
            controllerGlyphStyle: style,
          },
        },
      };
    });
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
        {supportsControllerButtonStyle(config.controllerGlyphVariant) && (
          <SelectEdit
            label="Controller button style"
            value={controllerGlyphStyle}
            options={controllerGlyphStyleOptions}
            onChange={setControllerGlyphStyle}
          />
        )}
        <ButtonItem layout="below" onClick={openCalibration}>Launch Calibration</ButtonItem>
      </PanelSection>
      <PanelSection title="System">
        <ToggleRow label="Enable SSH" value={!!config.sshEnabled} onChange={setSshEnabled} />
        <Field label="OS Version" description={config.osVersion || "unknown"} />
      </PanelSection>
    </>
  );
}
