import { DialogBody, DialogButton, DialogFooter, ModalRoot, showModal } from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import { beginCalibrationSession, endCalibrationSession, getControllerState } from "../backend";
import { t } from "../i18n";
import type { CalibrationState } from "../types";
import { focusStyles } from "./CalibrationPlots";
import { LegacyCalibration } from "./LegacyCalibration";
import { McuCalibration } from "./McuCalibration";

function CalibrationModal({ closeModal }: { closeModal?: () => void }) {
  const [state, setState] = useState<CalibrationState | null>(null);
  const [error, setError] = useState("");
  const [triggersOnly, setTriggersOnly] = useState(false);
  const busy = useRef(false);

  useEffect(() => {
    const token = `${Date.now()}-${Math.random()}`;
    let cancelled = false;
    let timer: number;
    const tick = async () => {
      try {
        const next = await getControllerState();
        if (!cancelled) { setState((current) => ({ ...next, calibration: next.calibration || current?.calibration })); setError(""); }
      } catch (error) {
        if (!cancelled) setError(String(error));
      }
      if (!cancelled) timer = window.setTimeout(tick, 50);
    };
    // Calibration input must not navigate Steam behind the modal.
    beginCalibrationSession(token).then(() => {
      if (!cancelled) tick();
      else endCalibrationSession(token).catch(() => {});
    }).catch((error) => {
      if (!cancelled) setError(String(error));
    });
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      endCalibrationSession(token).catch(() => {});
    };
  }, []);

  const close = () => { if (!busy.current) closeModal?.(); };
  return (
    <ModalRoot onCancel={close}>
      <style>{focusStyles}</style>
      {!state ? <>
        <DialogBody>{error || t("calibration.checking")}</DialogBody>
        <DialogFooter><DialogButton onClick={close}>{t("common.close")}</DialogButton></DialogFooter>
      </> : state.calibration?.sticks === "mcu" && !triggersOnly ? (
        <McuCalibration state={state} close={close} onBusy={(value) => { busy.current = value; }}
          calibrateTriggers={() => setTriggersOnly(true)} />
      ) : (
        <LegacyCalibration state={state} setState={setState} close={close} triggersOnly={triggersOnly}
          back={triggersOnly ? () => setTriggersOnly(false) : undefined} />
      )}
    </ModalRoot>
  );
}

export function openCalibration() {
  showModal(<CalibrationModal />);
}
