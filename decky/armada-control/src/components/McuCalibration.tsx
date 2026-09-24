import { DialogBody, DialogButton, DialogFooter } from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import { mcuCalibration } from "../backend";
import { t } from "../i18n";
import { centerOverlay } from "../lib/mcuCalibration";
import type { CalibrationState, McuCalibrationOperation, McuCalibrationSession } from "../types";
import { gridTwoCol, StickPlot, TriggerBar, type OverlayBar } from "./CalibrationPlots";

export function McuCalibration({ state, close, onBusy, calibrateTriggers }: {
  state: CalibrationState; close: () => void; onBusy: (busy: boolean) => void; calibrateTriggers: () => void;
}) {
  const [session, setSession] = useState<McuCalibrationSession | null>(null);
  const [connectionError, setConnectionError] = useState("");
  const [pending, setPending] = useState(false);
  const token = useRef<string | null>(null);
  const inflight = useRef(false);
  const revision = useRef(0);
  const mounted = useRef(true);
  const available = !!state.calibration?.available;
  const applying = session?.state === "applying";
  useEffect(() => { onBusy(pending || (applying && !connectionError)); }, [pending, applying, connectionError, onBusy]);

  useEffect(() => {
    mounted.current = true;
    let timer: number;
    const tick = async () => {
      const current = token.current;
      const version = revision.current;
      if (current && !inflight.current) {
        try {
          const next = await mcuCalibration("status", current);
          if (mounted.current && version === revision.current) { setSession(next); setConnectionError(""); }
        } catch (error) {
          if (mounted.current && version === revision.current) setConnectionError(String(error));
        }
      }
      if (mounted.current) timer = window.setTimeout(tick, 100);
    };
    tick();
    return () => {
      mounted.current = false;
      window.clearTimeout(timer);
      if (token.current) mcuCalibration("cancel", token.current).catch(() => {});
    };
  }, []);

  const act = async (operation: McuCalibrationOperation) => {
    if (inflight.current) return;
    if (operation === "start") token.current = `${Date.now()}-${Math.random()}`;
    if (!token.current) return;
    inflight.current = true;
    revision.current++;
    setPending(true);
    onBusy(true);
    try {
      const next = await mcuCalibration(operation, token.current, session?.step);
      if (mounted.current) { setSession(next); setConnectionError(""); }
    } catch (error) {
      // Resume status polling; never infer that a failed RPC means no write occurred.
      if (mounted.current) setConnectionError(String(error));
    } finally {
      inflight.current = false;
      if (mounted.current) setPending(false);
    }
  };
  const actions = session?.actions || ["start"];
  const measuring = session?.state === "measuring" || session?.state === "measured";
  const overlay = measuring && session.phase === "center"
    ? centerOverlay(session.progress.coveredDirections, session.progress.pendingDirection) : undefined;
  let bar: OverlayBar | undefined;
  if (measuring) {
    const p = session.progress;
    if (session.phase === "center") {
      const settling = !!p.pendingDirection;
      const value = settling ? p.stableSamples || 0 : p.directionCount || 0;
      const goal = settling ? p.stableGoal || 30 : p.directionGoal || 8;
      bar = { label: settling ? t("calibration.returnProgress", { stable: value, goal })
        : t("calibration.centerProgress", { covered: value, goal }), fraction: value / goal };
    } else {
      const turns = p.turns || 0, goal = p.turnGoal || 4;
      const headings = p.coveredHeadings || 0, headingGoal = p.headingGoal || 8;
      bar = { label: t("calibration.turnProgress", { turns: turns.toFixed(1), goal, headings, headingGoal }),
        fraction: Math.min(turns / goal, headings / headingGoal) };
    }
  }
  let description = t(!available ? "calibration.unavailable"
    : state.calibration?.triggers ? "calibration.chooseSticksOrTriggers" : "calibration.sticksOnly");
  if (measuring) description = t(session.phase === "center" ? "calibration.centerStep" : "calibration.rangeStep",
    { step: session.step + 1, total: session.totalSteps });
  if (session?.state === "ready") description = t("calibration.readyToApply");
  if (applying) description = t("calibration.applying");
  if (session?.state === "applied") description = t("calibration.applied");
  if (session?.state === "failed") description = t("calibration.captureStopped", { error: session.error });
  if (session?.state === "uncertain") description = t("calibration.applyUnknown", { error: session.error });

  return <>
    <DialogBody>
      <div style={{ ...gridTwoCol, alignItems: "start", marginBottom: "22px" }}>
        <StickPlot title={t("calibration.leftStick")} xName="left_x" yName="left_y" state={state}
          overlay={session?.stick === "left" ? overlay : undefined} bar={session?.stick === "left" ? bar : undefined} />
        <StickPlot title={t("calibration.rightStick")} xName="right_x" yName="right_y" state={state}
          overlay={session?.stick === "right" ? overlay : undefined} bar={session?.stick === "right" ? bar : undefined} />
      </div>
      {!measuring && <div style={{ ...gridTwoCol, marginBottom: "16px" }}>
        <TriggerBar title="LT" name="left_trigger" state={state} />
        <TriggerBar title="RT" name="right_trigger" state={state} />
      </div>}
      <div style={{ textAlign: "center" }}>{connectionError ? t("calibration.connectionLost", { error: connectionError }) : description}</div>
    </DialogBody>
    <DialogFooter>
      <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
        {actions.includes("start") && <DialogButton disabled={!available || pending || !!connectionError} onClick={() => act("start")}>
          {t(session ? "calibration.runAgain" : "calibration.calibrateSticks")}</DialogButton>}
        {actions.includes("continue") && <DialogButton disabled={pending || !!connectionError} onClick={() => act("continue")}>
          {t(session!.step + 1 === session!.totalSteps ? "calibration.finishMeasurements" : "common.continue")}</DialogButton>}
        {actions.includes("apply") && <DialogButton disabled={pending || !!connectionError} onClick={() => act("apply")}>{t("calibration.applyCalibration")}</DialogButton>}
        {actions.includes("cancel") && <DialogButton disabled={pending || !!connectionError} onClick={() => act("cancel")}>{t("common.cancel")}</DialogButton>}
        {actions.includes("start") && state.calibration?.triggers && <DialogButton disabled={pending || !!connectionError} onClick={calibrateTriggers}>{t("calibration.calibrateTriggers")}</DialogButton>}
        <DialogButton disabled={pending || (applying && !connectionError)} onClick={close}>{t("common.close")}</DialogButton>
      </div>
    </DialogFooter>
  </>;
}
