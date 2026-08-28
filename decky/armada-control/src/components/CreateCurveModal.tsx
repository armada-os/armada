import { DialogBody, DialogButton, DialogFooter, Field, ModalRoot, PanelSectionRow, TextField } from "@decky/ui";
import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { PseudoDropdown } from "./fanWidgets";
import { slugifyCurveName } from "../lib/fanCurve";
import { clone, titleCase } from "../lib/util";
import { styles } from "../styles";
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
    <ModalRoot onCancel={() => closeModal?.()}>
      <style>{styles}</style>
      <DialogBody className="afc-scope">
        <h2 className="afc-modal-title">Create Curve</h2>
        <PanelSectionRow>
          <div className="afc-control-inset">
            <Field
              label="Curve Name"
              description="Letters, numbers, spaces, hyphens, and underscores are supported."
              childrenLayout="below"
              childrenContainerWidth="max"
            >
              <TextField value={newName} onChange={(event) => setNewName(event.target.value)} />
            </Field>
          </div>
        </PanelSectionRow>
        {duplicateName ? (
          <div className="afc-modal-error">A curve named “{name}” already exists.</div>
        ) : null}
        <PseudoDropdown
          label="Base Curve"
          value={baseCurve}
          options={names.map((curveName) => ({
            data: curveName,
            label: initial.fanCurves[curveName]?.label || titleCase(curveName),
          }))}
          onChange={setBaseCurve}
        />
        <div className="afc-note">
          The new curve starts as a copy of the selected base curve. Changes remain unsaved until Save Changes is
          pressed.
        </div>
      </DialogBody>
      <DialogFooter>
        <DialogButton onClick={() => closeModal?.()}>Cancel</DialogButton>
        <DialogButton onClick={createCurve} disabled={!canCreate}>
          Create Curve
        </DialogButton>
      </DialogFooter>
    </ModalRoot>
  );
}
