import { ButtonItem, PanelSection } from "@decky/ui";
import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { SelectEdit } from "../components/widgets";
import { clone, titleCase, update } from "../lib/util";
import type { Config, PowerProfile } from "../types";

const GPU_TOP_MHZ = 1100; // the daemon expresses GPU limits as a ratio of the top OPP.
// Daemon uses int(top*ratio) then snaps: choose_at_most for max, choose_at_least for min.
const atMost = (list: number[], t: number) => {
  const below = list.filter((v) => v <= t);
  return below.length ? below[below.length - 1] : (list[0] ?? 0);
};
const atLeast = (list: number[], t: number) => {
  const above = list.filter((v) => v >= t);
  return above.length ? above[0] : (list[list.length - 1] ?? 0);
};
const nearest = (list: number[], t: number) => (list.length ? list.reduce((a, b) => (Math.abs(b - t) < Math.abs(a - t) ? b : a)) : t);
const ratioMax = (m: number) => Math.min(1, (m + 8) / GPU_TOP_MHZ); // +8 keeps int(top*r) inside the OPP band
const ratioMin = (m: number) => m / GPU_TOP_MHZ;

export function Power({ config, setConfig }: { config: Config; setConfig: Dispatch<SetStateAction<Config | null>> }) {
  const order = config.power.order?.length ? config.power.order : Object.keys(config.power.profiles || {});
  const [selected, setSelected] = useState(config.power.general.default_profile || order[0]);
  const profile = order.includes(selected) ? selected : order[0];
  const p = (config.power.profiles[profile] || {}) as PowerProfile;

  const hw = config.hardware || { cpu: {}, gpu: [], governors: [] };
  const gpuOpps = hw.gpu || [];
  const govs = hw.governors?.length ? hw.governors : ["schedutil"];

  const profileOptions = order.map((name) => ({ data: name, label: config.power.profiles[name]?.label || titleCase(name) }));
  // Only curves actually referenced by a profile — hides leftover factory presets (relaxed/moderate/aggressive).
  const usedCurves = new Set(order.map((n) => config.power.profiles[n]?.fan_curve).filter(Boolean));
  const fanCurves = Object.entries(config.power.fan_curves || {})
    .filter(([name]) => usedCurves.has(name))
    .map(([name, c]) => ({ data: name, label: c.label || titleCase(name) }));

  const setField = (name: string, value: any) =>
    setConfig((cur) => (cur ? update(cur, ["power", "profiles", profile, name], value) : cur));

  // CPU per-cluster: lowest policy id = efficiency cores, highest = performance cores.
  const policyIds = Object.keys(hw.cpu).map(Number).sort((a, b) => a - b);
  const effId = policyIds.length ? String(policyIds[0]) : "0";
  const primeId = policyIds.length > 1 ? String(policyIds[policyIds.length - 1]) : effId;
  const effFreqs = hw.cpu[effId] || [];
  const primeFreqs = hw.cpu[primeId] || [];
  const toMhz = (khz: number) => Math.round(khz / 1000);
  // Effective cap = explicit per-policy MHz if set, else the profile's underclock-level table, else top OPP.
  const uclevels = (config.power.underclocks && config.power.underclocks[config.cpuDeviceClass]) || {};
  const resolveKhz = (prof: PowerProfile, pid: string, freqs: number[]): number => {
    const explicit = Number(prof[`cpu_max_policy${pid}`] || 0);
    if (explicit > 0) return explicit;
    const level = prof.cpu_underclock;
    const lvl = level && level !== "none" ? uclevels[level] : undefined;
    const fromLevel = lvl ? Number(lvl[`cpu_max_policy${pid}`] || 0) : 0;
    if (fromLevel > 0) return fromLevel;
    return freqs.length ? freqs[freqs.length - 1] : 0;
  };
  const curEff = resolveKhz(p, effId, effFreqs);
  const curPrime = resolveKhz(p, primeId, primeFreqs);

  // GPU: stored as ratio, shown as MHz.
  const showGpuMax = gpuOpps.length ? atMost(gpuOpps, Math.floor(Number(p.gpu_max || 1) * GPU_TOP_MHZ)) : 0;
  const showGpuMin = gpuOpps.length ? atLeast(gpuOpps, Math.floor(Number(p.gpu_min || 0) * GPU_TOP_MHZ)) : 0;
  const setGpu = (which: "gpu_min" | "gpu_max", pickMhz: number) => {
    setConfig((cur) => {
      if (!cur) return cur;
      const next = clone(cur);
      const t = next.power.profiles[profile] as PowerProfile;
      if (which === "gpu_max") t.gpu_max = ratioMax(pickMhz).toFixed(4);
      else t.gpu_min = ratioMin(pickMhz).toFixed(4);
      const mx = atMost(gpuOpps, Math.floor(Number(t.gpu_max || 1) * GPU_TOP_MHZ));
      const mn = atLeast(gpuOpps, Math.floor(Number(t.gpu_min || 0) * GPU_TOP_MHZ));
      if (mn > mx) {
        if (which === "gpu_max") t.gpu_min = ratioMin(mx).toFixed(4);
        else t.gpu_max = ratioMax(mn).toFixed(4);
      }
      return next;
    });
  };

  const resetProfile = () => {
    const def = config.powerDefaults?.profiles?.[profile];
    if (!def) return;
    setConfig((cur) => (cur ? update(cur, ["power", "profiles", profile], clone(def)) : cur));
  };

  return (
    <>
      <PanelSection title="EDIT POWER PROFILE">
        <SelectEdit value={profile} options={profileOptions} onChange={setSelected} />
      </PanelSection>
      <PanelSection title="FAN">
        <SelectEdit label="Fan Curve" value={p.fan_curve} options={fanCurves} onChange={(v) => setField("fan_curve", v)} />
      </PanelSection>
      {effFreqs.length ? (
        <PanelSection title="CPU MAX FREQUENCY">
          <SelectEdit
            label="Efficiency cores"
            value={String(nearest(effFreqs, curEff))}
            options={effFreqs.map((k) => ({ data: String(k), label: `${toMhz(k)} MHz` }))}
            onChange={(v) => setField(`cpu_max_policy${effId}`, String(v))}
          />
          {primeFreqs.length && primeId !== effId ? (
            <SelectEdit
              label="Performance cores"
              value={String(nearest(primeFreqs, curPrime))}
              options={primeFreqs.map((k) => ({ data: String(k), label: `${toMhz(k)} MHz` }))}
              onChange={(v) => setField(`cpu_max_policy${primeId}`, String(v))}
            />
          ) : null}
        </PanelSection>
      ) : null}
      {gpuOpps.length ? (
        <PanelSection title="GPU FREQUENCY">
          <SelectEdit
            label="GPU Max"
            value={String(showGpuMax)}
            options={gpuOpps.map((m) => ({ data: String(m), label: `${m} MHz` }))}
            onChange={(v) => setGpu("gpu_max", Number(v))}
          />
          <SelectEdit
            label="GPU Min (floor)"
            value={String(showGpuMin)}
            options={gpuOpps.map((m) => ({ data: String(m), label: `${m} MHz` }))}
            onChange={(v) => setGpu("gpu_min", Number(v))}
          />
        </PanelSection>
      ) : null}
      <PanelSection title="GOVERNOR">
        <SelectEdit
          value={p.cpu_governor || "schedutil"}
          options={govs.map((g) => ({ data: g, label: titleCase(g) }))}
          onChange={(v) => setField("cpu_governor", v)}
        />
      </PanelSection>
      <PanelSection>
        <div className="armada-reset-row">
          <ButtonItem layout="below" onClick={resetProfile}>Reset to Default</ButtonItem>
        </div>
      </PanelSection>
    </>
  );
}
