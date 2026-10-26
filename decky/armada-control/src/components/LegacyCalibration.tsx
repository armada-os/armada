import { DialogBody, DialogButton, DialogFooter } from "@decky/ui";
import { useState } from "react";
import { resetCalibration, saveCalibration, startCalibrationRecording } from "../backend";
import { t } from "../i18n";
import { useExclusive } from "../lib/useExclusive";
import type { CalibrationState } from "../types";
import { gridTwoCol, StickPlot, TriggerBar } from "./CalibrationPlots";

export function LegacyCalibration({ state, setState, close, onBusy, closing }: {
  state: CalibrationState; closing: boolean; setState: (state: CalibrationState) => void; close: () => void;
  onBusy: (busy: boolean) => void;
}) {
  const [recording, setRecording] = useState(false);
  const { exclusive, busy, error } = useExclusive(closing, onBusy);
  const progress = recording ? state.progress : undefined;
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
    ? t("calibration.captureDescription")
    : t(state.canApply ? "calibration.startDescription" : "calibration.readOnlyDescription");
  return <>
    <DialogBody>
      <div style={{ ...gridTwoCol, marginBottom: "10px" }}>
        <StickPlot title={t("calibration.leftStick")} xName="left_x" yName="left_y" state={state} progress={progress?.left_stick} />
        <StickPlot title={t("calibration.rightStick")} xName="right_x" yName="right_y" state={state} progress={progress?.right_stick} />
      </div>
      <div style={{ ...gridTwoCol, marginBottom: "16px" }}>
        <TriggerBar title="LT" name="left_trigger" state={state} progress={progress?.left_trigger} />
        <TriggerBar title="RT" name="right_trigger" state={state} progress={progress?.right_trigger} />
      </div>
      <div style={{ textAlign: "center" }}>{error || description}</div>
    </DialogBody>
    <DialogFooter className="armada-control-dialog-footer">
        {recording ? <DialogButton disabled={closing || busy || !progress?.ready} onClick={save}>{t("calibration.save")}</DialogButton>
          : state.canApply ? <>
            <DialogButton disabled={closing || busy} onClick={start}>{t("calibration.start")}</DialogButton>
            <DialogButton disabled={closing || busy} onClick={reset}>{t("calibration.resetDefaults")}</DialogButton>
          </> : null}
        <DialogButton disabled={closing || busy} onClick={close}>{t("common.close")}</DialogButton>
    </DialogFooter>
  </>;
}
