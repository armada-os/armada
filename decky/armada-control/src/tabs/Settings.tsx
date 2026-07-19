import { ButtonItem, Field, PanelSection } from "@decky/ui";
import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  setControllerType as applyControllerType,
  setSshEnabled as applySshEnabled,
  setStickLedColor as applyStickLedColor,
  setStickLedFlashColor as applyStickLedFlashColor,
  setStickLedMode as applyStickLedMode,
  setStickLedParam as applyStickLedParam,
  setStickLedScreenLink as applyStickLedScreenLink,
} from "../backend";
import { openCalibration } from "../components/Calibration";
import { SelectEdit, SliderEdit, ToggleRow } from "../components/widgets";
import type { Config } from "../types";

const PRESET_COLORS: { label: string; value: string }[] = [
  { label: "Blue", value: "0050FF" },
  { label: "Purple", value: "8000FF" },
  { label: "Red", value: "FF0000" },
  { label: "Green", value: "00FF00" },
  { label: "White", value: "FFFFFF" },
  { label: "Off", value: "000000" },
];

function hexToRgb(hex: string): [number, number, number] {
  const clean = /^[0-9A-Fa-f]{6}$/.test(hex) ? hex : "0050FF";
  return [parseInt(clean.slice(0, 2), 16), parseInt(clean.slice(2, 4), 16), parseInt(clean.slice(4, 6), 16)];
}
function rgbToHex(r: number, g: number, b: number): string {
  const clamp = (n: number) => Math.max(0, Math.min(255, Math.round(n)));
  return [clamp(r), clamp(g), clamp(b)].map((n) => n.toString(16).padStart(2, "0")).join("").toUpperCase();
}

const MODE_OPTIONS: { data: string; label: string }[] = [
  { data: "static", label: "Static" },
  { data: "breathing", label: "Breathing" },
  { data: "battery", label: "Battery" },
  { data: "battery-breathing", label: "Battery + Breathing" },
  { data: "rainbow", label: "Rainbow" },
  { data: "chase", label: "Chase" },
  { data: "alternating", label: "Alternating (L/R)" },
  { data: "reactive", label: "Reactive (sticks + buttons)" },
  { data: "multidot", label: "Multidot (RGB chase)" },
  { data: "ambilight", label: "Ambilight (matches screen)" },
];
const COLOR_VISIBLE_MODES = new Set(["static", "breathing", "chase", "alternating"]);

const FLASH_BUTTON_OPTIONS: { data: string; label: string }[] = [
  { data: "south", label: "South" },
  { data: "east", label: "East" },
  { data: "north", label: "North" },
  { data: "west", label: "West" },
  { data: "l1", label: "L1" },
  { data: "r1", label: "R1" },
  { data: "l3", label: "L3 (left stick click)" },
  { data: "r3", label: "R3 (right stick click)" },
  { data: "l4", label: "L4 (left paddle)" },
  { data: "r4", label: "R4 (right paddle)" },
  { data: "start", label: "Start" },
  { data: "select", label: "Select" },
  { data: "dpad_up", label: "D-Pad Up" },
  { data: "dpad_down", label: "D-Pad Down" },
  { data: "dpad_left", label: "D-Pad Left" },
  { data: "dpad_right", label: "D-Pad Right" },
  { data: "other", label: "Other buttons" },
];
const DEFAULT_FLASH_COLOR = "FFFFFF";

function aliasMode(mode: string): string {
  return mode === "battery-breathing" ? "breathing" : mode;
}

