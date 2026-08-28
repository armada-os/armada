import { DialogBody, DialogButton, DialogFooter, ModalRoot } from "@decky/ui";
import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { saveFanCurves } from "../backend";
import { FanCurveGraphEditor } from "./FanCurveEditor";
import { useCurrentTemp } from "../hooks/useCurrentTemp";
import { useFanCurvesSave } from "../hooks/useFanCurvesSave";
import { styles } from "../styles";
import type { CurvesState } from "../types";

export function FanCurveEditorModal({
  initial,
  setDraft,
  initialSelected,
  onSelectedChange,
  saved,
  onSaved,
  closeModal,
}: {
  initial: CurvesState;
  setDraft: Dispatch<SetStateAction<CurvesState | null>>;
  initialSelected: string;
  onSelectedChange: (value: string) => void;
  saved: CurvesState | null;
  onSaved: (next: CurvesState) => void;
  closeModal?: () => void;
}) {
  const [state, setState] = useState(initial);
  const [selected, setSelected] = useState(initialSelected);
  const [savedState, setSavedState] = useState(saved);
  const currentTemp = useCurrentTemp();
  const setBoth: Dispatch<SetStateAction<CurvesState | null>> = (value) => {
    setState((current) => {
      const next = typeof value === "function"
        ? (value as (c: CurvesState | null) => CurvesState | null)(current)
        : value;
      return next ?? current;
    });
    setDraft(value);
  };
  const setSelectedBoth = (value: string) => {
    setSelected(value);
    onSelectedChange(value);
  };
  const { dirty, saving, saveError, handleSave, handleRevert } = useFanCurvesSave({
    working: state,
    saved: savedState,
    setSaved: setSavedState,
    setWorking: setBoth,
    save: saveFanCurves,
    onSaved,
  });

  return (
    // bAllowFullSize -- without it GenericDialog clamps to a small default size.
    <ModalRoot bAllowFullSize onCancel={() => closeModal?.()}>
      <style>{styles}</style>
      <DialogBody className="afc-scope">
        {saveError ? <div className="afc-error">{saveError}</div> : null}
        <FanCurveGraphEditor
          state={state}
          setState={setBoth}
          selected={selected}
          onSelectedChange={setSelectedBoth}
          currentTemp={currentTemp}
        />
      </DialogBody>
      {/* Column layout: DialogFooter's default row doesn't hold up with three buttons. */}
      <DialogFooter className="afc-modal-footer">
        <div className="afc-modal-footer-row">
          <DialogButton
            className="afc-modal-footer-half"
            onClick={handleSave}
            disabled={!dirty || saving}
          >
            {saving ? "Saving..." : "Save Changes"}
          </DialogButton>
          <DialogButton
            className="afc-modal-footer-half"
            onClick={handleRevert}
            disabled={!dirty || saving}
          >
            Revert Changes
          </DialogButton>
        </div>
        <DialogButton className="afc-modal-footer-full" onClick={() => closeModal?.()}>
          Close
        </DialogButton>
      </DialogFooter>
    </ModalRoot>
  );
}
