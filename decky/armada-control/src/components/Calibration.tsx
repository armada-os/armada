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
  const [closeError, setCloseError] = useState("");
  const [triggersOnly, setTriggersOnly] = useState(false);
  const busy = useRef(false);
  const [closing, setClosing] = useState(false);
  const sessionToken = useRef(`${Date.now()}-${Math.random()}`);

  useEffect(() => {
    const token = sessionToken.current;
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

  const close = async () => {
    if (busy.current) return;
    busy.current = true;
    setClosing(true);
    setCloseError("");
    try {
      await endCalibrationSession(sessionToken.current);
      closeModal?.();
    } catch (error) {
      setCloseError(String(error));
    } finally {
      busy.current = false;
      setClosing(false);
    }
  };
  return (
    <ModalRoot onCancel={close}>
      <style>{focusStyles}</style>
      {closing && <div role="status">{t("calibration.applying")}</div>}
      {state && (closeError || error) && <div role="alert">{closeError || error}</div>}
      {!state ? <>
        <DialogBody>{error || t("calibration.checking")}</DialogBody>
        <DialogFooter><DialogButton onClick={close}>{t("common.close")}</DialogButton></DialogFooter>
      </> : state.calibration?.sticks === "mcu" && !triggersOnly ? (
        <McuCalibration state={state} closing={closing} close={close} onBusy={(value) => { if (!closing) busy.current = value; }}
          calibrateTriggers={() => setTriggersOnly(true)} />
      ) : (
        <LegacyCalibration closing={closing} state={state} setState={setState} close={close} triggersOnly={triggersOnly} onBusy={(value) => { if (!closing) busy.current = value; }}
          back={triggersOnly ? () => setTriggersOnly(false) : undefined} />
      )}
    </ModalRoot>
  );
}

export function openCalibration() {
  showModal(<CalibrationModal />);
}
