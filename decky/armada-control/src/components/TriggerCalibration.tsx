import { DialogBody, DialogButton, DialogFooter } from "@decky/ui";
import { useState } from "react";
import { resetCalibration, saveCalibration, startCalibrationRecording } from "../backend";
import { t } from "../i18n";
import { useExclusive } from "../lib/useExclusive";
import type { CalibrationState } from "../types";
import { gridTwoCol, StickPlot, TriggerBar } from "./CalibrationPlots";

// Software trigger calibration for boards whose sticks are calibrated on the MCU.
export function TriggerCalibration({ state, setState, close, back, onBusy, closing }: {
  state: CalibrationState; closing: boolean; setState: (state: CalibrationState) => void; close: () => void;
  back: () => void; onBusy: (busy: boolean) => void;
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
  const reset = () => exclusive(async () => { setState(await resetCalibration(true)); });
  return <>
    <DialogBody>
      <div style={{ ...gridTwoCol, marginBottom: "10px" }}>
        <StickPlot title={t("calibration.leftStick")} xName="left_x" yName="left_y" state={state} />
        <StickPlot title={t("calibration.rightStick")} xName="right_x" yName="right_y" state={state} />
      </div>
      <div style={{ ...gridTwoCol, marginBottom: "16px" }}>
        <TriggerBar title="LT" name="left_trigger" state={state} progress={progress?.left_trigger} />
        <TriggerBar title="RT" name="right_trigger" state={state} progress={progress?.right_trigger} />
      </div>
      <div style={{ textAlign: "center" }}>{error || t("calibration.triggerCapture")}</div>
    </DialogBody>
    <DialogFooter className="armada-control-dialog-footer">
        {recording ? <DialogButton disabled={closing || busy || !progress?.ready} onClick={save}>{t("calibration.save")}</DialogButton>
          : <>
            <DialogButton disabled={closing || busy} onClick={start}>{t("calibration.calibrateTriggers")}</DialogButton>
            <DialogButton disabled={closing || busy} onClick={reset}>{t("calibration.resetDefaults")}</DialogButton>
            <DialogButton disabled={closing || busy} onClick={back}>{t("common.back")}</DialogButton>
          </>}
        <DialogButton disabled={closing || busy} onClick={close}>{t("common.close")}</DialogButton>
    </DialogFooter>
  </>;
}
