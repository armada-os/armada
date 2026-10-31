import { showArmadaModal } from "./modalFocusView";
import { DialogBody, DialogButton, DialogButtonPrimary } from "@decky/ui";
import { useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { saveFanCurves } from "../backend";
import { useCurrentTemp } from "../hooks/useCurrentTemp";
import { t, translateLabel } from "../i18n";
import { parseCurve } from "../lib/fanCurve";
import { clone, titleCase } from "../lib/util";
import type { CurvesState, FanCurve } from "../types";
import { ArmadaConfirmModal, ArmadaDialogFooter, ArmadaDialogHeader, ArmadaModalRoot } from "./ArmadaModalRoot";
import { FanCurveEditor } from "./FanCurveEditor";
import { SupportingText } from "./widgets";

export function FanCurveEditorModal({ initial, curveId, createdCurve, onSaved, closeModal }: {
  initial: CurvesState;
  curveId: string;
  createdCurve?: FanCurve;
  onSaved: (next: CurvesState) => void;
  closeModal?: () => void;
}) {
  const [curve, setCurve] = useState(() => clone(createdCurve || initial.fanCurves[curveId]));
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [resetVersion, setResetVersion] = useState(0);
  const busy = useRef(false);
  const currentTemp = useCurrentTemp();
  const label = translateLabel(curve.label || titleCase(curveId));
  const factoryCurve = initial.factoryFanCurves[curveId];
  const profiles = Object.values(initial.profiles).filter((profile) => profile.fan_curve === curveId);
  const custom = !factoryCurve;
  const assigned = profiles.length > 0;
  const valid = !!curve.label.trim() && parseCurve(curve.curve).length > 0;
  const dirty = JSON.stringify(curve) !== JSON.stringify(initial.fanCurves[curveId]);
  const edit: Dispatch<SetStateAction<FanCurve>> = (next) => { if (!busy.current) setCurve(next); };
  const cancel = () => { if (!busy.current) closeModal?.(); };
  const persist = async (remove = false) => {
    if (busy.current || (!remove && !valid)) return;
    busy.current = true;
    setSaving(true);
    setSaveError("");
    try {
      const next = await saveFanCurves(remove ? {} : { [curveId]: { ...curve, label: curve.label.trim() } }, remove ? [curveId] : []);
      onSaved(next);
      closeModal?.();
    } catch (error) {
      setSaveError(String(error));
    } finally {
      busy.current = false;
      setSaving(false);
    }
  };
  const confirmDelete = () => showArmadaModal(<ArmadaConfirmModal
    title={t("fanCurve.delete")}
    description={t("profiles.deleteDescription", { profile: label })}
    confirmText={t("common.delete")}
    cancelText={t("common.cancel")}
    onConfirm={() => { void persist(true); }}
  />);

  return <ArmadaModalRoot bAllowFullSize bDisableBackgroundDismiss={saving} bCancelDisabled={saving} onCancel={cancel}>
    <ArmadaDialogHeader>{t("profiles.editFan", { profile: label })}</ArmadaDialogHeader>
    <DialogBody className="afc-scope">
      {saveError ? <div className="afc-error" role="alert">{saveError}</div> : null}
      {!curve?.label.trim() ? <SupportingText>{t("profiles.nameRequired")}</SupportingText> : null}
      <FanCurveEditor key={resetVersion} curve={curve} setCurve={edit} custom={custom} profiles={profiles} currentTemp={currentTemp} disabled={saving} />
      {custom && assigned ? <SupportingText>{t("profiles.assignedDelete")}</SupportingText> : null}
    </DialogBody>
    <ArmadaDialogFooter>
      <DialogButtonPrimary onClick={() => { void persist(); }} disabled={!dirty || !valid || saving}>
        {saving ? t("common.saving") : t("common.saveChanges")}
      </DialogButtonPrimary>
      <DialogButton onClick={cancel} disabled={saving}>{t("common.cancel")}</DialogButton>
      {!custom ? <DialogButton disabled={saving} onClick={() => {
        setCurve(clone(factoryCurve));
        setResetVersion((current) => current + 1);
      }}>{t("fanCurve.resetFactory")}</DialogButton> : !createdCurve ? <DialogButton disabled={saving || assigned} onClick={confirmDelete}>{t("fanCurve.delete")}</DialogButton> : null}
    </ArmadaDialogFooter>
  </ArmadaModalRoot>;
}
