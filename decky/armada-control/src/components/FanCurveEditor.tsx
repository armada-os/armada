import { DialogButton, DialogControlsSection, DialogControlsSectionHeader, SliderField, ToggleField } from "@decky/ui";
import { useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { AnimatedCollapse } from "./AnimatedCollapse";
import { FanCurveGraph } from "./FanCurveGraph";
import { SupportingText, TextEdit } from "./widgets";
import { t, translateLabel } from "../i18n";
import { buildFanStopPoints, DEFAULT_POINT, formatCurve, parseCurve, CURVE_PWM_MAX, CURVE_PWM_MIN, CURVE_TEMP_MAX, CURVE_TEMP_MIN, percentToPwm, pwmToPercent, restoreFanStopPoints } from "../lib/fanCurve";
import type { CurvePoint } from "../lib/fanCurve";
import { clamp } from "../lib/util";
import type { FanCurve, FanSettings, ProfileSummary } from "../types";

const DEFAULT_FAN_STOP_TEMP = 60;

export function FanCurveEditor({ curve, setCurve, custom, profiles, currentTemp, disabled = false }: {
  curve: FanCurve;
  setCurve: Dispatch<SetStateAction<FanCurve>>;
  custom: boolean;
  profiles: ProfileSummary[];
  currentTemp?: number | null;
  disabled?: boolean;
}) {
  const points = parseCurve(curve.curve);
  const [showPoints, setShowPoints] = useState(false);
  const beforeFanStop = useRef<CurvePoint[] | null>(null);
  const assignment = profiles.length
    ? t("fanCurve.usedBy", { profiles: profiles.map((profile) => translateLabel(profile.label)).join(", ") })
    : t("fanCurve.unassigned");
  const commitPoints = (next: CurvePoint[]) => setCurve((current) => ({ ...current, curve: formatCurve(next) }));
  const setPoint = (index: number, key: "temp" | "pwm", value: number) => {
    commitPoints(points.map((point, i) => i === index ? { ...point, [key]: value } : point));
  };
  const addPoint = () => {
    const usedTemps = new Set(points.map((point) => point.temp));
    let temp = DEFAULT_POINT.temp;
    while (usedTemps.has(temp) && temp < CURVE_TEMP_MAX) temp += 1;
    if (!usedTemps.has(temp)) commitPoints([...points, { ...DEFAULT_POINT, temp }]);
  };
  const fanStopEnabled = points[0]?.pwm === 0;
  const lastStoppedPoint = points.findIndex((point) => point.pwm !== 0);
  const stopUntil = fanStopEnabled ? points[(lastStoppedPoint === -1 ? points.length : lastStoppedPoint) - 1].temp : DEFAULT_FAN_STOP_TEMP;
  const setSetting = (key: keyof FanSettings, value: number) => {
    setCurve((current) => ({ ...current, [key]: value }));
  };
  const toggleFanStop = (enabled: boolean) => {
    if (enabled) {
      beforeFanStop.current = points;
      commitPoints(buildFanStopPoints(DEFAULT_FAN_STOP_TEMP, points));
    } else {
      commitPoints(beforeFanStop.current || restoreFanStopPoints(points));
      beforeFanStop.current = null;
    }
  };
  return <>
    <DialogControlsSection>
      {custom ? <TextEdit
        label={t("fanCurve.name")}
        description={assignment}
        value={curve.label}
        disabled={disabled}
        onChange={(label) => setCurve((current) => ({ ...current, label: label.slice(0, 80) }))}
      /> : <SupportingText>{assignment}</SupportingText>}
      <DialogControlsSectionHeader>{t("power.fanCurve")}</DialogControlsSectionHeader>
      <FanCurveGraph points={points} onChange={commitPoints} currentTemp={currentTemp} disabled={disabled} />
      <SupportingText>{t("fanCurve.advancedEditInstructions", { min: CURVE_PWM_MIN, max: CURVE_PWM_MAX })}</SupportingText>
      {!fanStopEnabled && points.some((point) => point.pwm < curve.min_pwm) ? <DialogButton disabled={disabled} onClick={() => {
        setSetting("min_pwm", clamp(Math.min(...points.map((point) => point.pwm)), CURVE_PWM_MIN, CURVE_PWM_MAX));
      }}>{t("fanCurve.belowMinimumWarning")}</DialogButton> : null}
      <ToggleField label={t("fanCurve.stop")} description={t("fanCurve.stopDescription")} checked={fanStopEnabled} onChange={toggleFanStop} disabled={disabled} />
      {fanStopEnabled ? <>
        <PointNumber
          label={t("fanCurve.stopUntil")}
          value={stopUntil}
          min={CURVE_TEMP_MIN}
          max={CURVE_TEMP_MAX - 1}
          disabled={disabled}
          onChange={(temp) => commitPoints(buildFanStopPoints(temp, beforeFanStop.current || restoreFanStopPoints(points)))}
        />
        <SupportingText>{t("fanCurve.stopMinimumDescription")}</SupportingText>
      </> : null}
      <DialogButton disabled={disabled} onClick={() => setShowPoints((current) => !current)}>
        {showPoints ? t("fanCurve.hidePoints") : t("fanCurve.editPoints")}
      </DialogButton>
      <AnimatedCollapse isOpen={showPoints}>
        <div className="afc-points-drawer">
          {points.map((point, index) => <div className="afc-point-row" key={index}>
            <PointNumber label={`P${index + 1}: ${t("fanCurve.temperature")}`} value={point.temp} min={CURVE_TEMP_MIN} max={CURVE_TEMP_MAX} disabled={disabled} onChange={(value) => setPoint(index, "temp", value)} />
            <PointNumber label={`PWM (${CURVE_PWM_MIN}-${CURVE_PWM_MAX})`} value={point.pwm} min={CURVE_PWM_MIN} max={CURVE_PWM_MAX} disabled={disabled} onChange={(value) => setPoint(index, "pwm", value)} />
            <DialogButton disabled={disabled || points.length < 2} onClick={() => commitPoints(points.filter((_, i) => i !== index))}>{t("common.delete")}</DialogButton>
          </div>)}
          <DialogButton disabled={disabled} onClick={addPoint}>{t("fanCurve.addPoint")}</DialogButton>
        </div>
      </AnimatedCollapse>
    </DialogControlsSection>
    <DialogControlsSection>
      <DialogControlsSectionHeader>{t("fanCurve.responsiveness")}</DialogControlsSectionHeader>
      <SliderField label={t("fanCurve.rampUp")} description={t("fanCurve.rampUpDescription")} value={curve.ramp_up} min={1} max={255} step={1} showValue disabled={disabled} onChange={(value) => setSetting("ramp_up", value)} />
      <SliderField label={t("fanCurve.rampDown")} description={t("fanCurve.rampDownDescription")} value={curve.ramp_down} min={1} max={255} step={1} showValue disabled={disabled} onChange={(value) => setSetting("ramp_down", value)} />
      <SliderField label={t("fanCurve.temperatureSmoothing")} description={t("fanCurve.temperatureSmoothingDescription")} value={Math.round(curve.smoothing * 100)} min={0} max={99} step={1} showValue disabled={disabled} onChange={(value) => setSetting("smoothing", value / 100)} />
      <SliderField label={t("fanCurve.minimumSpeed")} description={t("fanCurve.minimumSpeedDescription")} value={fanStopEnabled ? 0 : pwmToPercent(curve.min_pwm)} min={0} max={100} step={1} showValue disabled={disabled || fanStopEnabled} onChange={(value) => setSetting("min_pwm", percentToPwm(value))} />
    </DialogControlsSection>
  </>;
}

function PointNumber({ label, value, min, max, disabled, onChange }: {
  label: string;
  value: number;
  min: number;
  max: number;
  disabled: boolean;
  onChange: (value: number) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  return <TextEdit
    label={label}
    value={draft ?? String(value)}
    disabled={disabled}
    mustBeNumeric
    rangeMin={min}
    rangeMax={max}
    onChange={setDraft}
    onBlur={() => {
      if (draft === null) return;
      const next = Number(draft);
      if (draft.trim() && Number.isFinite(next)) onChange(clamp(Math.round(next), min, max));
      setDraft(null);
    }}
  />;
}
