import { ButtonItem, Field, Focusable, PanelSection, PanelSectionRow, SliderField, ToggleField } from "@decky/ui";
import React, { useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { saveRGBConfig } from "../backend";
import { SelectEdit } from "../components/widgets";
import { update } from "../lib/util";
import type { Config, RGBConfig } from "../types";

export interface PresetColor {
  name: string;
  rgb: [number, number, number];
  hex: string;
}

const PRESET_COLORS: PresetColor[] = [
  { name: "Cyber Cyan", rgb: [0, 255, 255], hex: "#00ffff" },
  { name: "Neon Purple", rgb: [255, 0, 255], hex: "#ff00ff" },
  { name: "Ice Blue", rgb: [0, 180, 255], hex: "#00b4ff" },
  { name: "Electric Blue", rgb: [0, 50, 255], hex: "#0032ff" },
  { name: "Emerald Green", rgb: [0, 255, 60], hex: "#00ff3c" },
  { name: "Sunset Orange", rgb: [255, 100, 0], hex: "#ff6400" },
  { name: "Solar Yellow", rgb: [255, 255, 0], hex: "#ffff00" },
  { name: "Ruby Red", rgb: [255, 0, 40], hex: "#ff0028" },
  { name: "Sakura Pink", rgb: [255, 50, 160], hex: "#ff32a0" },
  { name: "Pure White", rgb: [255, 255, 255], hex: "#ffffff" },
];

const effectOptions = [
  { data: "static", label: "Solid Color" },
  { data: "breathing", label: "Breathing Glow" },
  { data: "rainbow", label: "Rainbow Spectrum" },
  { data: "battery", label: "Battery Level Gauge" },
  { data: "temp", label: "CPU Temperature Glow" },
];

const zoneOptions = [
  { data: "synced", label: "All Zones (Synced)" },
  { data: "split", label: "Separate (Sticks / Sides)" },
];

export function RGB({ config, setConfig }: { config: Config; setConfig: Dispatch<SetStateAction<Config | null>> }) {
  const rgb: RGBConfig = config.rgb || {
    enabled: true,
    brightness: 255,
    effect: "static",
    speed: 5,
    color: [0, 255, 255],
    sync_zones: true,
    sticks_color: [0, 255, 255],
    sides_color: [255, 0, 255],
    sleep_off: true,
  };

  const [activeZone, setActiveZone] = useState<"all" | "sticks" | "sides">("all");
  const [showCustomSliders, setShowCustomSliders] = useState(false);
  const pendingSave = useRef<number | null>(null);

  const applyAndSave = (nextRgb: RGBConfig, immediate: boolean = true) => {
    setConfig((current) => (current ? update(current, ["rgb"], nextRgb) : current));

    if (immediate) {
      if (pendingSave.current) {
        window.clearTimeout(pendingSave.current);
        pendingSave.current = null;
      }
      saveRGBConfig(nextRgb).catch(() => {});
    } else {
      if (pendingSave.current) {
        window.clearTimeout(pendingSave.current);
      }
      pendingSave.current = window.setTimeout(() => {
        saveRGBConfig(nextRgb).catch(() => {});
        pendingSave.current = null;
      }, 50); // fast 50ms throttle for smooth slider dragging
    }
  };

  const setRgbValue = (key: keyof RGBConfig, val: any, immediate: boolean = true) => {
    const nextRgb = { ...rgb, [key]: val };
    applyAndSave(nextRgb, immediate);
  };

  const currentActiveColor: [number, number, number] =
    activeZone === "sticks"
      ? rgb.sticks_color || rgb.color
      : activeZone === "sides"
      ? rgb.sides_color || rgb.color
      : rgb.color || [0, 255, 255];

  const handleColorChange = (newRgb: [number, number, number], immediate: boolean = true) => {
    let nextRgb = { ...rgb };
    if (activeZone === "sticks") {
      nextRgb.sticks_color = newRgb;
    } else if (activeZone === "sides") {
      nextRgb.sides_color = newRgb;
    } else {
      nextRgb.color = newRgb;
      nextRgb.sticks_color = newRgb;
      nextRgb.sides_color = newRgb;
    }
    applyAndSave(nextRgb, immediate);
  };

  const brightnessPercent = Math.round((rgb.brightness / 255) * 100);

  const isColorSelected = (preset: PresetColor) => {
    return (
      Math.abs(preset.rgb[0] - currentActiveColor[0]) < 10 &&
      Math.abs(preset.rgb[1] - currentActiveColor[1]) < 10 &&
      Math.abs(preset.rgb[2] - currentActiveColor[2]) < 10
    );
  };

  return (
    <>
      <PanelSection title="MASTER CONTROLS">
        <PanelSectionRow>
          <ToggleField
            label="Enable RGB Lighting"
            description="Toggle all LEDs on device"
            checked={rgb.enabled}
            onChange={(v) => setRgbValue("enabled", v, true)}
          />
        </PanelSectionRow>

        {rgb.enabled && (
          <PanelSectionRow>
            <SliderField
              label={`Brightness (${brightnessPercent}%)`}
              value={rgb.brightness}
              min={5}
              max={255}
              step={5}
              showValue
              onChange={(v) => setRgbValue("brightness", v, false)}
            />
          </PanelSectionRow>
        )}
      </PanelSection>

      {rgb.enabled && (
        <>
          <PanelSection title="LIGHTING EFFECT">
            <SelectEdit
              label="Effect Mode"
              value={rgb.effect}
              options={effectOptions}
              onChange={(v) => setRgbValue("effect", v, true)}
            />

            {(rgb.effect === "breathing" || rgb.effect === "rainbow") && (
              <PanelSectionRow>
                <SliderField
                  label="Animation Speed"
                  value={rgb.speed || 5}
                  min={1}
                  max={10}
                  step={1}
                  showValue
                  onChange={(v) => setRgbValue("speed", v, false)}
                />
              </PanelSectionRow>
            )}

            {rgb.effect === "battery" && (
              <PanelSectionRow>
                <Field
                  label="Battery Dynamic"
                  description=">60% Green | 25-60% Amber | <25% Pulsing Red Alert"
                />
              </PanelSectionRow>
            )}

            {rgb.effect === "temp" && (
              <PanelSectionRow>
                <Field
                  label="Thermal Dynamic"
                  description="<45°C Cyan | 45-65°C Amber | >65°C Red Hot"
                />
              </PanelSectionRow>
            )}
          </PanelSection>

          {(rgb.effect === "static" || rgb.effect === "breathing") && (
            <PanelSection title="COLOR CUSTOMIZATION">
              <SelectEdit
                label="LED Zone Layout"
                value={rgb.sync_zones ? "synced" : "split"}
                options={zoneOptions}
                onChange={(v) => {
                  const sync = v === "synced";
                  const nextRgb = { ...rgb, sync_zones: sync };
                  setActiveZone(sync ? "all" : "sticks");
                  applyAndSave(nextRgb, true);
                }}
              />

              {!rgb.sync_zones && (
                <PanelSectionRow>
                  <div style={{ display: "flex", gap: "8px", margin: "4px 0 8px 0", width: "100%" }}>
                    <button
                      style={{
                        flex: 1,
                        padding: "8px 4px",
                        borderRadius: "6px",
                        border: activeZone === "sticks" ? "2px solid #1a9fff" : "1px solid rgba(255,255,255,0.15)",
                        backgroundColor: activeZone === "sticks" ? "rgba(26, 159, 255, 0.25)" : "rgba(255,255,255,0.06)",
                        color: "#fff",
                        fontWeight: "bold",
                        fontSize: "12px",
                        cursor: "pointer",
                      }}
                      onClick={() => setActiveZone("sticks")}
                    >
                      🕹️ Joysticks
                    </button>
                    <button
                      style={{
                        flex: 1,
                        padding: "8px 4px",
                        borderRadius: "6px",
                        border: activeZone === "sides" ? "2px solid #1a9fff" : "1px solid rgba(255,255,255,0.15)",
                        backgroundColor: activeZone === "sides" ? "rgba(26, 159, 255, 0.25)" : "rgba(255,255,255,0.06)",
                        color: "#fff",
                        fontWeight: "bold",
                        fontSize: "12px",
                        cursor: "pointer",
                      }}
                      onClick={() => setActiveZone("sides")}
                    >
                      💡 Side Grips
                    </button>
                  </div>
                </PanelSectionRow>
              )}

              <PanelSectionRow>
                <div style={{ width: "100%" }}>
                  {showCustomSliders ? (
                    <div>
                      <div
                        style={{
                          height: "28px",
                          borderRadius: "6px",
                          backgroundColor: `rgb(${currentActiveColor.join(",")})`,
                          boxShadow: `0 0 12px rgba(${currentActiveColor.join(",")}, 0.6)`,
                          marginBottom: "12px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: "#fff",
                          fontWeight: "bold",
                          textShadow: "0 1px 3px rgba(0,0,0,0.8)",
                          fontSize: "12px",
                        }}
                      >
                        {`#${currentActiveColor.map((c) => c.toString(16).padStart(2, "0")).join("")}`}
                      </div>
                      <SliderField
                        label={`Red (${currentActiveColor[0]})`}
                        value={currentActiveColor[0]}
                        min={0}
                        max={255}
                        step={1}
                        onChange={(r) => handleColorChange([r, currentActiveColor[1], currentActiveColor[2]], false)}
                      />
                      <SliderField
                        label={`Green (${currentActiveColor[1]})`}
                        value={currentActiveColor[1]}
                        min={0}
                        max={255}
                        step={1}
                        onChange={(g) => handleColorChange([currentActiveColor[0], g, currentActiveColor[2]], false)}
                      />
                      <SliderField
                        label={`Blue (${currentActiveColor[2]})`}
                        value={currentActiveColor[2]}
                        min={0}
                        max={255}
                        step={1}
                        onChange={(b) => handleColorChange([currentActiveColor[0], currentActiveColor[1], b], false)}
                      />
                    </div>
                  ) : (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(5, 1fr)",
                        gap: "6px",
                        padding: "4px 0",
                        width: "100%",
                      }}
                    >
                      {PRESET_COLORS.map((preset) => {
                        const selected = isColorSelected(preset);
                        return (
                          <Focusable
                            key={preset.name}
                            onClick={() => handleColorChange(preset.rgb, true)}
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              alignItems: "center",
                              justifyContent: "center",
                              padding: "6px 2px",
                              borderRadius: "8px",
                              backgroundColor: selected ? "rgba(255, 255, 255, 0.18)" : "rgba(255, 255, 255, 0.05)",
                              border: selected ? `2px solid ${preset.hex}` : "1px solid rgba(255, 255, 255, 0.1)",
                              cursor: "pointer",
                            }}
                          >
                            <div
                              style={{
                                width: "18px",
                                height: "18px",
                                borderRadius: "50%",
                                backgroundColor: preset.hex,
                                boxShadow: selected ? `0 0 8px ${preset.hex}` : "none",
                                marginBottom: "3px",
                              }}
                            />
                            <span
                              style={{
                                fontSize: "9px",
                                color: selected ? "#fff" : "#aaa",
                                fontWeight: selected ? "bold" : "normal",
                                textAlign: "center",
                                lineHeight: "1.1",
                              }}
                            >
                              {preset.name.split(" ")[0]}
                            </span>
                          </Focusable>
                        );
                      })}
                    </div>
                  )}
                </div>
              </PanelSectionRow>

              <PanelSectionRow>
                <ButtonItem layout="below" onClick={() => setShowCustomSliders(!showCustomSliders)}>
                  {showCustomSliders ? "Switch to Color Presets" : "Open Custom RGB Sliders"}
                </ButtonItem>
              </PanelSectionRow>
            </PanelSection>
          )}

          <PanelSection title="POWER & HARDWARE">
            <PanelSectionRow>
              <ToggleField
                label="Turn Off In Sleep Mode"
                description="Conserves battery when system is suspended"
                checked={rgb.sleep_off}
                onChange={(v) => setRgbValue("sleep_off", v, true)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <Field
                label="Detected LED Hardware"
                description={rgb.zones && rgb.zones.length > 0 ? rgb.zones.join(", ") : "Standard Multi-Color Hardware"}
              />
            </PanelSectionRow>
          </PanelSection>
        </>
      )}
    </>
  );
}
