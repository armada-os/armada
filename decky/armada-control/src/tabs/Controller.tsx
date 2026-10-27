import { toaster } from "@decky/api";
import { useRef, useState } from "react";
import { PanelSection } from "@decky/ui";
import type { Dispatch, SetStateAction } from "react";
import { getControllerConfig, setGyroEnabled as applyGyroEnabled, setGyroOrientation as applyGyroOrientation, setControllerType as applyControllerType } from "../backend";
import { openCalibration } from "../components/Calibration";
import { ButtonRow, ReadOnlyRow, SectionDescription, SelectEdit, ToggleRow } from "../components/widgets";
import { getCurrentLocale, t, translateLabel } from "../i18n";
import { createConfigMutation, markConfigFieldChange } from "../lib/configMutation";
import type { Config, ControllerConfig, GyroOrientation } from "../types";

const saveGyro = createConfigMutation("gyro", async (gyro) => ({ ...gyro, enabled: await applyGyroEnabled(gyro.enabled) }), { optimistic: false, read: getControllerConfig });
const saveGyroOrientation = createConfigMutation("gyro", async (gyro) => ({ ...gyro, orientation: await applyGyroOrientation(gyro.orientation) }), { optimistic: false, read: getControllerConfig });
const saveControllerType = createConfigMutation("controllerType", applyControllerType, { read: getControllerConfig });

export function Controller({ config, setConfig }: {
  config: Config & ControllerConfig;
  setConfig: Dispatch<SetStateAction<Config | null>>;
}) {
  const [gyroSaving, setGyroSaving] = useState(false);
  const gyroPending = useRef(false);
  const updateGyro = async (value: ControllerConfig["gyro"], save: typeof saveGyro) => {
    if (gyroPending.current) return;
    gyroPending.current = true;
    setGyroSaving(true);
    try {
      await save(config, setConfig, value, (error) => {
        toaster.toast({ title: t("settings.gyroError"), body: String(error) });
      });
    } finally {
      gyroPending.current = false;
      setGyroSaving(false);
    }
  };
  const setGyroEnabled = (enabled: boolean) => updateGyro({ ...config.gyro, enabled }, saveGyro);
  const setGyroOrientation = (orientation: GyroOrientation) => updateGyro({ ...config.gyro, orientation }, saveGyroOrientation);
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
        {config.gyro.supported && config.gyro.enabled ? <SelectEdit
          label={t("settings.gyroOrientation")}
          value={config.gyro.orientation}
          options={[
            { data: "default", label: t("settings.gyroOrientationDefault") },
            { data: "pitch-roll", label: t("settings.gyroOrientationPitchRoll") },
            { data: "pitch-yaw", label: t("settings.gyroOrientationPitchYaw") },
            { data: "roll-yaw", label: t("settings.gyroOrientationRollYaw") },
            ...(config.gyro.orientation === "custom" ? [{ data: "custom", label: t("settings.gyroOrientationCustom") }] : []),
          ]}
          disabled={gyroSaving}
          onChange={setGyroOrientation}
        /> : null}
      </PanelSection>
      <PanelSection title={t("controller.calibrationTitle")}>
        <ReadOnlyRow label={t("controller.lastCalibrated")} description={calibratedDate} />
        <ButtonRow layout="below" onClick={startCalibration}>{t("calibration.start")}</ButtonRow>
      </PanelSection>
    </>
  );
}