const PARAM_UI: Record<string, { label: string; min: number; max: number; step: number; modes: Set<string>; toBackend: (v: number) => number; fromBackend: (v: number) => number }> = {
  speed: {
    label: "Speed",
    min: 25,
    max: 300,
    step: 25,
    modes: new Set(["breathing", "chase", "rainbow", "alternating", "multidot", "ambilight"]),
    toBackend: (v) => v / 100,
    fromBackend: (v) => Math.round(v * 100),
  },
  intensity: {
    label: "Intensity (min brightness)",
    min: 0,
    max: 50,
    step: 5,
    modes: new Set(["breathing", "alternating", "chase", "multidot", "reactive"]),
    toBackend: (v) => v / 100,
    fromBackend: (v) => Math.round(v * 100),
  },
  size: {
    label: "Size",
    min: 1,
    max: 3,
    step: 1,
    modes: new Set(["chase", "multidot"]),
    toBackend: (v) => v,
    fromBackend: (v) => v,
  },
};
const PARAM_DEFAULTS: Record<string, number> = { speed: 1.0, intensity: 0.15, size: 2 };

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
  const [colorsExpanded, setColorsExpanded] = useState(false);
  const [flashExpanded, setFlashExpanded] = useState(false);
  const [flashButton, setFlashButton] = useState("south");
  const stickLed = config.stickLed;
  const mode = stickLed?.mode || "static";
  const setStickLedMode = async (nextMode: string) => {
    if (!stickLed) return;
    const previous = stickLed.mode;
    setConfig((current) => (current ? { ...current, stickLed: { ...current.stickLed, mode: nextMode } } : current));
    try {
      const applied = await applyStickLedMode(nextMode);
      setConfig((current) => (current ? { ...current, stickLed: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, stickLed: { ...current.stickLed, mode: previous } } : current));
    }
  };
  const setStickLedScreenLink = async (value: boolean) => {
    if (!stickLed) return;
    const previous = stickLed.screenLink;
    setConfig((current) => (current ? { ...current, stickLed: { ...current.stickLed, screenLink: value } } : current));
    try {
      const applied = await applyStickLedScreenLink(value);
      setConfig((current) => (current ? { ...current, stickLed: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, stickLed: { ...current.stickLed, screenLink: previous } } : current));
    }
  };
  const setStickLedColor = async (hex: string) => {
    if (!stickLed) return;
    const previous = stickLed.color;
    setConfig((current) => (current ? { ...current, stickLed: { ...current.stickLed, mode: "static", color: hex } } : current));
    try {
      const applied = await applyStickLedColor(hex);
      setConfig((current) => (current ? { ...current, stickLed: applied } : current));
    } catch (error) {
      setConfig((current) => (current ? { ...current, stickLed: { ...current.stickLed, color: previous } } : current));
    }
  };
  const setStickLedChannel = (channel: 0 | 1 | 2, value: number) => {
    if (!stickLed) return;
    const rgb = hexToRgb(stickLed.color);
    rgb[channel] = value;
    void setStickLedColor(rgbToHex(rgb[0], rgb[1], rgb[2]));
  };
  const setStickLedFlashColor = async (hex: string) => {
    if (!stickLed) return;
    const previous = stickLed.flashColors[flashButton];
    setConfig((current) =>
      current
        ? { ...current, stickLed: { ...current.stickLed, flashColors: { ...current.stickLed.flashColors, [flashButton]: hex } } }
        : current,
    );
    try {
      const applied = await applyStickLedFlashColor(flashButton, hex);
      setConfig((current) => (current ? { ...current, stickLed: applied } : current));
    } catch (error) {
      setConfig((current) =>
        current
          ? { ...current, stickLed: { ...current.stickLed, flashColors: { ...current.stickLed.flashColors, [flashButton]: previous } } }
          : current,
      );
    }
  };
  const setFlashChannel = (channel: 0 | 1 | 2, value: number) => {
    if (!stickLed) return;
    const rgb = hexToRgb(stickLed.flashColors[flashButton] ?? DEFAULT_FLASH_COLOR);
    rgb[channel] = value;
    void setStickLedFlashColor(rgbToHex(rgb[0], rgb[1], rgb[2]));
  };
  const setStickLedParam = async (param: string, backendValue: number) => {
    if (!stickLed) return;
    const effectiveMode = aliasMode(mode);
    const key = `${param}_${effectiveMode}`;
    const previous = stickLed.params[key];
    setConfig((current) =>
      current ? { ...current, stickLed: { ...current.stickLed, params: { ...current.stickLed.params, [key]: backendValue } } } : current,
    );
    try {
      const applied = await applyStickLedParam(param, effectiveMode, backendValue);
      setConfig((current) => (current ? { ...current, stickLed: applied } : current));
    } catch (error) {
      setConfig((current) =>
        current ? { ...current, stickLed: { ...current.stickLed, params: { ...current.stickLed.params, [key]: previous } } } : current,
      );
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
      {stickLed?.supported && (
        <PanelSection title="Stick Lighting">
          <SelectEdit label="Mode" value={mode} options={MODE_OPTIONS} onChange={setStickLedMode} />
          {Object.entries(PARAM_UI)
            .filter(([, spec]) => spec.modes.has(aliasMode(mode)))
            .map(([param, spec]) => {
              const key = `${param}_${aliasMode(mode)}`;
              const raw = stickLed.params[key] ?? PARAM_DEFAULTS[param];
              return (
                <SliderEdit
                  key={param}
                  label={spec.label}
                  value={spec.fromBackend(raw)}
                  min={spec.min}
                  max={spec.max}
                  step={spec.step}
                  onChange={(value) => setStickLedParam(param, spec.toBackend(value))}
                />
              );
            })}
          <ToggleRow
            label="Follow screen brightness"
            description="Dim the sticks along with the display backlight"
            value={!!stickLed.screenLink}
            onChange={setStickLedScreenLink}
          />
          {COLOR_VISIBLE_MODES.has(mode) && (
            <>
              <ButtonItem layout="below" onClick={() => setColorsExpanded((expanded) => !expanded)}>
                {colorsExpanded ? "Hide colors ▲" : "Show colors ▼"}
              </ButtonItem>
              {colorsExpanded && (
                <>
                  {PRESET_COLORS.map((preset) => (
                    <ButtonItem key={preset.value} layout="below" onClick={() => setStickLedColor(preset.value)}>
                      {preset.label}
                    </ButtonItem>
                  ))}
                  <SliderEdit
                    label="Red"
                    value={hexToRgb(stickLed.color)[0]}
                    min={0}
                    max={255}
                    step={1}
                    onChange={(value) => setStickLedChannel(0, value)}
                  />
                  <SliderEdit
                    label="Green"
                    value={hexToRgb(stickLed.color)[1]}
                    min={0}
                    max={255}
                    step={1}
                    onChange={(value) => setStickLedChannel(1, value)}
                  />
                  <SliderEdit
                    label="Blue"
                    value={hexToRgb(stickLed.color)[2]}
                    min={0}
                    max={255}
                    step={1}
                    onChange={(value) => setStickLedChannel(2, value)}
                  />
                </>
              )}
            </>
          )}
          {mode === "reactive" && (
            <>
              <ButtonItem layout="below" onClick={() => setFlashExpanded((expanded) => !expanded)}>
                {flashExpanded ? "Hide flash colors ▲" : "Show flash colors ▼"}
              </ButtonItem>
              {flashExpanded && (
                <>
                  <SelectEdit label="Button" value={flashButton} options={FLASH_BUTTON_OPTIONS} onChange={setFlashButton} />
                  {PRESET_COLORS.map((preset) => (
                    <ButtonItem key={preset.value} layout="below" onClick={() => setStickLedFlashColor(preset.value)}>
                      {preset.label}
                    </ButtonItem>
                  ))}
                  <SliderEdit
                    label="Red"
                    value={hexToRgb(stickLed.flashColors[flashButton] ?? DEFAULT_FLASH_COLOR)[0]}
                    min={0}
                    max={255}
                    step={1}
                    onChange={(value) => setFlashChannel(0, value)}
                  />
                  <SliderEdit
                    label="Green"
                    value={hexToRgb(stickLed.flashColors[flashButton] ?? DEFAULT_FLASH_COLOR)[1]}
                    min={0}
                    max={255}
                    step={1}
                    onChange={(value) => setFlashChannel(1, value)}
                  />
                  <SliderEdit
                    label="Blue"
                    value={hexToRgb(stickLed.flashColors[flashButton] ?? DEFAULT_FLASH_COLOR)[2]}
                    min={0}
                    max={255}
                    step={1}
                    onChange={(value) => setFlashChannel(2, value)}
                  />
                </>
              )}
            </>
          )}
        </PanelSection>
      )}
      <PanelSection title="System">
        <ToggleRow label="Enable SSH" value={!!config.sshEnabled} onChange={setSshEnabled} />
        <Field label="OS Version" description={config.osVersion || "unknown"} />
      </PanelSection>
    </>
  );
}
