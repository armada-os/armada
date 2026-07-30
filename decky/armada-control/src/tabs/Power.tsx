import { ButtonItem, PanelSection } from "@decky/ui";
import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { setCpuBoostEnabled as applyCpuBoostEnabled } from "../backend";
import { SelectEdit, SliderEdit, ToggleRow } from "../components/widgets";
import { clone, titleCase, update } from "../lib/util";
import type { Config, PowerProfile } from "../types";

const underclocks = [
  { data: "none", label: "None" },
  { data: "small", label: "Small" },
  { data: "medium", label: "Medium" },
  { data: "large", label: "Large" },
];

export function Power({ config, setConfig }: { config: Config; setConfig: Dispatch<SetStateAction<Config | null>> }) {
  const [profile, setProfile] = useState(config.power.general.default_profile || "balanced");
  const p = config.power.profiles[profile] || ({} as PowerProfile);
  const profiles = Object.entries(config.power.profiles || {}).map(([name, profile]) => ({
    data: name,
    label: profile.label || titleCase(name),
  }));
  const fanCurves = Object.entries(config.power.fan_curves || {}).map(([name, curve]) => ({
    data: name,
    label: curve.label || titleCase(name),
  }));
  const setProfileValue = (name: string, value: any) => {
    setConfig((current) => (current ? update(current, ["power", "profiles", profile, name], value) : current));
  };
  const setGpuValue = (name: string, value: any) => {
    setConfig((current) => {
      if (!current) return current;
      const next = clone(current);
      const target: any = next.power.profiles[profile];
      target[name] = value;
      if (name === "gpu_min" && Number(value) > Number(target.gpu_max || 0)) {
        target.gpu_max = value;
      }
      if (name === "gpu_max" && Number(value) < Number(target.gpu_min || 0)) {
        target.gpu_min = value;
      }
      return next;
    });
  };
  const resetProfile = () => {
    const defaults = config.powerDefaults?.profiles?.[profile];
    if (!defaults) return;
    setConfig((current) => (current ? update(current, ["power", "profiles", profile], defaults) : current));
  };
  const setCpuBoostEnabled = async (enabled: boolean) => {
    const previous = !!config.cpuBoost?.enabled;
    if (enabled === previous) return;
    setConfig((current) => (current ? update(current, ["cpuBoost", "enabled"], enabled) : current));
    try {
      const next = await applyCpuBoostEnabled(enabled);
      setConfig(next);
    } catch (error) {
      setConfig((current) => (current ? update(current, ["cpuBoost", "enabled"], previous) : current));
    }
  };
  const underclockLevel = p.cpu_underclock || "";
  const supportsUnderclockPresets = !!config.power.underclocks?.[config.cpuDeviceClass];
  return (
    <>
      <PanelSection title="EDIT POWER PROFILE">
        <SelectEdit value={profile} options={profiles} onChange={setProfile} />
      </PanelSection>
      <PanelSection title="PROFILE SETTINGS">
        <ToggleRow
          label="CPU Turbo Boost"
          value={!!config.cpuBoost?.enabled}
          disabled={!config.cpuBoost?.available}
          description={config.cpuBoost?.available ? "Allow the CPU to use boost frequencies." : "CPU boost control is not available on this device."}
          onChange={setCpuBoostEnabled}
        />
        <SelectEdit label="Fan Curve" value={p.fan_curve} options={fanCurves} onChange={(v) => setProfileValue("fan_curve", v)} />
        {supportsUnderclockPresets ? (
          <SelectEdit label="CPU Underclock" value={underclockLevel} options={underclocks} onChange={(v) => setProfileValue("cpu_underclock", v)} />
        ) : (
          <SliderEdit label="CPU Max (%)" value={Math.round(Number(p.cpu_max || 0) * 100)} min={35} max={100} step={1} onChange={(v) => setProfileValue("cpu_max", (v / 100).toFixed(2))} />
        )}
        <SliderEdit label="GPU Min (%)" value={Math.round(Number(p.gpu_min || 0) * 100)} min={0} max={100} step={1} onChange={(v) => setGpuValue("gpu_min", (v / 100).toFixed(2))} />
        <SliderEdit label="GPU Max (%)" value={Math.round(Number(p.gpu_max || 0) * 100)} min={35} max={100} step={1} onChange={(v) => setGpuValue("gpu_max", (v / 100).toFixed(2))} />
        <div className="armada-reset-row">
          <ButtonItem layout="below" onClick={resetProfile}>Reset to Default</ButtonItem>
        </div>
      </PanelSection>
    </>
  );
}
