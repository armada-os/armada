import {
  DialogBody,
  DialogButton,
  DialogFooter,
  ModalRoot,
  ProgressBar,
  showModal,
} from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import {
  beginCalibrationSession,
  endCalibrationSession,
  getControllerState,
  resetCalibration,
  saveCalibration,
  startCalibrationRecording,
} from "../backend";
import { normalizedValue, triggerPercent } from "../lib/calibration";
import { t } from "../i18n";
import type { CalibrationState, StickProgress, StickSide } from "../types";

type Phase = "idle" | "recording";

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

function StickPlot({ title, xName, yName, state, progress }: { title: string; xName: string; yName: string; state: CalibrationState | null; progress?: StickProgress }) {
  const x = normalizedValue(state, xName);
  const y = normalizedValue(state, yName);
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
      </div>
      </div>
    </div>
  );
}

function TriggerBar({ title, name, state, progress }: { title: string; name: string; state: CalibrationState | null; progress?: number }) {
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

const gridTwoCol = { display: "grid", gridTemplateColumns: `repeat(2, ${132 + 2 * MARKER_GUTTER}px)`, justifyContent: "center", width: "100%" } as const;

// Modal input capture leaves gamepad focus frozen on the last-touched button.
const focusStyles = `
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
`;

function CalibrationModal({ closeModal }: { closeModal?: () => void }) {
  const [state, setState] = useState<CalibrationState | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const sessionToken = useRef(`${Date.now()}-${Math.random()}`);
  const [busy, setBusy] = useState(false);
  const [closing, setClosing] = useState(false);
  const busyRef = useRef(false);
  const canApply = !!state?.canApply;
  const progress = phase === "recording" ? state?.progress : undefined;
  useEffect(() => {
    let cancelled = false;
    let inflight = false;
    const tick = async () => {
      if (cancelled || inflight) return;
      inflight = true;
      try {
        const next = await getControllerState();
        if (cancelled) return;
        setState(next);
      } catch (error) {
        if (!cancelled) setState({ supported: false, reason: String(error), controls: {} } as CalibrationState);
      } finally {
        inflight = false;
      }
    };
    tick();
    const timer = window.setInterval(tick, 50);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  // Intercept input for the whole modal so stick/trigger movement (during, after,
  // or just viewing calibration) doesn't leak to Steam behind it.
  useEffect(() => {
    const token = sessionToken.current;
    beginCalibrationSession(token).catch(() => {});
    return () => {
      endCalibrationSession(token).catch(() => {});
    };
  }, []);

  // Save, reset and close each finish before another can start, so Close always sees a saved change.
  const exclusive = async (work: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      await work();
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };
  const close = () =>
    exclusive(async () => {
      // Ending the session restarts InputPlumber after a change; stay open until the controller is back.
      setClosing(true);
      await endCalibrationSession(sessionToken.current).catch(() => {});
      closeModal?.();
    });
  const start = () =>
    exclusive(async () => {
      try {
        setState(await startCalibrationRecording());
        setPhase("recording");
      } catch (error) {
        setState((current) => ({ ...(current || {}), supported: false, reason: String(error) } as CalibrationState));
      }
    });
  const save = () =>
    exclusive(async () => {
      try {
        const next = await saveCalibration();
        setState(next);
        setPhase("idle");
      } catch (error) {
        setState((current) => ({ ...(current || {}), supported: false, reason: String(error) } as CalibrationState));
        setPhase("idle");
      }
    });
  const reset = () =>
    exclusive(async () => {
      try {
        const next = await resetCalibration();
        setState(next);
      } catch (error) {
        setState((current) => ({ ...(current || {}), supported: false, reason: String(error) } as CalibrationState));
      }
    });

  const instructions = !state
    ? t("calibration.checking")
    : !canApply
      ? t("calibration.readOnlyDescription")
      : phase === "recording"
        ? t("calibration.captureDescription")
        : t("calibration.startDescription");

  return (
    <ModalRoot onCancel={close}>
      <DialogBody>
        <div style={{ ...gridTwoCol, alignItems: "start", marginBottom: "10px" }}>
          <StickPlot title={t("calibration.leftStick")} xName="left_x" yName="left_y" state={state} progress={progress?.left_stick} />
          <StickPlot title={t("calibration.rightStick")} xName="right_x" yName="right_y" state={state} progress={progress?.right_stick} />
        </div>
        <div style={{ ...gridTwoCol, marginBottom: "16px" }}>
          <TriggerBar title="LT" name="left_trigger" state={state} progress={progress?.left_trigger} />
          <TriggerBar title="RT" name="right_trigger" state={state} progress={progress?.right_trigger} />
        </div>
        <div style={{ fontSize: "13px", lineHeight: "18px", opacity: 0.72, textAlign: "center" }}>{instructions}</div>
      </DialogBody>
      <DialogFooter>
        <style>{focusStyles}</style>
        {!canApply ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={close}>{t("common.close")}</DialogButton>
          </div>
        ) : phase === "recording" ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={save} disabled={!progress?.ready || busy}>{t("calibration.save")}</DialogButton>
            <DialogButton onClick={close} disabled={busy}>
              {closing ? t("calibration.applying") : t("common.close")}
            </DialogButton>
          </div>
        ) : (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={start} disabled={busy}>{t("calibration.start")}</DialogButton>
            <DialogButton onClick={reset} disabled={busy}>{t("calibration.resetDefaults")}</DialogButton>
            <DialogButton onClick={close} disabled={busy}>
              {closing ? t("calibration.applying") : t("common.close")}
            </DialogButton>
          </div>
        )}
      </DialogFooter>
    </ModalRoot>
  );
}

export function openCalibration() {
  showModal(<CalibrationModal />);
}
