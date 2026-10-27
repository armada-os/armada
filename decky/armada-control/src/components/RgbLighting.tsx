import { PanelSection } from "@decky/ui";
import { getRgb, setRgb } from "../backend";
import { t } from "../i18n";
import type { RgbConfig } from "../types";
import { SliderEdit, ToggleRow } from "./widgets";
import { useDebouncedApply } from "../hooks/useDebouncedApply";

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

export function RgbLighting({ config, setConfig }: {
  config: RgbConfig;
  setConfig: (next: RgbConfig | null) => void;
}) {
  const update = useDebouncedApply<RgbConfig | null>(
    getRgb,
    setConfig,
    async (next) => next ? setRgb(next.enabled, next.linkBrightness, next.color, next.saturation, next.maxBrightness, next.brightness) : null,
    t("rgb.changeError"),
    UPDATE_INTERVAL_MS,
  );

  return (
    <PanelSection title={t("rgb.title")}>
      <ToggleRow
        label={t("common.enabled")}
        bottomSeparator="standard"
        value={config.enabled}
        onChange={(enabled: boolean) => update({
          ...config,
          enabled,
          linkBrightness: enabled ? config.linkBrightness : false,
        })}
      />
      {config.enabled ? <>
        <ToggleRow
          label={t("rgb.smartBrightness")}
          value={config.linkBrightness}
          onChange={(linkBrightness: boolean) => update({
            ...config,
            linkBrightness,
            maxBrightness: linkBrightness
              ? Math.max(1, config.maxBrightness)
              : config.maxBrightness,
          })}
        />
        <SliderEdit
          label={config.linkBrightness ? t("rgb.maxBrightness") : t("common.brightness")}
          value={config.linkBrightness ? config.maxBrightness : config.brightness}
          min={config.linkBrightness ? 1 : 0}
          max={100}
          step={1}
          onChange={(brightness: number) => update(
            config.linkBrightness ?
              { ...config, maxBrightness: brightness } :
              { ...config, brightness })}
        />
        <SliderEdit
          label={t("common.color")}
          value={colorHue(config.color)}
          min={0}
          max={359}
          step={1}
          showValue={false}
          wrapperClassName="armada-slider-field armada-rgb-hue"
          onChange={(hue: number) => update({ ...config, color: hueColor(hue) })}
        />
        <SliderEdit
          label={t("rgb.saturation")}
          value={config.saturation}
          min={0}
          max={100}
          step={1}
          showValue={false}
          wrapperClassName="armada-slider-field armada-rgb-saturation"
          onChange={(saturation: number) => update({ ...config, saturation })}
        />
      </> : null}
    </PanelSection>
  );
}
