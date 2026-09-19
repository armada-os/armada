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
  beginMcuCalibrationCapture,
  commitMcuCalibration,
  beginCalibrationSession,
  endMcuCalibrationCapture,
  endCalibrationSession,
  getControllerState,
  getMcuCalibrationCapability,
  getMcuCalibrationCapture,
  resetCalibration,
  saveCalibration,
} from "../backend";
import { t } from "../i18n";
import { makeCapture, normalizedValue, triggerPercent, updateCapture } from "../lib/calibration";
import { centerOverlay, type StickOverlay } from "../lib/mcuCalibration";
import type { CalibrationState, Capture, McuCalibrationCapability, McuCalibrationCapture } from "../types";

type Phase = "idle" | "recording" | "mcu-capture" | "mcu-ready" | "mcu-applying" | "mcu-applied";

type OverlayBar = { label: string; fraction: number };

const MCU_STEPS = [
  { stick: "left", phase: "center" },
  { stick: "left", phase: "range" },
  { stick: "right", phase: "center" },
  { stick: "right", phase: "range" },
] as const;

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

function StickPlot({ title, xName, yName, state, overlay, bar }: { title: string; xName: string; yName: string; state: CalibrationState | null; overlay?: StickOverlay; bar?: OverlayBar }) {
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
  const [mcuCapture, setMcuCapture] = useState<McuCalibrationCapture | null>(null);
  const [mcuCommitError, setMcuCommitError] = useState("");
  const inputSessionToken = useRef(`${Date.now()}-${Math.random()}`);
  const mcuSessionToken = useRef(`${Date.now()}-${Math.random()}`);
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
    if (phase !== "mcu-capture") return;
    let cancelled = false;
    const tick = async () => {
      try {
        const next = await getMcuCalibrationCapture(mcuSessionToken.current);
        if (!cancelled) setMcuCapture(next);
      } catch (error) {
        if (!cancelled) setMcuCapture((current) => ({
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
    const inputToken = inputSessionToken.current;
    beginCalibrationSession(inputToken).catch(() => {});
    return () => {
      endMcuCalibrationCapture(mcuSessionToken.current).catch(() => {});
      endCalibrationSession(inputToken).catch(() => {});
    };
  }, []);

  const close = () => {
    if (phaseRef.current === "mcu-applying") return;
    endMcuCalibrationCapture(mcuSessionToken.current).catch(() => {});
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
  const startMcuCapture = async (stick: "left" | "right", capturePhase: "center" | "range") => {
    try {
      const next = await beginMcuCalibrationCapture(mcuSessionToken.current, stick, capturePhase);
      setMcuCapture(next);
      setPhase("mcu-capture");
    } catch (error) {
      setMcuCapture({ stick, phase: capturePhase, complete: false, progress: {}, error: String(error) });
      setPhase("mcu-capture");
    }
  };
  const stopMcuCapture = async () => {
    await endMcuCalibrationCapture(mcuSessionToken.current).catch(() => {});
    setPhase("idle");
  };
  const startMcuWizard = () => {
    mcuSessionToken.current = `${Date.now()}-${Math.random()}`;
    setMcuCommitError("");
    startMcuCapture("left", "center");
  };
  const continueMcuWizard = async () => {
    if (!mcuCapture?.complete) return;
    await endMcuCalibrationCapture(mcuSessionToken.current).catch(() => {});
    const index = MCU_STEPS.findIndex((step) => step.stick === mcuCapture.stick && step.phase === mcuCapture.phase);
    const next = MCU_STEPS[index + 1];
    if (!next) {
      setPhase("mcu-ready");
    } else {
      await startMcuCapture(next.stick, next.phase);
    }
  };
  const commitMcuWizard = async () => {
    setPhase("mcu-applying");
    try {
      await commitMcuCalibration(mcuSessionToken.current);
      setMcuCommitError("");
      setPhase("mcu-applied");
    } catch (error) {
      setMcuCommitError(String(error));
      setPhase("mcu-ready");
    }
  };

  const activeCapture = phase === "mcu-capture" && mcuCapture && !mcuCapture.error ? mcuCapture : null;
  const overlayFor = (stick: "left" | "right"): StickOverlay | undefined => {
    if (!activeCapture || activeCapture.stick !== stick || activeCapture.phase !== "center") return undefined;
    return centerOverlay(stick, activeCapture.progress.coveredDirections, activeCapture.progress.pendingDirection);
  };
  const barFor = (stick: "left" | "right"): OverlayBar | undefined => {
    if (!activeCapture || activeCapture.stick !== stick) return undefined;
    if (activeCapture.phase === "center") {
      const covered = activeCapture.progress.directionCount ?? 0;
      const goal = activeCapture.progress.directionGoal || 8;
      const pending = activeCapture.progress.pendingDirection;
      if (pending) {
        const stable = activeCapture.progress.stableSamples ?? 0;
        const stableGoal = activeCapture.progress.stableGoal || 30;
        return { label: t("calibration.returnProgress", { stable, goal: stableGoal }), fraction: stableGoal ? stable / stableGoal : 0 };
      }
      return { label: t("calibration.centerProgress", { covered, goal }), fraction: covered / goal };
    }
    const turns = activeCapture.progress.turns ?? 0;
    const turnGoal = activeCapture.progress.turnGoal || 4;
    const headings = activeCapture.progress.coveredHeadings ?? 0;
    const headingGoal = activeCapture.progress.headingGoal || 8;
    return {
      label: t("calibration.turnProgress", { turns: turns.toFixed(1), goal: turnGoal, headings, headingGoal }),
      fraction: Math.min(turnGoal ? turns / turnGoal : 0, headingGoal ? headings / headingGoal : 0),
    };
  };

  const wizardStep = mcuCapture
    ? MCU_STEPS.findIndex((step) => step.stick === mcuCapture.stick && step.phase === mcuCapture.phase) + 1
    : 0;

  const instructions = !state
    ? t("calibration.checking")
    : phase === "mcu-capture"
      ? mcuCapture?.error
        ? t("calibration.captureStopped", { error: mcuCapture.error })
        : mcuCapture?.phase === "center"
          ? t("calibration.centerStep", { step: wizardStep, total: MCU_STEPS.length })
          : t("calibration.rangeStep", { step: wizardStep, total: MCU_STEPS.length })
    : phase === "mcu-ready"
      ? mcuCommitError
        ? t("calibration.notApplied", { error: mcuCommitError })
        : t("calibration.readyToApply")
    : phase === "mcu-applying"
      ? t("calibration.applying")
    : phase === "mcu-applied"
      ? t("calibration.applied")
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
          <StickPlot title={t("calibration.leftStick")} xName="left_x" yName="left_y" state={state} overlay={overlayFor("left")} bar={barFor("left")} />
          <StickPlot title={t("calibration.rightStick")} xName="right_x" yName="right_y" state={state} overlay={overlayFor("right")} bar={barFor("right")} />
        </div>
        {phase !== "mcu-capture" ? (
          <div style={{ ...gridTwoCol, marginBottom: "16px" }}>
            <TriggerBar title="LT" name="left_trigger" state={state} />
            <TriggerBar title="RT" name="right_trigger" state={state} />
          </div>
        ) : null}
        <div style={{ fontSize: "13px", lineHeight: "18px", opacity: 0.72, textAlign: "center" }}>{instructions}</div>
      </DialogBody>
      <DialogFooter>
        <style>{focusStyles}</style>
        {phase === "mcu-capture" ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            {mcuCapture?.complete && !mcuCapture.error ? (
              <DialogButton onClick={continueMcuWizard}>
                {mcuCapture.stick === "right" && mcuCapture.phase === "range" ? t("calibration.finishMeasurements") : t("common.continue")}
              </DialogButton>
            ) : null}
            <DialogButton onClick={stopMcuCapture}>{mcuCapture?.error ? t("common.back") : t("common.cancel")}</DialogButton>
            <DialogButton onClick={close}>{t("common.close")}</DialogButton>
          </div>
        ) : phase === "mcu-ready" ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            <DialogButton onClick={commitMcuWizard}>{t("calibration.applyCalibration")}</DialogButton>
            <DialogButton onClick={startMcuWizard}>{t("calibration.runAgain")}</DialogButton>
            <DialogButton onClick={close}>{t("common.close")}</DialogButton>
          </div>
        ) : phase === "mcu-applied" ? (
          <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
            {state?.canCalibrateTriggers ? <DialogButton onClick={start}>{t("calibration.calibrateTriggers")}</DialogButton> : null}
            <DialogButton onClick={startMcuWizard}>{t("calibration.runAgain")}</DialogButton>
            <DialogButton onClick={close}>{t("common.close")}</DialogButton>
          </div>
        ) : phase === "mcu-applying" ? null : phase === "recording" ? (
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
