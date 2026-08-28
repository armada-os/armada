import { useState } from "react";
import { clone } from "../lib/util";
import type { CurvesState, FanCurve, FanSettings } from "../types";

interface UseFanCurvesSaveOptions {
  working: CurvesState | null;
  saved: CurvesState | null;
  setSaved: (next: CurvesState) => void;
  setWorking: (next: CurvesState) => void;
  save: (fanCurves: Record<string, FanCurve>, fanSettings: FanSettings) => Promise<CurvesState>;
  onSaved?: (next: CurvesState) => void;
}

export function useFanCurvesSave({ working, saved, setSaved, setWorking, save, onSaved }: UseFanCurvesSaveOptions) {
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const dirty = !!saved && !!working && JSON.stringify(saved.fanCurves) + JSON.stringify(saved.fanSettings) !==
    JSON.stringify(working.fanCurves) + JSON.stringify(working.fanSettings);

  const handleSave = async () => {
    if (!working || saving) return;
    setSaving(true);
    try {
      const next = await save(working.fanCurves, working.fanSettings);
      setSaveError("");
      setWorking(clone(next));
      setSaved(next);
      onSaved?.(next);
    } catch (error) {
      setSaveError(String(error));
    } finally {
      setSaving(false);
    }
  };

  const handleRevert = () => {
    if (!saved) return;
    setSaveError("");
    setWorking(clone(saved));
  };

  return { dirty, saving, saveError, handleSave, handleRevert };
}
