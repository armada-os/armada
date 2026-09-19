import { DialogBody, DialogButton, DialogFooter } from "@decky/ui";
import { useEffect, useState } from "react";
import { resetCalibration, saveCalibration } from "../backend";
import { t } from "../i18n";
import { makeCapture, updateCapture } from "../lib/calibration";
import type { CalibrationState, Capture } from "../types";
import { gridTwoCol, StickPlot, TriggerBar } from "./CalibrationPlots";

export function LegacyCalibration({ state, setState, close, triggersOnly = false, back }: {
  state: CalibrationState; setState: (state: CalibrationState) => void; close: () => void;
  triggersOnly?: boolean; back?: () => void;
}) {
  const [recording, setRecording] = useState(false);
  const [capture, setCapture] = useState<Capture | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (recording && state.supported) {
      setCapture((current) => updateCapture(current || makeCapture(state, triggersOnly), state));
    }
  }, [state, recording, triggersOnly]);
  const save = async () => {
    if (!capture) return;
    setBusy(true);
    try { setState(await saveCalibration(capture)); setRecording(false); setCapture(null); }
    catch (error) { setError(String(error)); setRecording(false); }
    finally { setBusy(false); }
  };
  const reset = async () => {
    setBusy(true);
    try { setState(await resetCalibration()); setError(""); }
    catch (error) { setError(String(error)); }
    finally { setBusy(false); }
  };
  const description = recording
    ? t(triggersOnly ? "calibration.triggerCapture" : "calibration.captureDescription")
    : t(state.canApply ? "calibration.startDescription" : "calibration.readOnlyDescription");
  return <>
    <DialogBody>
      <div style={{ ...gridTwoCol, marginBottom: "22px" }}>
        <StickPlot title={t("calibration.leftStick")} xName="left_x" yName="left_y" state={state} />
        <StickPlot title={t("calibration.rightStick")} xName="right_x" yName="right_y" state={state} />
      </div>
      <div style={{ ...gridTwoCol, marginBottom: "16px" }}>
        <TriggerBar title="LT" name="left_trigger" state={state} />
        <TriggerBar title="RT" name="right_trigger" state={state} />
      </div>
      <div style={{ textAlign: "center" }}>{error || description}</div>
    </DialogBody>
    <DialogFooter>
      <div className="armada-cal-footer" style={{ display: "flex", gap: "10px" }}>
        {recording ? <DialogButton disabled={busy || !capture} onClick={save}>{t("calibration.save")}</DialogButton>
          : state.canApply ? <>
            <DialogButton disabled={busy} onClick={() => { setError(""); setCapture(null); setRecording(true); }}>
              {t(triggersOnly ? "calibration.calibrateTriggers" : "calibration.start")}
            </DialogButton>
            {!triggersOnly && <DialogButton disabled={busy} onClick={reset}>{t("calibration.resetDefaults")}</DialogButton>}
          </> : null}
        {back && <DialogButton disabled={busy} onClick={back}>{t("common.back")}</DialogButton>}
        <DialogButton onClick={close}>{t("common.close")}</DialogButton>
      </div>
    </DialogFooter>
  </>;
}
