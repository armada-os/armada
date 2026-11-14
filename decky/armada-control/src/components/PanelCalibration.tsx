import { toaster } from "@decky/api";
import { DialogBody, DialogButton, DialogButtonPrimary, DialogControlsSection, Focusable } from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import { calibratePanel, getPanelCalibration, getPanelRate, savePanel, setPanel, stepPanel } from "../backend";
import { t } from "../i18n";
import type { PanelAttr, PanelCalibration as PanelState, PanelRate } from "../types";
import { ArmadaDialogFooter, ArmadaDialogHeader, ArmadaModalRoot } from "./ArmadaModalRoot";
import { showArmadaModal } from "./modalFocusView";
import { ButtonRow, CompactButton, ReadOnlyRow } from "./widgets";

const formatHz = (hz: number) => `${hz.toFixed(2)} Hz`;

export function PanelCalibration({ supported }: { supported: boolean }) {
  if (!supported) return null;

  return (
    <ButtonRow layout="below" label={t("display.label")} onClick={() => showArmadaModal(<PanelCalibrationModal />)}>
      {t("calibration.launch")}
    </ButtonRow>
  );
}

function PanelCalibrationModal({ closeModal }: { closeModal?: () => void }) {
  const [state, setState] = useState<PanelState | null>(null);
  const [rate, setRate] = useState<PanelRate | null | undefined>(undefined);
  const [busy, setBusy] = useState<"measuring" | "calibrating" | "saving" | null>(null);
  const [rangeEnd, setRangeEnd] = useState<"faster" | "slower" | null>(null);
  const busyRef = useRef(false);
  const closing = useRef(false);
  const pending = useRef<Promise<void>>(Promise.resolve());
  const openedWith = useRef<PanelState["live"]>(undefined);

  const refresh = async () => {
    const [next, nextRate] = await Promise.all([getPanelCalibration(), getPanelRate()]);
    setState(next);
    setRate(nextRate);
    return next;
  };

  const setLive = (attr: PanelAttr, value: number) =>
    setState((current) => current && { ...current, live: { ...current.live!, [attr]: value } });

  const run = (kind: "measuring" | "calibrating" | "saving", action: () => Promise<void>) => {
    if (busyRef.current || closing.current) return;
    busyRef.current = true;
    setBusy(kind);
    pending.current = action()
      .catch((error) => {
        if (!closing.current) toaster.toast({ title: t("display.calibrateFailed"), body: String(error) });
      })
      .finally(() => {
        busyRef.current = false;
        setBusy(null);
      });
  };

  useEffect(() => {
    run("measuring", async () => {
      openedWith.current = (await refresh().catch(() => { setRate(null); return null; }))?.live;
    });
  }, []);

  const attr = rate?.attr ?? null;
  const live = attr ? state?.live?.[attr] ?? null : null;
  const fallback = attr ? state?.defaults?.[attr] ?? null : null;

  const auto = () =>
    run("calibrating", async () => {
      setRangeEnd(null);
      try {
        await calibratePanel();
      } catch {
        if (!closing.current) toaster.toast({ title: t("display.calibrateFailed"), body: t("display.errorCalibrate") });
      }
      await refresh();
    });

  const step = (direction: "faster" | "slower") =>
    run("measuring", async () => {
      if (!attr || live == null) return;
      setLive(attr, direction === "faster" ? live - 1 : live + 1);
      try {
        const result = await stepPanel(attr, direction);
        setRangeEnd(result.limit === "range" ? direction : null);
        setLive(attr, result.value);
        setRate((current) => current && { ...current, hz: result.hz });
      } catch (error) {
        setLive(attr, live);
        throw error;
      }
    });

  // Save on the panel default clears the setting.
  const reset = () =>
    run("measuring", async () => {
      if (!attr || fallback == null) return;
      await setPanel(attr, fallback);
      setRangeEnd(null);
      setLive(attr, fallback);
      await refresh();
    });

  const save = () =>
    run("saving", async () => {
      if (!attr) return;
      // A Cancel after this point must not undo what is being saved.
      closing.current = true;
      try {
        await savePanel(attr);
      } catch (error) {
        closing.current = false;
        throw error;
      }
      closeModal?.();
    });

  const cancel = async () => {
    if (closing.current) return;
    closing.current = true;
    await pending.current;
    const current = (await getPanelCalibration().catch(() => null))?.live;
    let restored = true;
    for (const [name, value] of Object.entries(openedWith.current ?? {}) as [PanelAttr, number | null][]) {
      if (value != null && current?.[name] !== value) {
        restored = (await setPanel(name, value).then(() => true, () => false)) && restored;
      }
    }
    if (!restored) toaster.toast({ title: t("display.calibrateFailed"), body: t("display.errorRestore") });
    closeModal?.();
  };

  // Positive is faster: a lower frame length is a faster refresh.
  const offset = live != null && fallback != null ? fallback - live : null;
  const headline = offset == null ? "-" : offset < 0 ? `−${-offset}` : `+${offset}`;
  const measured = rate === undefined || busy === "measuring" || busy === "calibrating"
    ? t("display.measuring")
    : rate?.hz != null
      ? formatHz(rate.hz)
      : t("display.unavailable");

  const controlsDisabled = busy != null || !attr;
  const saveDisabled = controlsDisabled || live == null;

  return (
    <ArmadaModalRoot onOK={save} onCancel={() => { void cancel(); }} bOKDisabled={saveDisabled} bCancelDisabled={busy === "saving"} bDisableBackgroundDismiss={busy === "saving"}>
      <ArmadaDialogHeader>{t("display.label")}</ArmadaDialogHeader>
      <DialogBody>
        <DialogControlsSection>
          <ReadOnlyRow label={measured} />
          <ButtonRow layout="below" onClick={auto} disabled={controlsDisabled}>
            {t(busy === "calibrating" ? "display.calibrating" : "display.autoCalibrate")}
          </ButtonRow>
          <Focusable className="armada-calibration-label" flow-children="row" tabIndex={-1} noFocusRing>
            <CompactButton onClick={() => step("slower")} disabled={controlsDisabled || rangeEnd === "slower"}>−</CompactButton>
            <span>{headline}</span>
            <CompactButton onClick={() => step("faster")} disabled={controlsDisabled || rangeEnd === "faster"}>+</CompactButton>
          </Focusable>
        </DialogControlsSection>
      </DialogBody>
      <ArmadaDialogFooter>
        <DialogButtonPrimary onClick={save} disabled={saveDisabled}>{t("common.save")}</DialogButtonPrimary>
        <DialogButton onClick={() => { void cancel(); }} disabled={busy === "saving"}>{t("common.cancel")}</DialogButton>
        <DialogButton onClick={reset} disabled={controlsDisabled || fallback == null || live === fallback}>{t("display.reset")}</DialogButton>
      </ArmadaDialogFooter>
    </ArmadaModalRoot>
  );
}
