import { ButtonItem, Field, PanelSection, PanelSectionRow } from "@decky/ui";
import { useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { AnimatedCollapse } from "./AnimatedCollapse";
import { NumberEdit, PseudoDropdown, SliderEdit, ToggleEdit } from "./fanWidgets";
import { FanCurveGraph } from "./FanCurveGraph";
import { useSelectedFanCurve } from "../hooks/useSelectedFanCurve";
import type { SelectedFanCurve } from "../hooks/useSelectedFanCurve";
import {
  CURVE_PWM_MAX,
  CURVE_PWM_MIN,
  CURVE_TEMP_MAX,
  CURVE_TEMP_MIN,
  DEFAULT_POINT,
  formatCurve,
  parseCurve,
  percentToPwm,
  pwmToPercent,
} from "../lib/fanCurve";
import type { CurvePoint } from "../lib/fanCurve";
import { clamp, clone, titleCase, update } from "../lib/util";
import type { CurvesState } from "../types";

const DEFAULT_FAN_STOP_TEMP = 60;
const RAMP_MIN = 1;
const RAMP_MAX = 255;
const SMOOTHING_MIN = 0;
const SMOOTHING_MAX = 99;
const MIN_FAN_SPEED = 0;
const MAX_FAN_SPEED = 100;
const FAN_STOP_SPAN = 20;

export function FanCurveEditor({
  state,
  setState,
  selected,
  onSelectedChange,
  onOpenFullscreen,
  onOpenCreateCurve,
  currentTemp,
}: {
  state: CurvesState;
  setState: Dispatch<SetStateAction<CurvesState | null>>;
  selected: string;
  onSelectedChange: (value: string) => void;
  onOpenFullscreen?: () => void;
  onOpenCreateCurve?: () => void;
  currentTemp?: number | null;
}) {
  const selectedCurve = useSelectedFanCurve(state, setState, selected);
  const { names, curveName, curve, points, commitPoints } = selectedCurve;
  const [showPointEditor, setShowPointEditor] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const minPwmBeforeFanStop = useRef<number | null>(null);
  const preFanStopPoints = useRef<{ name: string; points: CurvePoint[] } | null>(null);
  const usedBy = Object.values(state.profiles || {}).filter((p) => p.fan_curve === curveName);

  const deletableNames = names.filter((name) => {
    if (state.factoryFanCurves?.[name]) return false;
    return !Object.values(state.profiles || {}).some((p) => p.fan_curve === name);
  });
  const deleteTargetName = deletableNames.includes(deleteTarget) ? deleteTarget : deletableNames[0] || "";

  let zeroRunEnd = 0;
  while (zeroRunEnd < points.length && points[zeroRunEnd].pwm === 0) zeroRunEnd += 1;
  const fanStopEnabled = zeroRunEnd > 0;
  const anyFanStop = Object.values(state.fanCurves).some((fanCurve) => {
    const curvePoints = parseCurve(fanCurve.curve);
    return curvePoints.length > 0 && curvePoints[0].pwm === 0;
  });
  const fanStopTemp = fanStopEnabled ? points[zeroRunEnd - 1].temp : DEFAULT_FAN_STOP_TEMP;

  const restoreFanStopPoints = (allPoints: CurvePoint[], runEnd: number): CurvePoint[] => {
    if (runEnd <= 0) return allPoints;
    const zeroRun = allPoints.slice(0, runEnd);
    const rest = allPoints.slice(runEnd);
    const restorePwm = rest.length ? rest[0].pwm : DEFAULT_POINT.pwm;
    const restored = zeroRun.map((point) => ({ ...point, pwm: restorePwm || DEFAULT_POINT.pwm }));
    if (rest.length) return [...restored, ...rest];
    const lastTemp = restored[restored.length - 1].temp;
    return [
      ...restored,
      { temp: clamp(lastTemp + FAN_STOP_SPAN, lastTemp + 1, CURVE_TEMP_MAX), pwm: DEFAULT_POINT.pwm },
    ];
  };

  const buildFanStopPoints = (temp: number, allPoints: CurvePoint[]): CurvePoint[] => {
    const zeroed = allPoints.filter((point) => point.temp <= temp).map((point) => ({ ...point, pwm: 0 }));
    const above = allPoints.filter((point) => point.temp > temp);
    const hasBoundaryPoint = zeroed.some((point) => point.temp === temp);
    const zone = hasBoundaryPoint ? zeroed : [...zeroed, { temp, pwm: 0 }];
    if (above.length) return [...zone, ...above];
    const fallbackPwm = allPoints.length ? allPoints[allPoints.length - 1].pwm : DEFAULT_POINT.pwm;
    return [
      ...zone,
      { temp: clamp(temp + FAN_STOP_SPAN, temp + 1, CURVE_TEMP_MAX), pwm: fallbackPwm || DEFAULT_POINT.pwm },
    ];
  };

  const toggleFanStop = (checked: boolean) => {
    if (!curveName) return;
    let nextPoints: CurvePoint[];
    if (checked) {
      preFanStopPoints.current = { name: curveName, points };
      nextPoints = buildFanStopPoints(clamp(DEFAULT_FAN_STOP_TEMP, CURVE_TEMP_MIN, CURVE_TEMP_MAX), points);
    } else {
      const cached = preFanStopPoints.current;
      nextPoints = cached && cached.name === curveName ? cached.points : restoreFanStopPoints(points, zeroRunEnd);
      preFanStopPoints.current = null;
    }
    setState((current) => {
      if (!current) return current;
      const next = update(current, ["fanCurves", curveName, "curve"], formatCurve(nextPoints));
      if (checked) {
        minPwmBeforeFanStop.current = current.fanSettings.min_pwm;
        next.fanSettings.min_pwm = 0;
      } else {
        const anotherCurveStops = Object.entries(next.fanCurves).some(([name, fanCurve]) => {
          if (name === curveName) return false;
          const curvePoints = parseCurve(fanCurve.curve);
          return curvePoints.length > 0 && curvePoints[0].pwm === 0;
        });
        if (!anotherCurveStops) {
          next.fanSettings.min_pwm = minPwmBeforeFanStop.current ?? next.factoryFanSettings.min_pwm;
          minPwmBeforeFanStop.current = null;
        }
      }
      return next;
    });
  };

  const setFanStopTemp = (value: number) => {
    const cached = preFanStopPoints.current;
    const base = cached && cached.name === curveName ? cached.points : restoreFanStopPoints(points, zeroRunEnd);
    commitPoints(buildFanStopPoints(value, base));
  };

  const handleDeleteClick = () => {
    if (confirmDelete) {
      if (!deleteTargetName) return;
      setState((current) => {
        if (!current) return current;
        const next = clone(current);
        delete next.fanCurves[deleteTargetName];
        return next;
      });
      if (deleteTargetName === curveName) {
        onSelectedChange("");
      }
      setDeleteTarget("");
      setConfirmDelete(false);
    } else {
      setConfirmDelete(true);
    }
  };

  const setFanSetting = (key: "ramp_up" | "ramp_down" | "smoothing" | "min_pwm", value: number) => {
    setState((current) => (current ? update(current, ["fanSettings", key], value) : current));
  };

  return (
    <>
      <PanelSection title="EDIT CURVE">
        {names.length ? (
          <PseudoDropdown
            label="Curve"
            value={curveName}
            options={names.map((name) => ({ data: name, label: state.fanCurves[name]?.label || titleCase(name) }))}
            onChange={onSelectedChange}
          />
        ) : (
          <PanelSectionRow>
            <Field label="No fan curves found" />
          </PanelSectionRow>
        )}
        {curveName ? (
          <div className="afc-field-note afc-used-by-note">
            {usedBy.length ? `Used by: ${usedBy.map((p) => p.label).join(", ")}` : "Not assigned to any profile"}
          </div>
        ) : null}
      </PanelSection>
      {curve ? (
        <PointsPanel
          key={curveName}
          selectedCurve={selectedCurve}
          showPointEditor={showPointEditor}
          onToggleShowPointEditor={() => setShowPointEditor((v) => !v)}
          onOpenFullscreen={onOpenFullscreen}
          currentTemp={currentTemp}
          fanStopEnabled={fanStopEnabled}
          fanStopTemp={fanStopTemp}
          onToggleFanStop={toggleFanStop}
          onFanStopTempChange={setFanStopTemp}
        />
      ) : null}
      <PanelSection title="FAN RESPONSIVENESS">
        <SliderEdit
          label="Ramp Up"
          value={state.fanSettings.ramp_up}
          min={RAMP_MIN}
          max={RAMP_MAX}
          step={1}
          onChange={(v) => setFanSetting("ramp_up", v)}
        />
        <div className="afc-field-note">How fast the fan speeds up per ~3-second tick as the target rises.</div>
        <SliderEdit
          label="Ramp Down"
          value={state.fanSettings.ramp_down}
          min={RAMP_MIN}
          max={RAMP_MAX}
          step={1}
          onChange={(v) => setFanSetting("ramp_down", v)}
        />
        <div className="afc-field-note">How fast the fan slows down per ~3-second tick once the target drops.</div>
        <SliderEdit
          label="Temperature Smoothing (%)"
          value={Math.round(state.fanSettings.smoothing * 100)}
          min={SMOOTHING_MIN}
          max={SMOOTHING_MAX}
          step={1}
          onChange={(v) => setFanSetting("smoothing", Number((v / 100).toFixed(2)))}
        />
        <div className="afc-field-note">
          Evens out the temperature reading itself before it reaches the curve, so brief spikes don't yank the
          target around.
        </div>
        <SliderEdit
          label="Minimum Fan Speed (%)"
          value={pwmToPercent(state.fanSettings.min_pwm)}
          min={MIN_FAN_SPEED}
          max={MAX_FAN_SPEED}
          step={1}
          onChange={(v) => setFanSetting("min_pwm", percentToPwm(v))}
          disabled={anyFanStop}
        />
        <div className="afc-field-note">The lowest speed Armada allows. Fan Stop forces it to 0%.</div>
      </PanelSection>
      <PanelSection title="MANAGE CURVES">
        <PanelSectionRow>
          <div className="afc-control-inset">
            <ButtonItem layout="below" onClick={onOpenCreateCurve} disabled={!onOpenCreateCurve}>
              Create Curve
            </ButtonItem>
          </div>
        </PanelSectionRow>
        {deletableNames.length ? (
          <>
            <PseudoDropdown
              label="Curve To Delete"
              value={deleteTargetName}
              options={deletableNames.map((name) => ({
                data: name,
                label: state.fanCurves[name]?.label || titleCase(name),
              }))}
              onChange={(v) => {
                setDeleteTarget(v);
                setConfirmDelete(false);
              }}
            />
            <PanelSectionRow>
              <div className="afc-control-inset">
                <ButtonItem layout="below" onClick={handleDeleteClick} disabled={!deleteTargetName}>
                  {confirmDelete ? "Tap Again To Confirm Delete" : "Delete Curve"}
                </ButtonItem>
              </div>
            </PanelSectionRow>
          </>
        ) : (
          <div className="afc-note">
            No curves are eligible for deletion -- only a curve with no factory default that isn't assigned to a
            profile on the Power tab can be removed.
          </div>
        )}
      </PanelSection>
    </>
  );
}

export function FanCurveGraphEditor({ state, setState, selected, onSelectedChange, currentTemp }: {
  state: CurvesState;
  setState: Dispatch<SetStateAction<CurvesState | null>>;
  selected: string;
  onSelectedChange: (value: string) => void;
  currentTemp?: number | null;
}) {
  const { names, curveName, curve, points, factoryCurve, commitPoints, resetCurve, belowMinPoint, fixMinPwm } =
    useSelectedFanCurve(state, setState, selected);

  return (
    <>
      <PanelSection title="EDIT CURVE">
        {names.length ? (
          <PseudoDropdown
            label="Curve"
            value={curveName}
            options={names.map((name) => ({ data: name, label: state.fanCurves[name]?.label || titleCase(name) }))}
            onChange={onSelectedChange}
          />
        ) : (
          <PanelSectionRow>
            <Field label="No fan curves found" />
          </PanelSectionRow>
        )}
      </PanelSection>
      {curve ? (
        <PanelSection title="POINTS">
          <PanelSectionRow>
            <FanCurveGraph points={points} onChange={commitPoints} currentTemp={currentTemp} />
          </PanelSectionRow>
          <MinPwmWarningButton onFix={fixMinPwm} visible={belowMinPoint} />
          <div className="afc-note">
            Drag a point, or press A to steer it with the D-Pad. LB/RB switches points; B exits.
          </div>
          {factoryCurve ? (
            <div className="afc-reset-row">
              <ButtonItem layout="below" onClick={resetCurve}>
                Reset Curve To Factory
              </ButtonItem>
            </div>
          ) : null}
          <div className="afc-note">Nothing here is written to disk until you press Save Changes.</div>
        </PanelSection>
      ) : null}
    </>
  );
}

// Wrapper row stays mounted (avoids a scroll jump); only the button itself is conditionally
// rendered, since `disabled` alone left it selectable via gamepad nav.
function MinPwmWarningButton({ onFix, visible }: { onFix: () => void; visible: boolean }) {
  return (
    <PanelSectionRow>
      <div className={`afc-control-inset afc-min-warning-button${visible ? "" : " afc-min-warning-hidden"}`}>
        {visible ? (
          <ButtonItem
            layout="below"
            onClick={onFix}
            description="Also adjustable via the Minimum Fan Speed slider in Fan Responsiveness."
          >
            {"⚠ Below the Minimum Fan Speed floor -- tap to lower it to match"}
          </ButtonItem>
        ) : null}
      </div>
    </PanelSectionRow>
  );
}

function PointsPanel({
  selectedCurve,
  showPointEditor,
  onToggleShowPointEditor,
  onOpenFullscreen,
  currentTemp,
  fanStopEnabled,
  fanStopTemp,
  onToggleFanStop,
  onFanStopTempChange,
}: {
  selectedCurve: SelectedFanCurve;
  showPointEditor: boolean;
  onToggleShowPointEditor: () => void;
  onOpenFullscreen?: () => void;
  currentTemp?: number | null;
  fanStopEnabled: boolean;
  fanStopTemp: number;
  onToggleFanStop: (checked: boolean) => void;
  onFanStopTempChange: (value: number) => void;
}) {
  const {
    curveName,
    points,
    factoryCurve,
    commitPoints,
    resetCurve,
    setPoint,
    removePoint,
    addPoint,
    belowMinPoint,
    fixMinPwm,
  } = selectedCurve;
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggleExpanded = (index: number) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  // Removing a point shifts later indices down by one, so expanded rows are remapped here.
  const handleRemovePoint = (index: number) => {
    setExpanded((current) => {
      const next = new Set<number>();
      current.forEach((i) => {
        if (i === index) return;
        next.add(i > index ? i - 1 : i);
      });
      return next;
    });
    removePoint(index);
  };

  return (
    <PanelSection title="POINTS">
      <PanelSectionRow>
        <FanCurveGraph points={points} onChange={commitPoints} currentTemp={currentTemp} />
      </PanelSectionRow>
      <MinPwmWarningButton onFix={fixMinPwm} visible={belowMinPoint} />
      <div className="afc-note">
        Drag a point, or press A to steer it with the D-Pad. LB/RB switches points; B exits. Advanced editing uses
        raw {CURVE_PWM_MIN}-{CURVE_PWM_MAX} PWM.
      </div>
      <ToggleEdit
        label="Fan Stop"
        description="Fan off below the set temperature."
        checked={fanStopEnabled}
        onChange={onToggleFanStop}
      />
      {fanStopEnabled ? (
        <>
          <NumberEdit
            label="Stop Until (°C)"
            value={fanStopTemp}
            rangeMin={CURVE_TEMP_MIN}
            rangeMax={CURVE_TEMP_MAX}
            onCommit={onFanStopTempChange}
          />
          <div className="afc-note">The 0% minimum applies globally while Fan Stop is enabled.</div>
        </>
      ) : null}
      {onOpenFullscreen ? (
        <PanelSectionRow>
          <div className="afc-control-inset">
            <ButtonItem layout="below" onClick={onOpenFullscreen}>
              Fullscreen Editor
            </ButtonItem>
          </div>
        </PanelSectionRow>
      ) : null}
      <PanelSectionRow>
        <div className="afc-control-inset">
          <ButtonItem layout="below" onClick={onToggleShowPointEditor}>
            {showPointEditor ? "Hide Points" : "Edit Curve Points"}
          </ButtonItem>
        </div>
      </PanelSectionRow>
      <AnimatedCollapse isOpen={showPointEditor}>
        <div className="afc-points-drawer">
          {points.map((point, index) => (
            <PointRow
              key={`${curveName}-${index}`}
              index={index}
              point={point}
              isExpanded={expanded.has(index)}
              onToggle={() => toggleExpanded(index)}
              onCommitTemp={(v) => setPoint(index, "temp", v)}
              onCommitPwm={(v) => setPoint(index, "pwm", v)}
              onRemove={() => handleRemovePoint(index)}
              canRemove={points.length > 1}
            />
          ))}
          <div className="afc-reset-row">
            <ButtonItem layout="below" onClick={addPoint}>
              Add Point
            </ButtonItem>
          </div>
        </div>
      </AnimatedCollapse>
      {factoryCurve ? (
        <div className="afc-reset-row">
          <ButtonItem layout="below" onClick={resetCurve}>
            Reset Curve To Factory
          </ButtonItem>
        </div>
      ) : null}
      <div className="afc-note">Nothing here is written to disk until you press Save Changes.</div>
    </PanelSection>
  );
}

function PointRow({
  index,
  point,
  isExpanded,
  onToggle,
  onCommitTemp,
  onCommitPwm,
  onRemove,
  canRemove,
}: {
  index: number;
  point: CurvePoint;
  isExpanded: boolean;
  onToggle: () => void;
  onCommitTemp: (value: number) => void;
  onCommitPwm: (value: number) => void;
  onRemove: () => void;
  canRemove: boolean;
}) {
  const percent = pwmToPercent(point.pwm);

  return (
    <div className="afc-point-row">
      <div className="afc-point-row-header">
        <ButtonItem layout="below" onClick={onToggle}>
          {`${isExpanded ? "▾" : "▸"}  P${index + 1}: ${point.temp}°C / ${percent}%`}
        </ButtonItem>
        <ButtonItem layout="below" onClick={onRemove} disabled={!canRemove}>
          ×
        </ButtonItem>
      </div>
      <AnimatedCollapse isOpen={isExpanded}>
        <div className="afc-point-details-inner">
          <NumberEdit
            label="Temperature (°C)"
            value={point.temp}
            rangeMin={CURVE_TEMP_MIN}
            rangeMax={CURVE_TEMP_MAX}
            onCommit={onCommitTemp}
          />
          <NumberEdit
            label={`PWM (${CURVE_PWM_MIN}-${CURVE_PWM_MAX})`}
            value={point.pwm}
            rangeMin={CURVE_PWM_MIN}
            rangeMax={CURVE_PWM_MAX}
            onCommit={onCommitPwm}
          />
        </div>
      </AnimatedCollapse>
    </div>
  );
}
