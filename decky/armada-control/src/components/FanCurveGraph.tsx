import { Focusable, GamepadButton } from "@decky/ui";
import type { GamepadEvent } from "@decky/ui";
import { useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import {
  CURVE_PWM_MAX as PWM_MAX,
  CURVE_PWM_MIN as PWM_MIN,
  CURVE_TEMP_MAX as TEMP_MAX,
  CURVE_TEMP_MIN as TEMP_MIN,
  percentToPwm,
  pwmToPercent,
} from "../lib/fanCurve";
import type { CurvePoint } from "../lib/fanCurve";
import { clamp } from "../lib/util";

const WIDTH = 280;
const HEIGHT = 170;
const PAD_LEFT = 26;
const PAD_RIGHT = 8;
const PAD_TOP = 10;
const PAD_BOTTOM = 18;
const PLOT_W = WIDTH - PAD_LEFT - PAD_RIGHT;
const PLOT_H = HEIGHT - PAD_TOP - PAD_BOTTOM;
const TEMP_TICKS = [0, 20, 40, 60, 80, 100, 120];
const PWM_TICK_PERCENTS = [0, 25, 50, 75, 100];
const CONTROLLER_TEMP_STEP = 1;
const CONTROLLER_PWM_STEP = 5;

function xForTemp(temp: number) {
  return PAD_LEFT + (clamp(temp, TEMP_MIN, TEMP_MAX) - TEMP_MIN) / (TEMP_MAX - TEMP_MIN) * PLOT_W;
}

function yForPwm(pwm: number) {
  return PAD_TOP + (1 - (clamp(pwm, PWM_MIN, PWM_MAX) - PWM_MIN) / (PWM_MAX - PWM_MIN)) * PLOT_H;
}

interface DragState {
  points: CurvePoint[];
  index: number;
}

export function FanCurveGraph({ points, onChange, currentTemp }: {
  points: CurvePoint[];
  onChange: (next: CurvePoint[]) => void;
  currentTemp?: number | null;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const [livePoints, setLivePoints] = useState<CurvePoint[] | null>(null);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [controllerActive, setControllerActive] = useState(false);
  const [controllerIndex, setControllerIndex] = useState(0);
  const shown = livePoints ?? points;
  const sorted = useMemo(() => [...shown].sort((a, b) => a.temp - b.temp), [shown]);
  if (!sorted.length) return null;

  const eventToPoint = (e: ReactPointerEvent): CurvePoint | null => {
    const svg = svgRef.current;
    if (!svg) return null;
    const rect = svg.getBoundingClientRect();
    const fracX = clamp((e.clientX - rect.left) / rect.width, 0, 1);
    const fracY = clamp((e.clientY - rect.top) / rect.height, 0, 1);
    const vbX = fracX * WIDTH;
    const vbY = fracY * HEIGHT;
    const temp = Math.round(TEMP_MIN + clamp((vbX - PAD_LEFT) / PLOT_W, 0, 1) * (TEMP_MAX - TEMP_MIN));
    const pwm = Math.round(PWM_MAX - clamp((vbY - PAD_TOP) / PLOT_H, 0, 1) * (PWM_MAX - PWM_MIN));
    return { temp: clamp(temp, TEMP_MIN, TEMP_MAX), pwm: clamp(pwm, PWM_MIN, PWM_MAX) };
  };
  const onPointerDown = (index: number) => (e: ReactPointerEvent<SVGCircleElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = { points: points.map((p) => ({ ...p })), index };
    setActiveIndex(index);
    setLivePoints(points.map((p) => ({ ...p })));
  };
  const onPointerMove = (e: ReactPointerEvent<SVGCircleElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    const next = eventToPoint(e);
    if (!next) return;
    drag.points[drag.index] = next;
    setLivePoints([...drag.points]);
  };
  const endDrag = (e: ReactPointerEvent<SVGCircleElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    dragRef.current = null;
    setActiveIndex(null);
    setLivePoints(null);
    onChange(drag.points);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // already released (e.g. pointercancel) -- fine to ignore
    }
  };
  const enterControllerMode = () => {
    if (!points.length) return;
    setControllerActive(true);
    setControllerIndex((current) => clamp(current, 0, points.length - 1));
  };
  const exitControllerMode = () => setControllerActive(false);
  const cycleControllerPoint = (delta: number) => {
    if (!points.length) return;
    setControllerIndex((current) => (current + delta + points.length) % points.length);
  };
  const moveControllerPoint = (deltaTemp: number, deltaPwm: number) => {
    if (!points.length) return;
    const index = clamp(controllerIndex, 0, points.length - 1);
    const current = points[index];
    const lowerBound = index > 0 ? points[index - 1].temp + 1 : TEMP_MIN;
    const upperBound = index < points.length - 1 ? points[index + 1].temp - 1 : TEMP_MAX;
    const nextTemp = clamp(current.temp + deltaTemp, Math.max(TEMP_MIN, lowerBound), Math.min(TEMP_MAX, upperBound));
    const nextPwm = clamp(current.pwm + deltaPwm, PWM_MIN, PWM_MAX);
    if (nextTemp === current.temp && nextPwm === current.pwm) return;
    onChange(points.map((point, i) => (i === index ? { temp: nextTemp, pwm: nextPwm } : point)));
  };
  const handleGraphButtonDown = (e: GamepadEvent) => {
    switch (e.detail.button) {
      case GamepadButton.BUMPER_LEFT:
        cycleControllerPoint(-1);
        break;
      case GamepadButton.BUMPER_RIGHT:
        cycleControllerPoint(1);
        break;
      default:
        return;
    }
    e.preventDefault();
    e.stopPropagation();
  };
  const handleGraphDirection = (e: GamepadEvent) => {
    switch (e.detail.button) {
      case GamepadButton.DIR_UP:
        moveControllerPoint(0, CONTROLLER_PWM_STEP);
        break;
      case GamepadButton.DIR_DOWN:
        moveControllerPoint(0, -CONTROLLER_PWM_STEP);
        break;
      case GamepadButton.DIR_RIGHT:
        moveControllerPoint(CONTROLLER_TEMP_STEP, 0);
        break;
      case GamepadButton.DIR_LEFT:
        moveControllerPoint(-CONTROLLER_TEMP_STEP, 0);
        break;
      default:
        return;
    }
    e.preventDefault();
    e.stopPropagation();
  };

  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  const pathD = [
    `M ${PAD_LEFT} ${yForPwm(first.pwm)}`,
    `L ${xForTemp(first.temp)} ${yForPwm(first.pwm)}`,
    ...sorted.slice(1).map((p) => `L ${xForTemp(p.temp)} ${yForPwm(p.pwm)}`),
    `L ${PAD_LEFT + PLOT_W} ${yForPwm(last.pwm)}`,
  ].join(" ");
  const fanStopActive = first.pwm === 0;
  let fanStopBoundaryTemp = first.temp;
  for (const point of sorted) {
    if (point.pwm !== 0) break;
    fanStopBoundaryTemp = point.temp;
  }
  const fanStopX = xForTemp(fanStopBoundaryTemp);
  const hasCurrentTemp = typeof currentTemp === "number" && Number.isFinite(currentTemp);
  const currentTempX = hasCurrentTemp ? xForTemp(currentTemp as number) : 0;
  const interpolatePwm = (temp: number) => {
    if (temp <= first.temp) return first.pwm;
    if (temp >= last.temp) return last.pwm;
    for (let i = 0; i < sorted.length - 1; i += 1) {
      const a = sorted[i];
      const b = sorted[i + 1];
      if (temp >= a.temp && temp <= b.temp) {
        const t = b.temp === a.temp ? 0 : (temp - a.temp) / (b.temp - a.temp);
        return a.pwm + t * (b.pwm - a.pwm);
      }
    }
    return last.pwm;
  };
  const currentTempY = hasCurrentTemp ? yForPwm(interpolatePwm(currentTemp as number)) : 0;

  return (
    <Focusable
      className={controllerActive ? "afc-graph-focusable afc-graph-editing" : "afc-graph-focusable"}
      focusClassName="afc-graph-focused"
      onActivate={enterControllerMode}
      onOKButton={enterControllerMode}
      onCancelButton={controllerActive ? exitControllerMode : undefined}
      onButtonDown={controllerActive ? handleGraphButtonDown : undefined}
      onGamepadDirection={controllerActive ? handleGraphDirection : undefined}
      onGamepadBlur={controllerActive ? exitControllerMode : undefined}
      onOKActionDescription={controllerActive ? undefined : "Edit Point"}
      onCancelActionDescription={controllerActive ? "Stop Editing" : undefined}
    >
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ width: "100%", height: "auto", display: "block", touchAction: "none", userSelect: "none" }}
      >
        <rect x={PAD_LEFT} y={PAD_TOP} width={PLOT_W} height={PLOT_H} fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.15)" />
      {fanStopActive ? (
        <g pointerEvents="none">
          <rect x={PAD_LEFT} y={PAD_TOP} width={Math.max(0, fanStopX - PAD_LEFT)} height={PLOT_H} fill="rgba(255,209,102,0.14)" />
          <line x1={fanStopX} x2={fanStopX} y1={PAD_TOP} y2={PAD_TOP + PLOT_H} stroke="rgba(255,209,102,0.55)" strokeDasharray="2,2" />
          <text x={PAD_LEFT + 2} y={PAD_TOP + 9} fontSize="7" textAnchor="start" fill="rgba(255,209,102,0.85)">
            FAN STOPPED
          </text>
        </g>
      ) : null}
      {PWM_TICK_PERCENTS.map((percent) => {
        const pwm = percentToPwm(percent);
        return (
          <g key={`pwm-${percent}`}>
            <line x1={PAD_LEFT} x2={PAD_LEFT + PLOT_W} y1={yForPwm(pwm)} y2={yForPwm(pwm)} stroke="rgba(255,255,255,0.08)" />
            <text x={PAD_LEFT - 4} y={yForPwm(pwm) + 3} fontSize="7" textAnchor="end" fill="rgba(255,255,255,0.55)">
              {`${percent}%`}
            </text>
          </g>
        );
      })}
      {TEMP_TICKS.map((temp) => (
        <g key={`temp-${temp}`}>
          <line x1={xForTemp(temp)} x2={xForTemp(temp)} y1={PAD_TOP} y2={PAD_TOP + PLOT_H} stroke="rgba(255,255,255,0.06)" />
          <text x={xForTemp(temp)} y={HEIGHT - 4} fontSize="7" textAnchor="middle" fill="rgba(255,255,255,0.55)">
            {temp}
          </text>
        </g>
      ))}
      <path d={pathD} fill="none" stroke="#5cc8ff" strokeWidth={2} />
      {hasCurrentTemp ? (
        <g pointerEvents="none">
          <circle cx={currentTempX} cy={currentTempY} r={7} fill="rgba(255,255,255,0.18)" />
          <circle cx={currentTempX} cy={currentTempY} r={3.5} fill="#ffffff" stroke="#0D141C" strokeWidth={1.5} />
          <text
            x={clamp(currentTempX, PAD_LEFT + 14, PAD_LEFT + PLOT_W - 14)}
            y={currentTempY - 10 < PAD_TOP ? currentTempY + 15 : currentTempY - 10}
            fontSize="7"
            textAnchor="middle"
            fill="#ffffff"
          >
            {`${currentTemp}°C`}
          </text>
        </g>
      ) : null}
      {sorted.map((point) => {
        const index = shown.indexOf(point);
        const isActive = activeIndex !== null
          ? shown[activeIndex] === point
          : controllerActive && clamp(controllerIndex, 0, points.length - 1) === index;
        return (
          <g key={`point-${index}`}>
            <circle
              cx={xForTemp(point.temp)}
              cy={yForPwm(point.pwm)}
              r={14}
              fill="transparent"
              onPointerDown={onPointerDown(index)}
              onPointerMove={onPointerMove}
              onPointerUp={endDrag}
              onPointerCancel={endDrag}
              style={{ cursor: "grab", touchAction: "none" }}
            />
            <circle
              cx={xForTemp(point.temp)}
              cy={yForPwm(point.pwm)}
              r={isActive ? 6 : 4.5}
              fill={isActive ? "#ffd166" : "#5cc8ff"}
              stroke="#0D141C"
              strokeWidth={1.5}
              pointerEvents="none"
            />
            {isActive ? (
              <text
                x={xForTemp(point.temp)}
                y={yForPwm(point.pwm) - 12 < PAD_TOP ? yForPwm(point.pwm) + 14 : yForPwm(point.pwm) - 12}
                fontSize="8"
                textAnchor="middle"
                fill="#ffd166"
              >
                {`${point.temp}°C / ${pwmToPercent(point.pwm)}%`}
              </text>
            ) : null}
          </g>
        );
      })}
      </svg>
      {controllerActive ? (
        <div className="afc-controller-hint">
          {`D-Pad moves point ${clamp(controllerIndex, 0, points.length - 1) + 1} of ${points.length} · LB/RB switches points · B stops`}
        </div>
      ) : null}
    </Focusable>
  );
}
