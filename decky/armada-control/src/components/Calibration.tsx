import {
  DialogBody,
  DialogButton,
  DialogFooter,
  ModalRoot,
  showModal,
} from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import {
  beginMcuCalibrationPreview,
  commitMcuCalibration,
  beginCalibrationSession,
  endMcuCalibrationPreview,
  endCalibrationSession,
  getControllerState,
  getMcuCalibrationCapability,
  getMcuCalibrationPreview,
  resetCalibration,
  saveCalibration,
} from "../backend";
import { makeCapture, normalizedValue, triggerPercent, updateCapture } from "../lib/calibration";
import type { CalibrationState, Capture, McuCalibrationCapability, McuCalibrationPreview } from "../types";

type Phase = "idle" | "recording" | "mcu-preview" | "mcu-complete" | "mcu-confirm";

type OverlayBar = { label: string; fraction: number };

function OverlayBar({ bar }: { bar: OverlayBar }) {
  return (
    <div style={{ marginTop: "10px" }}>
      <div style={{ marginBottom: "5px", fontSize: "12px", opacity: 0.75, textAlign: "center" }}>{bar.label}</div>
      <div style={{ height: "6px", borderRadius: "3px", background: "rgba(255,255,255,0.14)", overflow: "hidden" }}>
        <div style={{ width: `${Math.max(0, Math.min(100, bar.fraction * 100))}%`, height: "100%", background: "#2677d8" }} />
      </div>
    </div>
  );
}

function StickPlot({ title, xName, yName, state, bar }: { title: string; xName: string; yName: string; state: CalibrationState | null; bar?: OverlayBar }) {
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
      {bar ? <OverlayBar bar={bar} /> : null}
    </div>
  );
}

function TriggerBar({ title, name, state }: { title: string; name: string; state: CalibrationState | null }) {
  const percent = triggerPercent(state, name);
  return (
    <div>
      <div style={{ marginBottom: "10px", fontSize: "15px", fontWeight: 600, opacity: 0.9 }}>{title}</div>
      <div
        role="progressbar"
        aria-label={title}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percent)}
        style={{ height: "8px", overflow: "hidden", borderRadius: "4px", background: "rgba(255,255,255,0.18)" }}
      >
        <div style={{ width: `${percent}%`, height: "100%", background: "#2677d8" }} />
      </div>
    </div>
  );
}

const gridTwoCol = { display: "grid", gridTemplateColumns: "repeat(2, 132px)", gap: "22px", justifyContent: "center", width: "100%" } as const;
const mcuSteps = [
  ["left", "center"], ["left", "range"], ["right", "center"], ["right", "range"],
] as const;

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

  @keyframes armada-cal-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.35; }
  }
