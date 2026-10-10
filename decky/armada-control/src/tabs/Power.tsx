import { ButtonItem, PanelSection } from "@decky/ui";
import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { SelectEdit, SliderEdit } from "../components/widgets";
import { t, translateLabel } from "../i18n";
import type { TranslationKey } from "../i18n";
import { clusterRoles, derivedKhz, indexAtMost, isOverclocked, presetKhz } from "../lib/freq";
import { titleCase, update } from "../lib/util";
import type { Config, CpuPolicy, PowerProfile } from "../types";

const policyKey = (policy: CpuPolicy) => `cpu_max_policy${policy.id}` as const;

export function Power({ config, setConfig }: { config: Config; setConfig: Dispatch<SetStateAction<Config | null>> }) {
  const [profile, setProfile] = useState(config.power.general.default_profile || "balanced");
  const p = config.power.profiles[profile] || ({} as PowerProfile);
  const profiles = Object.entries(config.power.profiles || {}).map(([name, profile]) => ({
    data: name,
    label: translateLabel(profile.label || titleCase(name)),
  }));
  const fanCurves = Object.entries(config.power.fan_curves || {}).map(([name, curve]) => ({
    data: name,
    label: translateLabel(curve.label || titleCase(name)),
  }));
  const setProfileValue = (name: string, value: any) => {
    setConfig((current) => (current ? update(current, ["power", "profiles", profile, name], value) : current));
  };
  const defaults = config.powerDefaults?.profiles?.[profile];
  const presets = config.power.underclocks?.[config.cpuDeviceClass];
  const presetClass = !!presets;
  const underclockLevel = (p.cpu_underclock || "").toLowerCase();
  const underclockOptions = [...new Set(["none", ...Object.keys(presets ?? {}), "custom"])].map((level) => ({
    data: level,
    label: translateLabel(titleCase(level)),
  }));
  const cpuPolicies = config.freqLimits?.cpuPolicies ?? [];
  const cpuRoles = clusterRoles(cpuPolicies).map((role) => (/^big\d+$/.test(role) ? t("cpu.bigN", { n: role.slice(3) }) : t(`cpu.${role}` as TranslationKey)));
  const clearedCpuCaps = Object.fromEntries(cpuPolicies.map((policy) => [policyKey(policy), null]));
  const displayKhz = (policy: CpuPolicy, current: PowerProfile) => {
    const preset = presetKhz(presets, current.cpu_underclock || "", policyKey(policy));
    return current[policyKey(policy)] ?? derivedKhz(policy.khz[policy.khz.length - 1], preset, Number(current.cpu_max), presetClass);
  };
  const snappedCpuCaps = (current: PowerProfile) =>
    Object.fromEntries(cpuPolicies.map((policy) => [policyKey(policy), policy.khz[indexAtMost(policy.khz, displayKhz(policy, current))]]));
  const setUnderclock = (level: string) => {
    setConfig((current) => {
      if (!current) return current;
      const currentProfile = current.power.profiles[profile];
      const caps = level === "custom" ? snappedCpuCaps(currentProfile) : clearedCpuCaps;
      return update(current, ["power", "profiles", profile], { ...currentProfile, cpu_underclock: level, ...caps });
    });
  };
  const setCpuMax = (policy: CpuPolicy, index: number) => {
    setConfig((current) => {
      if (!current) return current;
      const currentProfile = current.power.profiles[profile];
      return update(current, ["power", "profiles", profile], { ...currentProfile, ...snappedCpuCaps(currentProfile), [policyKey(policy)]: policy.khz[index], ...(presetClass ? { cpu_underclock: "custom" } : {}) });
    });
  };
  const resetProfile = () => {
    if (!defaults) return;
    const reset = { ...defaults, gpu_max_mhz: null, gpu_min_mhz: null, ...clearedCpuCaps };
    setConfig((current) => (current ? update(current, ["power", "profiles", profile], reset) : current));
  };
  const gpuMhz = config.freqLimits?.gpuMhz ?? [];
  const gpuStockMaxMhz = config.freqLimits?.gpuStockMaxMhz ?? 0;
  const gpuIndex = indexAtMost(gpuMhz, p.gpu_max_mhz ?? defaults?.gpu_max_mhz ?? Infinity);
  const gpuMaxMhz = gpuMhz[gpuIndex];
  const gpuMinIndex = indexAtMost(gpuMhz, p.gpu_min_mhz ?? defaults?.gpu_min_mhz ?? 0);
  const gpuMinMhz = gpuMhz[gpuMinIndex];
  const setGpuMax = (mhz: number) => {
    setConfig((current) => {
      if (!current) return current;
      const currentProfile = current.power.profiles[profile];
      const minMhz = gpuMhz[indexAtMost(gpuMhz, currentProfile.gpu_min_mhz ?? defaults?.gpu_min_mhz ?? 0)];
      return update(current, ["power", "profiles", profile], { ...currentProfile, ...(mhz < minMhz ? { gpu_max_mhz: mhz, gpu_min_mhz: mhz } : { gpu_max_mhz: mhz }) });
    });
  };
  return (
    <>
      <PanelSection title={t("power.editProfile")}>
        <SelectEdit value={profile} options={profiles} onChange={setProfile} />
      </PanelSection>
      <PanelSection title={t("power.profileSettings")}>
        <SelectEdit label={t("power.fanCurve")} value={p.fan_curve} options={fanCurves} onChange={(v) => setProfileValue("fan_curve", v)} />
        {(config.perf?.governors?.length ?? 0) > 0 ? (
          <SelectEdit
            label={t("power.cpuGovernor")}
            value={p.cpu_governor}
            options={config.perf!.governors.map((g) => ({ data: g, label: translateLabel(titleCase(g)) }))}
            onChange={(v) => setProfileValue("cpu_governor", v)}
          />
        ) : null}
        {presetClass ? (
          <SelectEdit label={t("power.cpuUnderclock")} value={underclockLevel} options={underclockOptions} onChange={setUnderclock} />
        ) : null}
        {cpuPolicies.map((policy, i) => {
          const index = indexAtMost(policy.khz, displayKhz(policy, p));
          return (
            <SliderEdit key={policy.id} label={t("power.cpuCluster", { role: cpuRoles[i], cpus: policy.cpus, mhz: policy.mhz[index] })} value={index} min={0} max={policy.khz.length - 1} step={1} showValue={false} onChange={(i) => setCpuMax(policy, i)} />
          );
        })}
        {gpuMhz.length > 0 ? (
          <SliderEdit label={t("power.gpuMin", { mhz: gpuMinMhz })} value={gpuMinIndex} min={0} max={gpuMhz.length - 1} step={1} showValue={false} onChange={(i) => setProfileValue("gpu_min_mhz", Math.min(gpuMhz[i], gpuMaxMhz))} />
        ) : null}
        {gpuMhz.length > 0 ? (
          <SliderEdit
            label={t("power.gpuMax", { mhz: gpuMaxMhz })}
            description={isOverclocked(gpuMaxMhz, gpuStockMaxMhz) ? t("power.gpuOverclocked", { mhz: gpuStockMaxMhz }) : undefined}
            value={gpuIndex}
            min={0}
            max={gpuMhz.length - 1}
            step={1}
            showValue={false}
            onChange={(i) => setGpuMax(gpuMhz[i])}
          />
        ) : null}
        <div className="armada-reset-row">
          <ButtonItem layout="below" onClick={resetProfile}>{t("common.resetToDefault")}</ButtonItem>
        </div>
      </PanelSection>
    </>
  );
}
