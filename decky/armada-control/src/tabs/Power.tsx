import { DialogBody, DialogButton, DialogButtonPrimary, DialogControlsSection, DialogControlsSectionHeader, Dropdown, Field, SliderField } from "@decky/ui";
import { useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { savePowerProfile } from "../backend";
import { ArmadaDialogFooter, ArmadaDialogHeader, ArmadaModalRoot } from "../components/ArmadaModalRoot";
import { t, translateLabel } from "../i18n";
import type { TranslationKey } from "../i18n";
import { clusterRoles, derivedKhz, indexAtMost, isOverclocked, presetKhz } from "../lib/freq";
import { markConfigFieldChange } from "../lib/configMutation";
import { clone, titleCase } from "../lib/util";
import type { Config, CpuPolicy, FullConfig, PowerProfile, ProfilesConfig } from "../types";

const policyKey = (policy: CpuPolicy) => `cpu_max_policy${policy.id}` as const;

export function PowerProfileEditorModal({ profileId, getLatestConfig, setConfig, onSaved, closeModal }: {
  profileId: string;
  getLatestConfig: () => Config & ProfilesConfig;
  setConfig: Dispatch<SetStateAction<Config | null>>;
  onSaved: (next: FullConfig) => void;
  closeModal?: () => void;
}) {
  const [initial] = useState(() => clone(getLatestConfig()));
  const [profile, setProfile] = useState(() => clone(initial.power.profiles[profileId]));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const busy = useRef(false);
  const dirty = JSON.stringify(profile) !== JSON.stringify(initial.power.profiles[profileId]);
  const fanCurves = Object.entries(initial.power.fan_curves).map(([data, curve]) => ({ data, label: translateLabel(curve.label || titleCase(data)) }));
  const defaults = initial.powerDefaults?.profiles[profileId];
  const presets = initial.power.underclocks?.[initial.cpuDeviceClass];
  const presetClass = !!presets;
  const underclockOptions = [...new Set(["none", ...Object.keys(presets ?? {}), "custom"])].map((data) => ({ data, label: translateLabel(titleCase(data)) }));
  const cpuPolicies = initial.freqLimits?.cpuPolicies ?? [];
  const cpuRoles = clusterRoles(cpuPolicies, initial.freqLimits?.cpuTopology).map((role) => (/^big\d+$/.test(role) ? t("cpu.bigN", { n: role.slice(3) }) : t(`cpu.${role}` as TranslationKey)));
  const clearedCpuCaps = Object.fromEntries(cpuPolicies.map((policy) => [policyKey(policy), null]));
  const displayKhz = (policy: CpuPolicy, current: PowerProfile) => {
    const preset = presetKhz(presets, current.cpu_underclock || "", policyKey(policy));
    return current[policyKey(policy)] ?? derivedKhz(policy.khz[policy.khz.length - 1], preset, Number(current.cpu_max), presetClass);
  };
  const snappedCpuCaps = (current: PowerProfile) =>
    Object.fromEntries(cpuPolicies.map((policy) => [policyKey(policy), policy.khz[indexAtMost(policy.khz, displayKhz(policy, current))]]));
  const setValue = (key: keyof PowerProfile, value: string | number) => {
    if (!busy.current) setProfile((current) => ({ ...current, [key]: value }));
  };
  const setUnderclock = (level: string) => {
    if (busy.current) return;
    setProfile((current) => ({ ...current, cpu_underclock: level, ...(level === "custom" ? snappedCpuCaps(current) : clearedCpuCaps) }));
  };
  const setCpuMax = (policy: CpuPolicy, index: number) => {
    if (busy.current) return;
    setProfile((current) => ({ ...current, ...snappedCpuCaps(current), [policyKey(policy)]: policy.khz[index], ...(presetClass ? { cpu_underclock: "custom" } : {}) }));
  };
  const resetProfile = () => {
    if (busy.current || !defaults) return;
    setProfile({ ...clone(defaults), gpu_max_mhz: null, gpu_min_mhz: null, ...clearedCpuCaps });
  };
  const gpuMhz = initial.freqLimits?.gpuMhz ?? [];
  const gpuStockMaxMhz = initial.freqLimits?.gpuStockMaxMhz ?? 0;
  const gpuIndex = indexAtMost(gpuMhz, profile.gpu_max_mhz ?? defaults?.gpu_max_mhz ?? Infinity);
  const gpuMaxMhz = gpuMhz[gpuIndex];
  const gpuMinIndex = indexAtMost(gpuMhz, profile.gpu_min_mhz ?? defaults?.gpu_min_mhz ?? 0);
  const gpuMinMhz = gpuMhz[gpuMinIndex];
  const setGpuMax = (mhz: number) => {
    if (busy.current) return;
    setProfile((current) => {
      const minMhz = gpuMhz[indexAtMost(gpuMhz, current.gpu_min_mhz ?? defaults?.gpu_min_mhz ?? 0)];
      return { ...current, gpu_max_mhz: mhz, ...(mhz < minMhz ? { gpu_min_mhz: mhz } : {}) };
    });
  };
  const cancel = () => { if (!busy.current) closeModal?.(); };
  const save = async () => {
    if (busy.current) return;
    busy.current = true;
    setSaving(true);
    setError("");
    markConfigFieldChange(setConfig, "power");
    try {
      const next = await savePowerProfile(profileId, clone(profile));
      setConfig((current) => current?.power ? {
        ...current,
        power: { ...current.power, profiles: { ...current.power.profiles, [profileId]: next.power.profiles[profileId] } },
      } : current);
      onSaved(next);
      closeModal?.();
    } catch (error) {
      setError(String(error));
    } finally {
      busy.current = false;
      setSaving(false);
    }
  };

  return <ArmadaModalRoot bAllowFullSize bDisableBackgroundDismiss={saving} bCancelDisabled={saving} onCancel={cancel}>
    <ArmadaDialogHeader>{t("profiles.editPerformance", { profile: translateLabel(profile.label || titleCase(profileId)) })}</ArmadaDialogHeader>
    <DialogBody className="afc-scope">
      {error ? <div className="afc-error" role="alert">{error}</div> : null}
      <DialogControlsSection>
        <DialogControlsSectionHeader>{t("profiles.cpuSettings")}</DialogControlsSectionHeader>
        {initial.perf?.governors?.length ? <Field label={t("power.cpuGovernor")} bottomSeparator="standard" childrenLayout="below">
          <Dropdown selectedOption={profile.cpu_governor} rgOptions={initial.perf.governors.map((data) => ({ data, label: translateLabel(titleCase(data)) }))} disabled={saving} onChange={(option) => setValue("cpu_governor", String(option.data))} />
        </Field> : null}
        {presetClass ? <Field label={t("power.cpuUnderclock")} bottomSeparator="standard" childrenLayout="below">
          <Dropdown selectedOption={(profile.cpu_underclock || "").toLowerCase()} rgOptions={underclockOptions} disabled={saving} onChange={(option) => setUnderclock(String(option.data))} />
        </Field> : null}
        {cpuPolicies.map((policy, i) => {
          const index = indexAtMost(policy.khz, displayKhz(policy, profile));
          return <SliderField key={policy.id} label={t("power.cpuCluster", { role: cpuRoles[i], cpus: policy.cpus, mhz: policy.mhz[index] })} value={index} min={0} max={policy.khz.length - 1} step={1} showValue={false} disabled={saving} onChange={(index) => setCpuMax(policy, index)} />;
        })}
      </DialogControlsSection>
      <DialogControlsSection>
        <DialogControlsSectionHeader>{t("profiles.gpuSettings")}</DialogControlsSectionHeader>
        {gpuMhz.length ? <>
          <SliderField label={t("power.gpuMin", { mhz: gpuMinMhz })} value={gpuMinIndex} min={0} max={gpuMhz.length - 1} step={1} showValue={false} disabled={saving} onChange={(index) => setValue("gpu_min_mhz", Math.min(gpuMhz[index], gpuMaxMhz))} />
          <SliderField label={t("power.gpuMax", { mhz: gpuMaxMhz })} description={isOverclocked(gpuMaxMhz, gpuStockMaxMhz) ? t("power.gpuOverclocked", { mhz: gpuStockMaxMhz }) : undefined} value={gpuIndex} min={0} max={gpuMhz.length - 1} step={1} showValue={false} disabled={saving} onChange={(index) => setGpuMax(gpuMhz[index])} />
        </> : null}
      </DialogControlsSection>
      <DialogControlsSection>
        <DialogControlsSectionHeader>{t("profiles.otherSettings")}</DialogControlsSectionHeader>
        <Field label={t("power.fanCurve")} bottomSeparator="standard" childrenLayout="below">
          <Dropdown selectedOption={profile.fan_curve} rgOptions={fanCurves} disabled={saving} onChange={(option) => setValue("fan_curve", String(option.data))} />
        </Field>
      </DialogControlsSection>
    </DialogBody>
    <ArmadaDialogFooter>
      <DialogButtonPrimary disabled={saving || !dirty} onClick={() => { void save(); }}>{saving ? t("common.saving") : t("common.saveChanges")}</DialogButtonPrimary>
      <DialogButton disabled={saving} onClick={cancel}>{t("common.cancel")}</DialogButton>
      <DialogButton disabled={saving || !defaults} onClick={resetProfile}>{t("common.resetToDefault")}</DialogButton>
    </ArmadaDialogFooter>
  </ArmadaModalRoot>;
}
