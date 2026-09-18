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
import { t } from "../i18n";
import { makeCapture, normalizedValue, triggerPercent, updateCapture } from "../lib/calibration";
import type { CalibrationState, Capture, McuCalibrationCapability, McuCalibrationPreview } from "../types";

type Phase = "idle" | "recording" | "mcu-preview" | "mcu-complete" | "mcu-confirm";

type OverlayBar = { label: string; fraction: number };

const MCU_STEPS = [
  { stick: "left", phase: "center" },
  { stick: "left", phase: "range" },
  { stick: "right", phase: "center" },
  { stick: "right", phase: "range" },
] as const;

function OverlayBar({ bar }: { bar: OverlayBar }) {
  return (
    <div style={{ marginTop: "10px" }}>
      <div style={{ marginBottom: "5px", fontSize: "12px", opacity: 0.75, textAlign: "center" }}>{bar.label}</div>
      <ProgressBar nProgress={Math.max(0, Math.min(100, bar.fraction * 100))} nTransitionSec={0} />
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
  return (
    <div>
      <div style={{ marginBottom: "10px", fontSize: "15px", fontWeight: 600, opacity: 0.9 }}>{title}</div>
      <ProgressBar nProgress={triggerPercent(state, name)} nTransitionSec={0} />
    </div>
  );
}

const gridTwoCol = { display: "grid", gridTemplateColumns: "repeat(2, 132px)", gap: "22px", justifyContent: "center", width: "100%" } as const;

// Prevent modal gamepad input from leaving a focused button highlighted.
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
      setMcuCapability({ available: false });
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
          ...(current || { stick: "left", phase: "center", complete: false, progress: {} }),
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

  // Keep calibration input from reaching Steam behind the modal.
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
      setMcuPreview({ stick, phase: previewPhase, complete: false, progress: {}, error: String(error) });
      setPhase("mcu-preview");
    }
  };
  const stopMcuPreview = async () => {
    await endMcuCalibrationPreview(sessionToken.current).catch(() => {});
    setPhase("idle");
  };
  const startMcuWizard = () => {
    setMcuCommitted(false);
    setMcuCommitError("");
    startMcuPreview("left", "center");
  };
  const continueMcuWizard = async () => {
    if (!mcuPreview?.complete) return;
    await endMcuCalibrationPreview(sessionToken.current).catch(() => {});
    const index = MCU_STEPS.findIndex((step) => step.stick === mcuPreview.stick && step.phase === mcuPreview.phase);
    const next = MCU_STEPS[index + 1];
    if (!next) {
      setPhase("mcu-complete");
    } else {
      await startMcuPreview(next.stick, next.phase);
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
      return { label: t("calibration.centerProgress", { stable, goal: stableGoal }), fraction: stableGoal ? stable / stableGoal : 0 };
    }
    const turns = activePreview.progress.turns ?? 0;
    const turnGoal = activePreview.progress.turnGoal || 4;
    const headings = activePreview.progress.coveredHeadings ?? 0;
    const headingGoal = activePreview.progress.headingGoal || 8;
    return {
      label: t("calibration.turnProgress", { turns: turns.toFixed(1), goal: turnGoal, headings, headingGoal }),
      fraction: Math.min(turnGoal ? turns / turnGoal : 0, headingGoal ? headings / headingGoal : 0),
    };
  };

  const wizardStep = mcuPreview
    ? MCU_STEPS.findIndex((step) => step.stick === mcuPreview.stick && step.phase === mcuPreview.phase) + 1
    : 0;

  const instructions = !state
    ? t("calibration.checking")
    : phase === "mcu-preview"
      ? mcuPreview?.error
        ? t("calibration.previewStopped", { error: mcuPreview.error })
        : mcuPreview?.phase === "center"
          ? t("calibration.centerStep", { step: wizardStep, total: MCU_STEPS.length })
          : t("calibration.rangeStep", { step: wizardStep, total: MCU_STEPS.length })
    : phase === "mcu-confirm"
      ? t("calibration.confirmApply")
    : phase === "mcu-complete"
      ? mcuCommitError
        ? t("calibration.notApplied", { error: mcuCommitError })
        : mcuCommitted
          ? t("calibration.applied")
          : t("calibration.review")
    : phase === "recording"
      ? mcuCapability?.available
        ? t("calibration.triggerCapture")
        : t("calibration.captureDescription")
    : mcuCapability?.available
      ? state?.canCalibrateTriggers
        ? t("calibration.chooseSticksOrTriggers")
        : t("calibration.sticksOnly")
    : !canApply
      ? t("calibration.readOnlyDescription")
      : t("calibration.startDescription");

  return (
    <ModalRoot onCancel={close}>
      <DialogBody>
        <div style={{ ...gridTwoCol, alignItems: "start", marginBottom: "22px" }}>
          <StickPlot title={t("calibration.leftStick")} xName="left_x" yName="left_y" state={state} bar={barFor("left")} />
          <StickPlot title={t("calibration.rightStick")} xName="right_x" yName="right_y" state={state} bar={barFor("right")} />
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
                {mcuPreview.stick === "right" && mcuPreview.phase === "range" ? t("calibration.finishPreview") : t("common.continue")}
              </DialogButton>
            ) : null}
            <DialogButton onClick={stopMcuPreview}>{mcuPreview?.error ? t("common.back") : t("common.cancel")}</DialogButton>
            <DialogButton onClick={close}>{t("common.close")}</DialogButton>
          </div>
        ) : phase === "mcu-complete" ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            {mcuCapability?.available && !mcuCommitError && !mcuCommitted ? <DialogButton onClick={() => setPhase("mcu-confirm")}>{t("calibration.applyMeasured")}</DialogButton> : null}
            {state?.canCalibrateTriggers ? <DialogButton onClick={start}>{t("calibration.calibrateTriggers")}</DialogButton> : null}
            <DialogButton onClick={startMcuWizard}>{t("calibration.runAgain")}</DialogButton>
            <DialogButton onClick={close}>{t("common.close")}</DialogButton>
          </div>
        ) : phase === "mcu-confirm" ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={commitMcuWizard}>{t("calibration.applyPermanently")}</DialogButton>
            <DialogButton onClick={() => setPhase("mcu-complete")}>{t("common.back")}</DialogButton>
          </div>
        ) : phase === "recording" ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={save} disabled={!capture}>{t("calibration.save")}</DialogButton>
            <DialogButton onClick={close}>{t("common.close")}</DialogButton>
          </div>
        ) : mcuCapability?.available ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={startMcuWizard}>{t("calibration.calibrateSticks")}</DialogButton>
            {state?.canCalibrateTriggers ? <DialogButton onClick={start}>{t("calibration.calibrateTriggers")}</DialogButton> : null}
            <DialogButton onClick={close}>{t("common.close")}</DialogButton>
          </div>
        ) : !canApply ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={close}>{t("common.close")}</DialogButton>
          </div>
        ) : (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={start}>{t("calibration.start")}</DialogButton>
            <DialogButton onClick={reset}>{t("calibration.resetDefaults")}</DialogButton>
            <DialogButton onClick={close}>{t("common.close")}</DialogButton>
          </div>
        )}
      </DialogFooter>
    </ModalRoot>
  );
}

export function openCalibration() {
  showModal(<CalibrationModal />);
}
