import { DialogBody, DialogButton, DialogControlsSection, DialogFooter, DialogHeader, Dropdown, Field, TextField } from "@decky/ui";
import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { t, translateLabel } from "../i18n";
import { slugifyCurveName } from "../lib/fanCurve";
import { clone, titleCase } from "../lib/util";
import { ArmadaModalRoot } from "./ArmadaModalRoot";
import type { CurvesState } from "../types";

export function CreateCurveModal({
  initial,
  setDraft,
  initialBaseCurve,
  onCreated,
  closeModal,
}: {
  initial: CurvesState;
  setDraft: Dispatch<SetStateAction<CurvesState | null>>;
  initialBaseCurve: string;
  onCreated: (name: string) => void;
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
    setDraft((current) => {
      if (!current || current.fanCurves[name]) return current;
      const next = clone(current);
      next.fanCurves[name] = {
        label: titleCase(name.replace(/_/g, " ")),
        curve: source.curve,
      };
      return next;
    });
    onCreated(name);
    closeModal?.();
  };

  return (
    <ArmadaModalRoot onCancel={() => closeModal?.()}>
      <DialogBody className="afc-scope">
        <DialogHeader>{t("fanCurve.create")}</DialogHeader>
        <DialogControlsSection>
          <TextField
            label={t("fanCurve.name")}
            description={t("fanCurve.nameRequirements")}
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
          />
          <Field
            label={t("fanCurve.base")}
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
        <div className="afc-note">
          {t("fanCurve.createDescription")}
        </div>
      </DialogBody>
      <DialogFooter className="armada-control-dialog-footer">
        <DialogButton onClick={createCurve} disabled={!canCreate}>
          {t("fanCurve.create")}
        </DialogButton>
        <DialogButton onClick={() => closeModal?.()}>{t("common.cancel")}</DialogButton>
      </DialogFooter>
    </ArmadaModalRoot>
  );
}
