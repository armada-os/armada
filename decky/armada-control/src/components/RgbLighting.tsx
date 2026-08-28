import { toaster } from "@decky/api";
import { PanelSection } from "@decky/ui";
import { useCallback, useEffect, useRef, useState } from "react";
import { getRgb, setRgb } from "../backend";
import type { RgbConfig } from "../types";
import { SliderEdit, ToggleRow } from "./widgets";

const UPDATE_INTERVAL_MS: number = 100;

function colorHue(color: string): number {
  const red: number = Number.parseInt(color.slice(0, 2), 16) / 255;
  const green: number = Number.parseInt(color.slice(2, 4), 16) / 255;
  const blue: number = Number.parseInt(color.slice(4, 6), 16) / 255;
  const maximum: number = Math.max(red, green, blue);
  const difference: number = maximum - Math.min(red, green, blue);

  if (difference === 0) return 0;

  let hue: number;
  if (maximum === red) hue = (green - blue) / difference;
  else if (maximum === green) hue = 2 + (blue - red) / difference;
  else hue = 4 + (red - green) / difference;

  return Math.round((hue * 60 + 360) % 360);
}

function hexChannel(value: number): string {
  return Math.round(value).toString(16).padStart(2, "0").toUpperCase();
}

function hueColor(hue: number): string {
  const normalizedHue: number = hue % 360;
  const section: number = Math.floor(normalizedHue / 60);
  const value: number = ((normalizedHue % 60) / 60) * 255;
  const rising: string = hexChannel(value);
  const falling: string = hexChannel(255 - value);

  switch (section) {
    case 0: return `FF${rising}00`;
    case 1: return `${falling}FF00`;
    case 2: return `00FF${rising}`;
    case 3: return `00${falling}FF`;
    case 4: return `${rising}00FF`;
    default: return `FF00${falling}`;
  }
}

export function RgbLighting() {
  const [config, setConfig] = useState<RgbConfig | null>(null);
  const savedConfig = useRef<string>("");
  const lastUpdate = useRef<number>(0);

  const load = useCallback(async () => {
    try {
      const next: RgbConfig | null = await getRgb();
      savedConfig.current = JSON.stringify(next);
      setConfig(next);
    } catch (error) {
      toaster.toast({ title: "Could not load RGB lighting", body: String(error) });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!config) return;
    const current: string = JSON.stringify(config);
    if (current === savedConfig.current) return;

    const elapsed: number = Date.now() - lastUpdate.current;
    const delay: number = Math.max(0, UPDATE_INTERVAL_MS - elapsed);
    const timer: number = window.setTimeout(async () => {
      lastUpdate.current = Date.now();
      try {
        await setRgb(config.enabled, config.color, config.brightness);
        savedConfig.current = current;
      } catch (error) {
        toaster.toast({ title: "Could not change RGB lighting", body: String(error) });
        load();
      }
    }, delay);

    return () => window.clearTimeout(timer);
  }, [config, load]);

  if (!config) return null;

  return (
    <PanelSection title="RGB Lighting">
      <ToggleRow
        label="Enabled"
        value={config.enabled}
        onChange={(enabled: boolean) => setConfig({ ...config, enabled })}
      />
      <SliderEdit
        label="Brightness"
        value={config.brightness}
        min={0}
        max={100}
        step={1}
        disabled={!config.enabled}
        onChange={(brightness: number) => setConfig({ ...config, brightness })}
      />
      <SliderEdit
        label="Color"
        value={colorHue(config.color)}
        min={0}
        max={359}
        step={1}
        disabled={!config.enabled}
        showValue={false}
        wrapperClassName="armada-slider-field armada-rgb-hue"
        onChange={(hue: number) => setConfig({ ...config, color: hueColor(hue) })}
      />
    </PanelSection>
  );
}
