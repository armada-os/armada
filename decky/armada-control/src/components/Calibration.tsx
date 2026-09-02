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
} from "../backend";
import { makeCapture, normalizedValue, triggerPercent, updateCapture } from "../lib/calibration";
import { t } from "../i18n";
import type { CalibrationState, Capture } from "../types";

type Phase = "idle" | "recording";

function StickPlot({ title, xName, yName, state }: { title: string; xName: string; yName: string; state: CalibrationState | null }) {
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
      </div>
    </div>
  );
}

function TriggerBar({ title, name, state }: { title: string; name: string; state: CalibrationState | null }) {
  return (
    <div>
      <div style={{ marginBottom: "10px", fontSize: "15px", fontWeight: 600, opacity: 0.9 }}>{title}</div>
      <ProgressBar nProgress={triggerPercent(state, name)} nTransitionSec={0} />
    </div>
  );
}

const gridTwoCol = { display: "grid", gridTemplateColumns: "repeat(2, 132px)", gap: "22px", justifyContent: "center", width: "100%" } as const;

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
  const [capture, setCapture] = useState<Capture | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const sessionToken = useRef(`${Date.now()}-${Math.random()}`);
  const phaseRef = useRef<Phase>("idle");
  const canApply = !!state?.canApply;
  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

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
        if (phaseRef.current === "recording" && next.supported) {
          setCapture((current) => updateCapture(current || makeCapture(next), next));
        }
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

  const close = () => {
    closeModal?.();
  };
  const start = () => {
    setCapture(null);
    setPhase("recording");
  };
  const save = async () => {
    if (!capture) return;
    try {
      const next = await saveCalibration(capture);
      setState(next);
      setCapture(null);
      setPhase("idle");
    } catch (error) {
      setState((current) => ({ ...(current || {}), supported: false, reason: String(error) } as CalibrationState));
      setPhase("idle");
    }
  };
  const reset = async () => {
    try {
      const next = await resetCalibration();
      setState(next);
    } catch (error) {
      setState((current) => ({ ...(current || {}), supported: false, reason: String(error) } as CalibrationState));
    }
  };

  const instructions = !state
    ? t("Checking controller...")
    : !canApply
      ? t("This device can't save calibration, but you can check stick and trigger response here.")
      : phase === "recording"
        ? t("Move both sticks in full circles and fully press both triggers, then Save.")
        : t("Press Start, then move sticks and triggers through full range.");

  return (
    <ModalRoot onCancel={close}>
      <DialogBody>
        <div style={{ ...gridTwoCol, alignItems: "start", marginBottom: "22px" }}>
          <StickPlot title={t("Left Stick")} xName="left_x" yName="left_y" state={state} />
          <StickPlot title={t("Right Stick")} xName="right_x" yName="right_y" state={state} />
        </div>
        <div style={{ ...gridTwoCol, marginBottom: "16px" }}>
          <TriggerBar title="LT" name="left_trigger" state={state} />
          <TriggerBar title="RT" name="right_trigger" state={state} />
        </div>
        <div style={{ fontSize: "13px", lineHeight: "18px", opacity: 0.72, textAlign: "center" }}>{instructions}</div>
      </DialogBody>
      <DialogFooter>
        <style>{focusStyles}</style>
        {!canApply ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={close}>{t("Close")}</DialogButton>
          </div>
        ) : phase === "recording" ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={save} disabled={!capture}>{t("Save Calibration")}</DialogButton>
            <DialogButton onClick={close}>{t("Close")}</DialogButton>
          </div>
        ) : (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={start}>{t("Start Calibration")}</DialogButton>
            <DialogButton onClick={reset}>{t("Reset to Defaults")}</DialogButton>
            <DialogButton onClick={close}>{t("Close")}</DialogButton>
          </div>
        )}
      </DialogFooter>
    </ModalRoot>
  );
}

export function openCalibration() {
  showModal(<CalibrationModal />);
}
