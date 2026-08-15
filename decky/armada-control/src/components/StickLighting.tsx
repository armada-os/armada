import { toaster } from "@decky/api";
import { PanelSection } from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { saveLeds as applyLeds } from "../backend";
import { SelectEdit, SliderEdit, ToggleRow } from "./widgets";
import type { Config, LedConfig } from "../types";

const modes = [
  { data: "static", label: "Static" },
  { data: "breathing", label: "Breathing" },
];

// Colours are stored at full value; the brightness slider scales them, so the
// picker only needs hue and saturation.
export function hsToHex(hue: number, saturation: number): string {
  const s = Math.max(0, Math.min(100, saturation)) / 100;
  const h = ((hue % 360) + 360) % 360;
  const c = s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = 1 - c;
  const sector = Math.floor(h / 60) % 6;
  const rgb = [
    [c, x, 0],
    [x, c, 0],
    [0, c, x],
    [0, x, c],
    [x, 0, c],
    [c, 0, x],
  ][sector];
  return rgb.map((part) => Math.round((part + m) * 255).toString(16).padStart(2, "0")).join("");
}

export function hexToHs(hex: string): { hue: number; saturation: number } {
  const text = String(hex || "").replace("#", "");
  if (text.length !== 6) return { hue: 0, saturation: 0 };
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(text.slice(i, i + 2), 16) / 255);
  if ([r, g, b].some((part) => !Number.isFinite(part))) return { hue: 0, saturation: 0 };
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;
  const saturation = max ? Math.round((delta / max) * 100) : 0;
  if (!delta) return { hue: 0, saturation };
  let hue: number;
  if (max === r) hue = 60 * (((g - b) / delta) % 6);
  else if (max === g) hue = 60 * ((b - r) / delta + 2);
  else hue = 60 * ((r - g) / delta + 4);
  return { hue: Math.round(((hue % 360) + 360) % 360), saturation };
}

function ColorRows({ label, color, onChange }: {
  label: string;
  color: string;
  onChange: (hex: string) => void;
}) {
  const { hue, saturation } = hexToHs(color);
  return (
    <>
      <SliderEdit label={`${label} Hue`} value={hue} min={0} max={359} step={1} onChange={(v: number) => onChange(hsToHex(v, saturation))} />
      <SliderEdit label={`${label} Saturation`} value={saturation} min={0} max={100} step={1} onChange={(v: number) => onChange(hsToHex(hue, v))} />
    </>
  );
}

export function StickLighting({ config, setConfig }: {
  config: Config;
  setConfig: Dispatch<SetStateAction<Config | null>>;
}) {
  const leds = config.leds;
  const [linked, setLinked] = useState(leds.left === leds.right);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef<LedConfig | null>(null);

  const flush = () => {
    const next = pending.current;
    pending.current = null;
    if (!next) return;
    applyLeds(next).catch((error) => {
      toaster.toast({ title: "Could not change stick lighting", body: String(error) });
    });
  };

  // Sliders fire continuously; armada-ledd picks the file up within 100 ms, so
  // a short debounce still previews live without hammering the socket.
  const commit = (changes: Partial<LedConfig>) => {
    const next = { ...leds, ...changes };
    setConfig((current) => (current ? { ...current, leds: next } : current));
    pending.current = next;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(flush, 150);
  };

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
    flush();
  }, []);

  const setColor = (side: "left" | "right", hex: string) => {
    commit(linked ? { left: hex, right: hex } : { [side]: hex });
  };

  return (
    <PanelSection title="Stick Lighting">
      <ToggleRow label="Enabled" value={leds.enabled} onChange={(value) => commit({ enabled: value })} />
      {leds.enabled ? (
        <>
          <SelectEdit label="Mode" value={leds.mode} options={modes} onChange={(value: string) => commit({ mode: value })} />
          <SliderEdit label="Brightness" value={leds.brightness} min={0} max={100} step={1} onChange={(v: number) => commit({ brightness: v })} />
          {leds.mode === "breathing" ? (
            <SliderEdit label="Breath Length (s)" value={leds.period} min={1} max={10} step={0.5} onChange={(v: number) => commit({ period: v })} />
          ) : null}
          <ToggleRow
            label="Match Both Sticks"
            value={linked}
            onChange={(value) => {
              setLinked(value);
              if (value) commit({ right: leds.left });
            }}
          />
          <ColorRows label={linked ? "Colour" : "Left"} color={leds.left} onChange={(hex) => setColor("left", hex)} />
          {linked ? null : <ColorRows label="Right" color={leds.right} onChange={(hex) => setColor("right", hex)} />}
        </>
      ) : null}
    </PanelSection>
  );
}
