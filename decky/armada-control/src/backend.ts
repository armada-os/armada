import { call } from "@decky/api";
import type {
  CalibrationState,
  Capture,
  Config,
  HdrRuntimeState,
  InstalledGame,
  PowerConfig,
  Tweaks,
} from "./types";

export const getConfig = () => call<[], Config>("get_config");
export const getHdrRuntimeState = () => call<[], HdrRuntimeState>("get_hdr_runtime_state");
export const getInstalledGames = () => call<[], InstalledGame[]>("get_installed_games");
export const savePowerConfig = (data: PowerConfig) => call<[PowerConfig], Config>("save_power_config", data);
export const saveTweaks = (data: Tweaks) => call<[Tweaks], Config>("save_tweaks", data);
export const getCompatApplied = () => call<[], string[]>("get_compat_applied");
let compatAppliedSaveChain = Promise.resolve<unknown>(undefined);
export const saveCompatApplied = (appids: string[]) => {
  const snapshot = [...appids];
  const request = compatAppliedSaveChain
    .catch(() => {})
    .then(() => call<[string[]], string[]>("save_compat_applied", snapshot));
  compatAppliedSaveChain = request;
  return request;
};
export const setSshEnabled = (enabled: boolean) => call<[boolean], boolean>("set_ssh_enabled", enabled);
export const setControllerType = (value: string) => call<[string], string>("set_controller_type", value);
export const getControllerState = () => call<[], CalibrationState>("get_controller_state");
export const saveCalibration = (capture: Capture) => call<[Capture], CalibrationState>("save_calibration", capture);
export const resetCalibration = () => call<[], CalibrationState>("reset_calibration");
export const beginCalibrationSession = (token: string) => call<[string], boolean>("begin_calibration_session", token);
export const endCalibrationSession = (token: string) => call<[string], boolean>("end_calibration_session", token);
