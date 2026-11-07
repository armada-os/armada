import { toaster } from "@decky/api";
import { useRef, useState } from "react";
import { PanelSection } from "@decky/ui";
import type { Dispatch, SetStateAction } from "react";
import { getControllerConfig, setGyroEnabled as applyGyroEnabled, setControllerType as applyControllerType } from "../backend";
import { openCalibration } from "../components/Calibration";
import { ButtonRow, ReadOnlyRow, SectionDescription, SelectEdit, ToggleRow } from "../components/widgets";
import { getCurrentLocale, t, translateLabel } from "../i18n";
import { createConfigMutation, markConfigFieldChange } from "../lib/configMutation";
import type { Config, ControllerConfig } from "../types";

const saveGyro = createConfigMutation("gyro", async (gyro) => ({ ...gyro, enabled: await applyGyroEnabled(gyro.enabled) }), { optimistic: false, read: getControllerConfig });
const saveControllerType = createConfigMutation("controllerType", applyControllerType, { read: getControllerConfig });

export function Controller({ config, setConfig }: {
  config: Config & ControllerConfig;
  setConfig: Dispatch<SetStateAction<Config | null>>;
}) {
  const [gyroSaving, setGyroSaving] = useState(false);
  const gyroPending = useRef(false);
  const setGyroEnabled = async (enabled: boolean) => {
    if (gyroPending.current) return;
    gyroPending.current = true;
    setGyroSaving(true);
    try {
      await saveGyro(config, setConfig, { ...config.gyro, enabled }, (error) => {
        toaster.toast({ title: t("settings.gyroError"), body: String(error) });
      });
    } finally {
      gyroPending.current = false;
      setGyroSaving(false);
    }
  };
  const setControllerType = (value: string) => saveControllerType(config, setConfig, value);
  const calibratedAt = config.calibratedAt ? new Date(config.calibratedAt) : null;
  const calibratedDate = calibratedAt && Number.isFinite(calibratedAt.getTime())
    ? new Intl.DateTimeFormat(getCurrentLocale(), { dateStyle: "medium" }).format(calibratedAt)
    : config.hasCalibration === false ? t("common.never") : t("common.unknown");
  const startCalibration = () => openCalibration((state) => {
    markConfigFieldChange(setConfig, "calibratedAt");
    markConfigFieldChange(setConfig, "hasCalibration");
    setConfig((current) => current ? { ...current, calibratedAt: state.calibratedAt ?? null, hasCalibration: state.hasCalibration ?? state.saved ?? !!state.calibratedAt } : current);
  });

  return (
    <>
      <PanelSection title={t("controller.emulationTitle")}>
        <SectionDescription>{t("controller.emulationDescription")}</SectionDescription>
        <SelectEdit
          label={t("settings.emulation")}
          value={config.controllerType || "deck-uhid"}
          options={(config.controllerTypes || []).map((option) => ({ ...option, label: translateLabel(option.label) }))}
          onChange={setControllerType}
        />
        {config.gyro.supported ? <ToggleRow label={t("settings.enableGyro")} value={config.gyro.enabled} disabled={gyroSaving} onChange={setGyroEnabled} /> : null}
      </PanelSection>
      <PanelSection title={t("controller.calibrationTitle")}>
        <ReadOnlyRow label={t("controller.lastCalibrated")} description={calibratedDate} />
        <ButtonRow layout="below" onClick={startCalibration}>{t("calibration.start")}</ButtonRow>
      </PanelSection>
    </>
  );
}
