import { DialogBody, DialogButton, DialogButtonPrimary, DialogControlsSection, Dropdown, Field } from "@decky/ui";
import { useState } from "react";
import { t, translateLabel } from "../i18n";
import { slugifyCurveName } from "../lib/fanCurve";
import { titleCase } from "../lib/util";
import { ArmadaDialogFooter, ArmadaDialogHeader, ArmadaModalRoot } from "./ArmadaModalRoot";
import { SupportingText, TextEdit } from "./widgets";
import type { CurvesState, FanCurve } from "../types";

export function CreateCurveModal({
  initial,
  initialBaseCurve,
  onCreated,
  closeModal,
}: {
  initial: CurvesState;
  initialBaseCurve: string;
  onCreated: (name: string, curve: FanCurve) => void;
  closeModal?: () => void;
}) {
  const names = Object.keys(initial.fanCurves || {}).sort();
  const defaultBase = names.includes(initialBaseCurve) ? initialBaseCurve : names[0] || "";
  const [newName, setNewName] = useState("");
  const [baseCurve, setBaseCurve] = useState(defaultBase);
  const name = slugifyCurveName(newName);
  const duplicateName = !!name && !!initial.fanCurves[name];
  const canCreate = !!name && !!baseCurve && !duplicateName;
  const createCurve = () => {
    if (!canCreate) return;
    const source = initial.fanCurves[baseCurve];
    if (!source) return;
    closeModal?.();
    onCreated(name, { ...source, label: newName.trim() });
  };

  return (
    <ArmadaModalRoot onCancel={() => closeModal?.()}>
      <ArmadaDialogHeader>{t("fanCurve.create")}</ArmadaDialogHeader>
      <DialogBody className="afc-scope">
        <DialogControlsSection>
          <TextEdit
            label={t("fanCurve.name")}
            description={t("fanCurve.nameRequirements")}
            value={newName}
            onChange={(value) => setNewName(value.slice(0, 80))}
          />
          <Field
            label={t("fanCurve.base")}
            bottomSeparator="standard"
            childrenLayout="below"
          >
            <Dropdown
              selectedOption={baseCurve}
              rgOptions={names.map((curveName) => ({
                data: curveName,
                label: translateLabel(initial.fanCurves[curveName]?.label || titleCase(curveName)),
              }))}
              onChange={(option) => setBaseCurve(String(option.data))}
            />
          </Field>
        </DialogControlsSection>
        {duplicateName ? (
          <div className="afc-modal-error">{t("fanCurve.nameExists", { name })}</div>
        ) : null}
        <SupportingText>
          {t("fanCurve.createDescription")}
        </SupportingText>
      </DialogBody>
      <ArmadaDialogFooter>
        <DialogButtonPrimary onClick={createCurve} disabled={!canCreate}>
          {t("fanCurve.create")}
        </DialogButtonPrimary>
        <DialogButton onClick={() => closeModal?.()}>{t("common.cancel")}</DialogButton>
      </ArmadaDialogFooter>
    </ArmadaModalRoot>
  );
}