`;

function CalibrationModal({ closeModal }: { closeModal?: () => void }) {
  const [state, setState] = useState<CalibrationState | null>(null);
  const [capture, setCapture] = useState<Capture | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [mcuCapability, setMcuCapability] = useState<McuCalibrationCapability | null>(null);
  const [mcuPreview, setMcuPreview] = useState<McuCalibrationPreview | null>(null);
  const [mcuCommitError, setMcuCommitError] = useState("");
  const [mcuCommitted, setMcuCommitted] = useState(false);
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

  useEffect(() => {
    getMcuCalibrationCapability().then(setMcuCapability).catch(() => {
      setMcuCapability({ available: false, abiVersion: 0, writeEnabled: false, phases: [] });
    });
  }, []);

  useEffect(() => {
    if (phase !== "mcu-preview") return;
    let cancelled = false;
    const tick = async () => {
      try {
        const next = await getMcuCalibrationPreview(sessionToken.current);
        if (!cancelled) setMcuPreview(next);
      } catch (error) {
        if (!cancelled) setMcuPreview((current) => ({
          ...(current || { active: false, stick: "left", phase: "center", sampleCount: 0, rawSampleCount: 0, generationGaps: 0, sequenceGaps: 0, droppedBaseline: null, dropped: null, latest: null, complete: false, progress: {}, result: null }),
          active: false,
          error: String(error),
        }));
      }
    };
    tick();
    const timer = window.setInterval(tick, 100);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [phase]);

  // Intercept input for the whole modal so stick/trigger movement (during, after,
  // or just viewing calibration) doesn't leak to Steam behind it.
  useEffect(() => {
    const token = sessionToken.current;
    beginCalibrationSession(token).catch(() => {});
    return () => {
      endMcuCalibrationPreview(token).catch(() => {});
      endCalibrationSession(token).catch(() => {});
    };
  }, []);

  const close = () => {
    endMcuCalibrationPreview(sessionToken.current).catch(() => {});
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
  const startMcuPreview = async (stick: "left" | "right", previewPhase: "center" | "range") => {
    try {
      const next = await beginMcuCalibrationPreview(sessionToken.current, stick, previewPhase);
      setMcuPreview(next);
      setPhase("mcu-preview");
    } catch (error) {
      setMcuPreview({ active: false, stick, phase: previewPhase, sampleCount: 0, rawSampleCount: 0, generationGaps: 0, sequenceGaps: 0, captureGaps: 0, droppedBaseline: null, dropped: null, latest: null, complete: false, progress: {}, result: null, error: String(error) });
    }
  };
  const stopMcuPreview = async () => {
    await endMcuCalibrationPreview(sessionToken.current).catch(() => {});
    setPhase("idle");
  };
  const startMcuWizard = () => {
    setMcuCommitted(false);
    startMcuPreview("left", "center");
  };
  const continueMcuWizard = async () => {
    if (!mcuPreview?.complete) return;
    await endMcuCalibrationPreview(sessionToken.current).catch(() => {});
    const index = mcuSteps.findIndex(([stick, phase]) => stick === mcuPreview.stick && phase === mcuPreview.phase);
    const next = mcuSteps[index + 1];
    if (!next) {
      setPhase("mcu-complete");
    } else {
      await startMcuPreview(...next);
    }
  };
  const commitMcuWizard = async () => {
    try {
      await commitMcuCalibration(sessionToken.current);
      setMcuCommitError("");
      setMcuCommitted(true);
    } catch (error) {
      setMcuCommitError(String(error));
    }
    setPhase("mcu-complete");
  };

  const activePreview = phase === "mcu-preview" && mcuPreview && !mcuPreview.error ? mcuPreview : null;
  const barFor = (stick: "left" | "right"): OverlayBar | undefined => {
    if (!activePreview || activePreview.stick !== stick) return undefined;
    if (activePreview.phase === "center") {
      const stable = activePreview.progress.stableSamples ?? 0;
      const stableGoal = activePreview.progress.stableGoal || 250;
      return { label: `Keep centered — ${stable}/${stableGoal}`, fraction: stableGoal ? stable / stableGoal : 0 };
    }
    const turns = activePreview.progress.turns ?? 0;
    const turnGoal = activePreview.progress.turnGoal || 4;
    return { label: `${turns.toFixed(1)}/${turnGoal} turns`, fraction: turnGoal ? turns / turnGoal : 0 };
  };

  const instructions = !state
    ? "Checking controller..."
    : phase === "mcu-preview"
      ? mcuPreview?.error
        ? `Preview stopped: ${mcuPreview.error}`
        : mcuPreview?.phase === "center"
          ? `Step ${mcuSteps.findIndex(([stick, phase]) => stick === mcuPreview.stick && phase === mcuPreview.phase) + 1} of ${mcuSteps.length} — release the stick and keep it untouched while its centre is measured.`
          : `Step ${mcuSteps.findIndex(([stick, phase]) => stick === mcuPreview.stick && phase === mcuPreview.phase) + 1} of ${mcuSteps.length} — hold the stick firmly against the outer edge for at least four complete rotations.`
    : phase === "mcu-confirm"
      ? "Apply these measured centre and range values permanently? This writes both Hall sensors' calibration NVM."
    : phase === "mcu-complete"
      ? mcuCommitError
        ? `Calibration was not applied: ${mcuCommitError}`
        : mcuCommitted
          ? "Stick calibration was applied. Calibrate the triggers separately if needed."
          : "Capture complete. Review the measured values before applying them permanently."
    : phase === "recording"
      ? mcuCapability?.available
        ? "Fully press and release both triggers several times, then Save."
        : "Move both sticks in full circles and fully press both triggers, then Save."
    : mcuCapability?.available
      ? state?.canCalibrateTriggers
        ? "Calibrate the Hall sticks in MCU storage, or calibrate the triggers separately."
        : "Calibrate the Hall sticks in MCU storage. Trigger response is shown for diagnostics."
    : !canApply
      ? "This device can't save calibration, but you can check stick and trigger response here."
      : "Press Start, then move sticks and triggers through full range.";

  return (
    <ModalRoot onCancel={close}>
      <DialogBody>
        <div style={{ ...gridTwoCol, alignItems: "start", marginBottom: "22px" }}>
          <StickPlot title="Left Stick" xName="left_x" yName="left_y" state={state} bar={barFor("left")} />
          <StickPlot title="Right Stick" xName="right_x" yName="right_y" state={state} bar={barFor("right")} />
        </div>
        {phase !== "mcu-preview" ? (
          <div style={{ ...gridTwoCol, marginBottom: "16px" }}>
            <TriggerBar title="LT" name="left_trigger" state={state} />
            <TriggerBar title="RT" name="right_trigger" state={state} />
          </div>
        ) : null}
        <div style={{ fontSize: "13px", lineHeight: "18px", opacity: 0.72, textAlign: "center" }}>{instructions}</div>
      </DialogBody>
      <DialogFooter>
        <style>{focusStyles}</style>
        {phase === "mcu-preview" ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            {mcuPreview?.complete && !mcuPreview.error ? (
              <DialogButton onClick={continueMcuWizard}>
                {mcuPreview.stick === "right" && mcuPreview.phase === "range" ? "Finish Preview" : "Continue"}
              </DialogButton>
            ) : null}
            <DialogButton onClick={stopMcuPreview}>{mcuPreview?.error ? "Back" : "Cancel"}</DialogButton>
            <DialogButton onClick={close}>Close</DialogButton>
          </div>
        ) : phase === "mcu-complete" ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            {mcuCapability?.writeEnabled && !mcuCommitError && !mcuCommitted ? <DialogButton onClick={() => setPhase("mcu-confirm")}>Apply Measured Calibration</DialogButton> : null}
            {state?.canCalibrateTriggers ? <DialogButton onClick={start}>Calibrate Triggers</DialogButton> : null}
            <DialogButton onClick={startMcuWizard}>Run Again</DialogButton>
            <DialogButton onClick={close}>Close</DialogButton>
          </div>
        ) : phase === "mcu-confirm" ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={commitMcuWizard}>Apply Permanently</DialogButton>
            <DialogButton onClick={() => setPhase("mcu-complete")}>Back</DialogButton>
          </div>
        ) : phase === "recording" ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={save} disabled={!capture}>Save Calibration</DialogButton>
            <DialogButton onClick={close}>Close</DialogButton>
          </div>
        ) : mcuCapability?.available ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={startMcuWizard}>Calibrate Sticks</DialogButton>
            {state?.canCalibrateTriggers ? <DialogButton onClick={start}>Calibrate Triggers</DialogButton> : null}
            <DialogButton onClick={close}>Close</DialogButton>
          </div>
        ) : !canApply ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={close}>Close</DialogButton>
          </div>
        ) : (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={start}>Start Calibration</DialogButton>
            <DialogButton onClick={reset}>Reset to Defaults</DialogButton>
            <DialogButton onClick={close}>Close</DialogButton>
          </div>
        )}
      </DialogFooter>
    </ModalRoot>
  );
}

export function openCalibration() {
  showModal(<CalibrationModal />);
}
