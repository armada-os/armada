import { useState } from "react";
import { PanelSection, PanelSectionRow, SliderField, ToggleField } from "@decky/ui";
import type { Config, RgbZone } from "../types";

const COLOR_PRESETS = [
  { name: "Red", r: 255, g: 0, b: 0 },
  { name: "Orange", r: 255, g: 127, b: 0 },
  { name: "Yellow", r: 255, g: 255, b: 0 },
  { name: "Green", r: 0, g: 255, b: 0 },
  { name: "Cyan", r: 0, g: 255, b: 255 },
  { name: "Blue", r: 0, g: 0, b: 255 },
  { name: "Purple", r: 127, g: 0, b: 255 },
  { name: "Magenta", r: 255, g: 0, b: 255 },
  { name: "White", r: 255, g: 255, b: 255 },
];

const getNormalizedColor = (r: number, g: number, b: number) => {
  const max = Math.max(r, g, b, 1);
  const multiplier = 255 / max;
  return `rgb(${Math.round(r * multiplier)}, ${Math.round(g * multiplier)}, ${Math.round(b * multiplier)})`;
};

const ZoneControls = ({
  zone,
  title,
  data,
  updateZone
}: {
  zone: "left" | "right";
  title: string;
  data: RgbZone;
  updateZone: (zone: "left" | "right", updates: Partial<RgbZone>) => void;
}) => {
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <PanelSection title={title}>
      <PanelSectionRow>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontSize: '16px' }}>Color Preview</div>
            <div style={{
              width: '80px',
              height: '24px',
              borderRadius: '4px',
              backgroundColor: getNormalizedColor(data.r, data.g, data.b),
              boxShadow: '0 0 5px rgba(0,0,0,0.5)',
              border: '1px solid rgba(255,255,255,0.2)'
            }} />
          </div>
          
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '10px' }}>
            {COLOR_PRESETS.map(preset => {
              const isSelected = data.r === preset.r && data.g === preset.g && data.b === preset.b;
              return (
                <div
                  key={preset.name}
                  onClick={() => updateZone(zone, { r: preset.r, g: preset.g, b: preset.b })}
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    backgroundColor: `rgb(${preset.r}, ${preset.g}, ${preset.b})`,
                    cursor: 'pointer',
                    border: isSelected ? '2px solid white' : '2px solid transparent',
                    boxShadow: isSelected ? '0 0 8px rgba(255,255,255,0.6)' : '0 2px 4px rgba(0,0,0,0.3)',
                    transition: 'all 0.2s'
                  }}
                  title={preset.name}
                />
              );
            })}
          </div>
        </div>
      </PanelSectionRow>
      
      <PanelSectionRow>
        <SliderField
          label="Brightness"
          value={data.brightness}
          min={0}
          max={255}
          step={1}
          onChange={(val) => updateZone(zone, { brightness: val })}
        />
      </PanelSectionRow>

      <PanelSectionRow>
        <ToggleField
          label="Advanced RGB Controls"
          checked={showAdvanced}
          onChange={setShowAdvanced}
        />
      </PanelSectionRow>

      {showAdvanced && (
        <>
          <PanelSectionRow>
            <SliderField
              label="Red"
              value={data.r}
              min={0}
              max={255}
              step={1}
              onChange={(val) => updateZone(zone, { r: val })}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <SliderField
              label="Green"
              value={data.g}
              min={0}
              max={255}
              step={1}
              onChange={(val) => updateZone(zone, { g: val })}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <SliderField
              label="Blue"
              value={data.b}
              min={0}
              max={255}
              step={1}
              onChange={(val) => updateZone(zone, { b: val })}
            />
          </PanelSectionRow>
        </>
      )}
    </PanelSection>
  );
};

export function Rgb({ config, setConfig }: { config: Config; setConfig: (cb: (current: Config | null) => Config | null) => void }) {
  const rgb = config.rgb || {
    enabled: true,
    sync: true,
    left: { r: 255, g: 255, b: 255, brightness: 255 },
    right: { r: 255, g: 255, b: 255, brightness: 255 }
  };

  const updateRgb = (updates: Partial<typeof rgb>) => {
    setConfig((current) => {
      if (!current) return current;
      return { ...current, rgb: { ...current.rgb, ...updates } };
    });
  };

  const updateZone = (zone: "left" | "right", updates: Partial<RgbZone>) => {
    setConfig((current) => {
      if (!current) return current;
      const nextRgb = {
        ...current.rgb,
        [zone]: { ...current.rgb[zone], ...updates },
      };
      
      // If sync is enabled and we're updating the left zone, mirror it to the right zone.
      if (current.rgb.sync && zone === "left") {
        nextRgb.right = { ...nextRgb.left };
      }
      return { ...current, rgb: nextRgb };
    });
  };

  return (
    <>
      <PanelSection title="RGB Settings">
        <PanelSectionRow>
          <ToggleField
            label="Enable RGB"
            checked={rgb.enabled}
            onChange={(val) => updateRgb({ enabled: val })}
          />
        </PanelSectionRow>
        {rgb.enabled && (
          <PanelSectionRow>
            <ToggleField
              label="Sync Left and Right"
              checked={rgb.sync}
              onChange={(val) => {
                if (val) {
                  // When enabling sync, immediately copy left to right
                  setConfig((current) => {
                    if (!current) return current;
                    return {
                      ...current,
                      rgb: {
                        ...current.rgb,
                        sync: true,
                        right: { ...current.rgb.left },
                      },
                    };
                  });
                } else {
                  updateRgb({ sync: false });
                }
              }}
            />
          </PanelSectionRow>
        )}
      </PanelSection>

      {rgb.enabled && (
        <>
          <ZoneControls zone="left" title={rgb.sync ? "Color Controls" : "Left Zone"} data={rgb.left} updateZone={updateZone} />
          {!rgb.sync && <ZoneControls zone="right" title="Right Zone" data={rgb.right} updateZone={updateZone} />}
        </>
      )}
    </>
  );
}
