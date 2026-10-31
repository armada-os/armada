import { showArmadaModal } from "../components/modalFocusView";
import { Field, PanelSection } from "@decky/ui";
import { useRef } from "react";
import type { Dispatch, SetStateAction } from "react";
import { CreateCurveModal } from "../components/CreateCurveModal";
import { FanCurveEditorModal } from "../components/FanCurveEditorModal";
import { LoadingState } from "../components/LoadingState";
import { ButtonRow, SectionDescription } from "../components/widgets";
import type { BackendState } from "../hooks/useBackendState";
import { t, translateLabel } from "../i18n";
import { titleCase } from "../lib/util";
import { markConfigFieldChange } from "../lib/configMutation";
import type { Config, CurvesState, FanCurve, ProfilesConfig } from "../types";
import { PowerProfileEditorModal } from "./Power";

export function Profiles({ config, setConfig, state }: {
  config: Config & ProfilesConfig;
  setConfig: Dispatch<SetStateAction<Config | null>>;
  state: BackendState<CurvesState>;
}) {
  const { value: curves, setValue: setCurves, error, refresh, loading } = state;
  const latestConfig = useRef(config);
  latestConfig.current = config;

  const fanSaved = (next: CurvesState) => {
    markConfigFieldChange(setConfig, "power");
    setCurves(next);
    setConfig((current) => current?.power ? { ...current, power: { ...current.power, fan_curves: next.fanCurves } } : current);
  };
  const editFan = (id: string, createdCurve?: FanCurve) => {
    if (!curves) return;
    showArmadaModal(<FanCurveEditorModal initial={curves} curveId={id} createdCurve={createdCurve} onSaved={fanSaved} />);
  };
  const createFan = () => {
    if (!curves) return;
    showArmadaModal(<CreateCurveModal
      initial={curves}
      initialBaseCurve={curves.profiles[curves.activeProfile]?.fan_curve || ""}
      onCreated={editFan}
    />);
  };
  const editPower = (profileId: string) => showArmadaModal(<PowerProfileEditorModal
    profileId={profileId}
    getLatestConfig={() => latestConfig.current}
    setConfig={setConfig}
    onSaved={(next) => setCurves((current) => current ? {
      ...current,
      profiles: { ...current.profiles, [profileId]: next.power.profiles[profileId] },
    } : current)}
  />);

  if (loading || (!curves && !error)) return <LoadingState label={t("common.loadingSettings")} />;

  return <div>
    <PanelSection title={t("profiles.fans")}>
      <SectionDescription>{t("profiles.fansDescription")}</SectionDescription>
      {error ? <>
        <Field label={t("profiles.loadingError")} description={error} bottomSeparator="none" />
        <ButtonRow layout="below" onClick={() => { void refresh(); }}>{t("common.retry")}</ButtonRow>
      </> : null}
      {curves ? <>
        {Object.entries(curves.fanCurves).map(([id, curve]) => <ButtonRow key={id} layout="below" onClick={() => editFan(id)}>
          {translateLabel(curve.label || titleCase(id))}
        </ButtonRow>)}
        <ButtonRow variant="primary" layout="below" disabled={!Object.keys(curves.fanCurves).length} onClick={createFan}>{t("fanCurve.add")}</ButtonRow>
      </> : null}
    </PanelSection>
    <PanelSection title={t("profiles.performance")}>
      <SectionDescription>{t("profiles.performanceDescription")}</SectionDescription>
      {Object.entries(config.power.profiles).map(([id, profile]) => <ButtonRow key={id} layout="below" onClick={() => editPower(id)}>
        {translateLabel(profile.label || titleCase(id))}
      </ButtonRow>)}
    </PanelSection>
  </div>;
}
