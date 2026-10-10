import { DialogBody, DialogButton, DialogFooter } from "@decky/ui";
import { useRef, useState } from "react";
import { resetCalibration, saveCalibration, startCalibrationRecording } from "../backend";
import { t } from "../i18n";
import type { CalibrationState } from "../types";
import { gridTwoCol, StickPlot, TriggerBar } from "./CalibrationPlots";

export function LegacyCalibration({ state, setState, close, triggersOnly = false, back, onBusy, closing }: {
  state: CalibrationState; closing: boolean; setState: (state: CalibrationState) => void; close: () => void;
  triggersOnly?: boolean; back?: () => void; onBusy: (busy: boolean) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inflight = useRef(false);
  const progress = recording ? state.progress : undefined;
  const exclusive = async (work: () => Promise<void>) => {
    if (inflight.current || closing) return;
    inflight.current = true;
    setBusy(true);
    onBusy(true);
    setError("");
    try { await work(); }
    catch (error) { setError(String(error)); }
    finally { inflight.current = false; setBusy(false); onBusy(false); }
  };
  const start = () => exclusive(async () => {
    setState(await startCalibrationRecording());
    setRecording(true);
  });
  const save = () => exclusive(async () => {
    setState(await saveCalibration());
    setRecording(false);
  });
  const reset = () => exclusive(async () => { setState(await resetCalibration()); });
  const description = recording
    ? t(triggersOnly ? "calibration.triggerCapture" : "calibration.captureDescription")
    : t(state.canApply ? "calibration.startDescription" : "calibration.readOnlyDescription");
  return <>
    <DialogBody>
      <div style={{ ...gridTwoCol, marginBottom: "10px" }}>
        <StickPlot title={t("calibration.leftStick")} xName="left_x" yName="left_y" state={state} progress={triggersOnly ? undefined : progress?.left_stick} />
        <StickPlot title={t("calibration.rightStick")} xName="right_x" yName="right_y" state={state} progress={triggersOnly ? undefined : progress?.right_stick} />
      </div>
      <div style={{ ...gridTwoCol, marginBottom: "16px" }}>
        <TriggerBar title="LT" name="left_trigger" state={state} progress={progress?.left_trigger} />
        <TriggerBar title="RT" name="right_trigger" state={state} progress={progress?.right_trigger} />
      </div>
      <div style={{ textAlign: "center" }}>{error || description}</div>
    </DialogBody>
    <DialogFooter>
      <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
        {recording ? <DialogButton disabled={closing || busy || !progress?.ready} onClick={save}>{t("calibration.save")}</DialogButton>
          : state.canApply ? <>
            <DialogButton disabled={closing || busy} onClick={start}>
              {t(triggersOnly ? "calibration.calibrateTriggers" : "calibration.start")}
            </DialogButton>
            {!triggersOnly && <DialogButton disabled={closing || busy} onClick={reset}>{t("calibration.resetDefaults")}</DialogButton>}
          </> : null}
        {back && !recording && <DialogButton disabled={closing || busy} onClick={back}>{t("common.back")}</DialogButton>}
        <DialogButton disabled={closing || busy} onClick={close}>{t("common.close")}</DialogButton>
      </div>
    </DialogFooter>
  </>;
}
