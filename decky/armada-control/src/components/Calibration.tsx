import { showArmadaModal } from "./modalFocusView";
import {
  DialogBody,
  DialogButton,
  DialogButtonPrimary,
  ProgressBar,
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
import { ArmadaDialogFooter, ArmadaDialogHeader, ArmadaModalRoot } from "./ArmadaModalRoot";
import { SupportingText } from "./widgets";
import type { CalibrationState, StickProgress, StickSide } from "../types";

type Phase = "idle" | "recording";

const MARKER_SIZE = 18;
const STICK_SIDES: StickSide[] = ["left", "right", "up", "down"];
const MARKER_RADIUS = MARKER_SIZE / 2 - 2;
const MARKER_CIRCUMFERENCE = 2 * Math.PI * MARKER_RADIUS;
const PLOT_SIZE = 100;
const PLOT_CENTER = PLOT_SIZE / 2;
const STICK_TRAVEL = 44;

function Marker({ progress, side }: { progress: number; side?: StickSide }) {
  const done = progress >= 1;
  const center = MARKER_SIZE / 2;
  return (
    <svg className="armada-calibration-marker" data-side={side} data-complete={done} viewBox={`0 0 ${MARKER_SIZE} ${MARKER_SIZE}`}>
      <circle
        className="armada-calibration-marker-base"
        cx={center}
        cy={center}
        r={MARKER_RADIUS}
        strokeWidth={2}
      />
      {!done && (
        <circle
          className="armada-calibration-marker-progress"
          data-progressing={progress > 0}
          cx={center}
          cy={center}
          r={MARKER_RADIUS}
          strokeWidth={2}
          strokeDasharray={MARKER_CIRCUMFERENCE}
          strokeDashoffset={MARKER_CIRCUMFERENCE * (1 - progress)}
          transform={`rotate(-90 ${center} ${center})`}
        />
      )}
      {done && <path className="armada-calibration-marker-check" d="M5 9.4 L7.8 12.2 L13 6.6" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />}
    </svg>
  );
}

function StickPlot({ title, xName, yName, state, progress }: { title: string; xName: string; yName: string; state: CalibrationState | null; progress?: StickProgress }) {
  const x = normalizedValue(state, xName);
  const y = normalizedValue(state, yName);
  return (
    <div className="armada-calibration-control">
      <div className="armada-calibration-label">{title}</div>
      <div className="armada-calibration-surround">
        {progress &&
          STICK_SIDES.map((side) => (
            <Marker
              key={side}
              progress={progress[side]}
              side={side}
            />
          ))}
        <svg className="armada-calibration-plot" viewBox={`0 0 ${PLOT_SIZE} ${PLOT_SIZE}`}>
          <rect className="armada-calibration-frame" x={1} y={1} width={PLOT_SIZE - 2} height={PLOT_SIZE - 2} />
          <path className="armada-calibration-axis" d="M8 50H92 M50 8V92" />
          <circle className="armada-calibration-dot" cx={PLOT_CENTER + x * STICK_TRAVEL} cy={PLOT_CENTER + y * STICK_TRAVEL} r={6} />
        </svg>
      </div>
    </div>
  );
}

function TriggerBar({ title, name, state, progress }: { title: string; name: string; state: CalibrationState | null; progress?: number }) {
  return (
    <div className="armada-calibration-control">
      <div className="armada-calibration-label">
        {title}
        {progress !== undefined && <Marker progress={progress} />}
      </div>
      <div className="armada-calibration-trigger"><ProgressBar nProgress={triggerPercent(state, name)} nTransitionSec={0} /></div>
    </div>
  );
}

function CalibrationModal({ closeModal, onChanged }: {
  closeModal?: () => void;
  onChanged?: (state: CalibrationState) => void;
}) {
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
        onChanged?.(next);
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
        onChanged?.(next);
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
    <ArmadaModalRoot bAllowFullSize onCancel={close}>
      <ArmadaDialogHeader>{t("controller.calibrationTitle")}</ArmadaDialogHeader>
      <DialogBody>
        <div className="armada-calibration-grid">
          <StickPlot title={t("calibration.leftStick")} xName="left_x" yName="left_y" state={state} progress={progress?.left_stick} />
          <StickPlot title={t("calibration.rightStick")} xName="right_x" yName="right_y" state={state} progress={progress?.right_stick} />
        </div>
        <div className="armada-calibration-grid">
          <TriggerBar title={t("calibration.leftTrigger")} name="left_trigger" state={state} progress={progress?.left_trigger} />
          <TriggerBar title={t("calibration.rightTrigger")} name="right_trigger" state={state} progress={progress?.right_trigger} />
        </div>
        <SupportingText className="armada-calibration-instructions">{instructions}</SupportingText>
      </DialogBody>
      <ArmadaDialogFooter>
        {!canApply ? (
          <DialogButton onClick={close}>{t("common.close")}</DialogButton>
        ) : phase === "recording" ? (
          <>
            <DialogButtonPrimary onClick={save} disabled={!progress?.ready || busy}>{t("calibration.save")}</DialogButtonPrimary>
            <DialogButton onClick={close} disabled={busy}>
              {closing ? t("calibration.applying") : t("common.close")}
            </DialogButton>
          </>
        ) : (
          <>
            <DialogButtonPrimary onClick={start} disabled={busy}>{t("calibration.start")}</DialogButtonPrimary>
            <DialogButton onClick={reset} disabled={busy}>{t("calibration.resetDefaults")}</DialogButton>
            <DialogButton onClick={close} disabled={busy}>
              {closing ? t("calibration.applying") : t("common.close")}
            </DialogButton>
          </>
        )}
      </ArmadaDialogFooter>
    </ArmadaModalRoot>
  );
}

export function openCalibration(onChanged?: (state: CalibrationState) => void) {
  showArmadaModal(<CalibrationModal onChanged={onChanged} />);
}
