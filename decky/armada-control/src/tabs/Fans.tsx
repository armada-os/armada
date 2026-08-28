import { ButtonItem, Field, PanelSection, PanelSectionRow, showModal } from "@decky/ui";
import { useCallback, useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { getFansState, saveFanCurves } from "../backend";
import { CreateCurveModal } from "../components/CreateCurveModal";
import { FanCurveEditor } from "../components/FanCurveEditor";
import { FanCurveEditorModal } from "../components/FanCurveEditorModal";
import { useCurrentTemp } from "../hooks/useCurrentTemp";
import { useFanCurvesSave } from "../hooks/useFanCurvesSave";
import { clone } from "../lib/util";
import type { Config, CurvesState } from "../types";

export function Fans({ setConfig }: {
  setConfig: Dispatch<SetStateAction<Config | null>>;
}) {
  const [saved, setSaved] = useState<CurvesState | null>(null);
  const [draft, setDraft] = useState<CurvesState | null>(null);
  const [message, setMessage] = useState("Loading");
  const [selectedCurve, setSelectedCurve] = useState("");
  const currentTemp = useCurrentTemp();

  const load = useCallback(async () => {
    try {
      const next = await getFansState();
      setSaved(next);
      setDraft(clone(next));
      const names = Object.keys(next.fanCurves || {}).sort();
      const activeCurve = next.profiles?.[next.activeProfile]?.fan_curve;
      setSelectedCurve(activeCurve && names.includes(activeCurve) ? activeCurve : names[0] || "");
    } catch (error) {
      setMessage(String(error));
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const syncSharedFanCurves = (next: CurvesState) => {
    setConfig((current) =>
      current ? { ...current, power: { ...current.power, fan_curves: next.fanCurves } } : current,
    );
  };

  const { dirty, saving, saveError, handleSave, handleRevert } = useFanCurvesSave({
    working: draft,
    saved,
    setSaved,
    setWorking: setDraft,
    save: saveFanCurves,
    onSaved: syncSharedFanCurves,
  });

  if (!draft) {
    return (
      <PanelSection title="Armada Fans">
        <Field label={message} />
      </PanelSection>
    );
  }

  const openFullscreen = () =>
    showModal(
      <FanCurveEditorModal
        initial={draft}
        setDraft={setDraft}
        initialSelected={selectedCurve}
        onSelectedChange={setSelectedCurve}
        saved={saved}
        onSaved={(next) => {
          setSaved(next);
          syncSharedFanCurves(next);
        }}
      />,
    );
  const openCreateCurve = () =>
    showModal(
      <CreateCurveModal
        initial={draft}
        setDraft={setDraft}
        initialBaseCurve={selectedCurve}
        onCreated={setSelectedCurve}
      />,
    );

  return (
    <div className="afc-scope">
      {saveError ? <div className="afc-error">{saveError}</div> : null}
      <FanCurveEditor
        state={draft}
        setState={setDraft}
        selected={selectedCurve}
        onSelectedChange={setSelectedCurve}
        onOpenFullscreen={openFullscreen}
        onOpenCreateCurve={openCreateCurve}
        currentTemp={currentTemp}
      />
      <PanelSection title="SAVE">
        <PanelSectionRow>
          <div className="afc-control-inset">
            <ButtonItem layout="below" onClick={handleSave} disabled={!dirty || saving}>
              {saving ? "Saving..." : "Save Changes"}
            </ButtonItem>
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <div className="afc-control-inset">
            <ButtonItem layout="below" onClick={handleRevert} disabled={!dirty || saving}>
              Revert Changes
            </ButtonItem>
          </div>
        </PanelSectionRow>
        {dirty ? <div className="afc-note">You have unsaved changes.</div> : null}
      </PanelSection>
    </div>
  );
}
