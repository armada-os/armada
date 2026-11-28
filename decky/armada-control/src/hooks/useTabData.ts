import { useState } from "react";
import type { Dispatch, RefObject, SetStateAction } from "react";
import { getAboutConfig, getControllerConfig, getDeviceConfig, getExperimentalConfig, getFansState, getProfilesConfig, getRgb, getSleepLogsStatus } from "../backend";
import { aboutConfigFields, controllerConfigFields, deviceConfigFields, experimentalConfigFields, profilesConfigFields } from "../lib/configSections";
import type { Config } from "../types";
import { useBackendState } from "./useBackendState";
import { useConfigSection } from "./useConfigSection";
import { waitForPendingApplies } from "./useDebouncedApply";
import { useGameSettingsState } from "./useGameSettingsState";

const readRgb = async () => { await waitForPendingApplies(); return getRgb(); };
const readLogs = async () => { await waitForPendingApplies(); return getSleepLogsStatus(); };

export function useTabData(config: Config | null, setConfig: Dispatch<SetStateAction<Config | null>>, active: string, host: RefObject<HTMLDivElement | null>) {
  const [savingLogs, setSavingLogs] = useState(false);
  const device = useConfigSection(config, setConfig, getDeviceConfig, deviceConfigFields, active === "System");
  const controller = useConfigSection(config, setConfig, getControllerConfig, controllerConfigFields, active === "Controller");
  const profiles = useConfigSection(config, setConfig, getProfilesConfig, profilesConfigFields, active === "Profiles");
  const experimental = useConfigSection(config, setConfig, getExperimentalConfig, experimentalConfigFields, active === "Settings" || active === "System");
  const about = useConfigSection(config, setConfig, getAboutConfig, aboutConfigFields, active === "About" || active === "Settings");
  const rgb = useBackendState(readRgb, 0, !config?.rgbSupported, host, active === "RGB");
  const fans = useBackendState(getFansState, 10000, !config, host, active === "Profiles");
  const logs = useBackendState(readLogs, 10000, !config || savingLogs, host, active === "System");
  const game = useGameSettingsState(config, host, active === "Compatibility" || active === "GlobalSettings");
  return { device, controller, profiles, experimental, about, rgb, fans, logs, game, savingLogs, setSavingLogs };
}
