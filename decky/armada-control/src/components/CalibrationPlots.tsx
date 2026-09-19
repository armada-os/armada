import { ProgressBar } from "@decky/ui";
import { normalizedValue, triggerPercent } from "../lib/calibration";
import type { StickOverlay } from "../lib/mcuCalibration";
import type { CalibrationState } from "../types";

export type OverlayBar = { label: string; fraction: number };

const COMPASS_ANGLES = [270, 315, 0, 45, 90, 135, 180, 225];

function RimDots({ overlay }: { overlay: StickOverlay }) {
  return (
    <>
      {overlay.dots.map((filled, index) => {
        const angle = (COMPASS_ANGLES[index] * Math.PI) / 180;
        const pending = overlay.pendingIndex === index;
        return (
          <div
            key={index}
            style={{
              position: "absolute",
              width: "10px",
              height: "10px",
              margin: "-5px 0 0 -5px",
              borderRadius: "50%",
              background: filled ? "#2677d8" : "rgba(255,255,255,0.10)",
              border: pending ? "2px solid #ffffff" : "1px solid rgba(255,255,255,0.35)",
              left: `${50 + 47 * Math.cos(angle)}%`,
              top: `${50 + 47 * Math.sin(angle)}%`,
              animation: pending ? "armada-cal-pulse 1.1s ease-in-out infinite" : undefined,
            }}
          />
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

export function StickPlot({ title, xName, yName, state, overlay, bar }: { title: string; xName: string; yName: string; state: CalibrationState | null; overlay?: StickOverlay; bar?: OverlayBar }) {
  const x = normalizedValue(state, xName);
  const y = normalizedValue(state, yName);
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ marginBottom: "10px", fontSize: "15px", fontWeight: 600, opacity: 0.9 }}>{title}</div>
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
        {overlay ? <RimDots overlay={overlay} /> : null}
      </div>
      {bar ? <OverlayBar bar={bar} /> : null}
    </div>
  );
}

export function TriggerBar({ title, name, state }: { title: string; name: string; state: CalibrationState | null }) {
  return (
    <div>
      <div style={{ marginBottom: "10px", fontSize: "15px", fontWeight: 600, opacity: 0.9 }}>{title}</div>
      <ProgressBar nProgress={triggerPercent(state, name)} nTransitionSec={0} />
    </div>
  );
}

export const gridTwoCol = { display: "grid", gridTemplateColumns: "repeat(2, 132px)", gap: "22px", justifyContent: "center", width: "100%" } as const;

// Prevent modal gamepad input from leaving a focused button highlighted.
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

  @keyframes armada-cal-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.35; }
  }
`;
