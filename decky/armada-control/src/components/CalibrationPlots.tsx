import { ProgressBar } from "@decky/ui";
import { normalizedValue, triggerPercent } from "../lib/calibration";
import type { CalibrationState, StickProgress, StickSide } from "../types";
import type { StickOverlay } from "../lib/mcuCalibration";

export type OverlayBar = { label: string; fraction: number };

const COMPASS_ANGLES = [270, 315, 0, 45, 90, 135, 180, 225];

function RimDirections({ overlay }: { overlay: StickOverlay }) {
  return (
    <>
      {overlay.dots.map((filled, index) => {
        const angle = (COMPASS_ANGLES[index] * Math.PI) / 180;
        const pending = overlay.pendingIndex === index;
        return (
          <svg
            key={index}
            viewBox="0 0 14 14"
            aria-hidden="true"
            style={{
              position: "absolute",
              width: "14px",
              height: "14px",
              margin: "-7px 0 0 -7px",
              transform: `rotate(${COMPASS_ANGLES[index]}deg)`,
              left: `${50 + 47 * Math.cos(angle)}%`,
              top: `${50 + 47 * Math.sin(angle)}%`,
              animation: pending ? "armada-cal-pulse 1.1s ease-in-out infinite" : undefined,
            }}
          >
            <path d="M2 2 L12 7 L2 12 Z" fill={filled ? "#2677d8" : "rgba(255,255,255,0.10)"}
              stroke={pending ? "#fff" : "rgba(255,255,255,0.6)"} strokeWidth={pending ? 2 : 1} />
          </svg>
        );
      })}
    </>
  );
}

function OverlayBar({ bar }: { bar: OverlayBar }) {
  return (
    <div style={{ marginTop: "10px" }}>
      <div style={{ marginBottom: "5px", fontSize: "12px", opacity: 0.75, textAlign: "center" }}>{bar.label}</div>
      <ProgressBar nProgress={Math.max(0, Math.min(100, bar.fraction * 100))} nTransitionSec={0} />
    </div>
  );
}

const DONE_COLOR = "#59bf40";
const MARKER_SIZE = 18;
const MARKER_GUTTER = 24;
const SIDE_POSITION: Record<StickSide, { left: string; top: string }> = {
  left: { left: `${MARKER_GUTTER / 2}px`, top: "50%" },
  right: { left: `calc(100% - ${MARKER_GUTTER / 2}px)`, top: "50%" },
  up: { left: "50%", top: `${MARKER_GUTTER / 2}px` },
  down: { left: "50%", top: `calc(100% - ${MARKER_GUTTER / 2}px)` },
};

const MARKER_RADIUS = MARKER_SIZE / 2 - 2;
const MARKER_CIRCUMFERENCE = 2 * Math.PI * MARKER_RADIUS;

function Marker({ progress, style }: { progress: number; style?: React.CSSProperties }) {
  const done = progress >= 1;
  const center = MARKER_SIZE / 2;
  return (
    <svg width={MARKER_SIZE} height={MARKER_SIZE} viewBox={`0 0 ${MARKER_SIZE} ${MARKER_SIZE}`} style={{ display: "block", flex: "none", ...style }}>
      <circle
        cx={center}
        cy={center}
        r={MARKER_RADIUS}
        fill={done ? DONE_COLOR : "rgba(255,255,255,0.08)"}
        stroke={done ? DONE_COLOR : "rgba(255,255,255,0.34)"}
        strokeWidth={2}
      />
      {!done && (
        <circle
          cx={center}
          cy={center}
          r={MARKER_RADIUS}
          fill="none"
          stroke={DONE_COLOR}
          strokeWidth={2}
          strokeDasharray={MARKER_CIRCUMFERENCE}
          strokeDashoffset={MARKER_CIRCUMFERENCE * (1 - progress)}
          transform={`rotate(-90 ${center} ${center})`}
          // Progress arrives in polled steps; a restarted hold must snap back, not glide.
          style={{ transition: progress > 0 ? "stroke-dashoffset 90ms linear" : "none" }}
        />
      )}
      {done && <path d="M5 9.4 L7.8 12.2 L13 6.6" fill="none" stroke="#fff" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />}
    </svg>
  );
}

export function StickPlot({ title, xName, yName, state, progress, overlay, bar, origin }: { title: string; xName: string; yName: string; state: CalibrationState | null; progress?: StickProgress; overlay?: StickOverlay; bar?: OverlayBar; origin?: [number, number] | null }) {
  const x = normalizedValue(state, xName, origin?.[0]);
  const y = normalizedValue(state, yName, origin?.[1]);
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ marginBottom: "4px", fontSize: "15px", fontWeight: 600, opacity: 0.9, textAlign: "center" }}>{title}</div>
      <div style={{ position: "relative", padding: `${MARKER_GUTTER}px` }}>
        {progress &&
          (Object.keys(SIDE_POSITION) as StickSide[]).map((side) => (
            <Marker
              key={side}
              progress={progress[side]}
              style={{ position: "absolute", margin: `-${MARKER_SIZE / 2}px 0 0 -${MARKER_SIZE / 2}px`, ...SIDE_POSITION[side] }}
            />
          ))}
      <div
        style={{
          position: "relative",
          width: "132px",
          height: "132px",
          border: "2px solid rgba(255,255,255,0.34)",
          background: "rgba(255,255,255,0.055)",
          boxSizing: "border-box",
        }}
      >
        <div style={{ position: "absolute", left: "8%", right: "8%", top: "50%", height: "1px", background: "rgba(255,255,255,0.22)" }} />
        <div style={{ position: "absolute", top: "8%", bottom: "8%", left: "50%", width: "1px", background: "rgba(255,255,255,0.22)" }} />
        <div
          style={{
            position: "absolute",
            width: "18px",
            height: "18px",
            margin: "-9px 0 0 -9px",
            border: "2px solid #fff",
            borderRadius: "50%",
            background: "#2677d8",
            left: `${50 + x * 44}%`,
            top: `${50 + y * 44}%`,
          }}
        />
        {overlay && <RimDirections overlay={overlay} />}
      </div>
      </div>
      {bar && <OverlayBar bar={bar} />}
    </div>
  );
}

export function TriggerBar({ title, name, state, progress }: { title: string; name: string; state: CalibrationState | null; progress?: number }) {
  return (
    <div style={{ padding: `0 ${MARKER_GUTTER}px` }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px", fontSize: "15px", fontWeight: 600, opacity: 0.9 }}>
        {title}
        {progress !== undefined && <Marker progress={progress} />}
      </div>
      <ProgressBar nProgress={triggerPercent(state, name)} nTransitionSec={0} />
    </div>
  );
}

export const gridTwoCol = { display: "grid", gridTemplateColumns: `repeat(2, ${132 + 2 * MARKER_GUTTER}px)`, justifyContent: "center", width: "100%" } as const;

// Modal input capture leaves gamepad focus frozen on the last-touched button.
export const focusStyles = `
  .armada-cal-footer button.gpfocus,
  .armada-cal-footer button:focus,
  .armada-cal-footer button:hover {
    background-color: rgba(255, 255, 255, 0.1) !important;
    color: #ffffff !important;
    box-shadow: none !important;
    transform: none !important;
    -webkit-filter: none !important;
    filter: none !important;
  }
  @keyframes armada-cal-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
`;
