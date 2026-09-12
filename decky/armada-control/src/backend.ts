import { call } from "@decky/api";
import type { CalibrationState, Capture, CompatAppliedState, Config, CurvesState, FanCurve, FanSettings, InstalledGame, PowerConfig, RgbConfig, Tweaks } from "./types";

export const getConfig = () => call<[], Config>("get_config");
export const getInstalledGames = () => call<[], InstalledGame[]>("get_installed_games");
export const getCompatMappedAppids = (tool: string) => call<[string], string[]>("get_compat_mapped_appids", tool);
export const savePowerConfig = (data: PowerConfig) => call<[PowerConfig], Config>("save_power_config", data);
export const saveTweaks = (data: Tweaks) => call<[Tweaks], Config>("save_tweaks", data);
export const getCompatApplied = () => call<[], CompatAppliedState>("get_compat_applied");
let compatAppliedSaveChain = Promise.resolve<unknown>(undefined);
export const saveCompatApplied = (appids: string[], protonDefault: string | null = null) => {
  const snapshot = [...appids];
  const request = compatAppliedSaveChain
    .catch(() => {})
    .then(() => call<[string[], string | null], CompatAppliedState>("save_compat_applied", snapshot, protonDefault));
  compatAppliedSaveChain = request;
  return request;
};
export const setSshEnabled = (enabled: boolean) => call<[boolean], boolean>("set_ssh_enabled", enabled);
export const setMtpEnabled = (enabled: boolean) => call<[boolean], boolean>("set_mtp_enabled", enabled);
export const setAblAutoEnabled = (enabled: boolean) => call<[boolean], boolean>("set_abl_auto_enabled", enabled);
export const setBottomScreenEnabled = (enabled: boolean) => call<[boolean], boolean>("set_bottom_screen_enabled", enabled);
export const setBottomScreenBrightness = (brightness: number) => call<[number], number>("set_bottom_screen_brightness", brightness);
export const setDesktopMode = (value: string) => call<[string], string>("set_desktop_mode", value);
export const setSleepMode = (value: string) => call<[string], string>("set_sleep_mode", value);
export const reapplyPerf = () => call<[], { pids?: number }>("reapply_perf");
export const restartGameMode = () => call<[], boolean>("restart_game_mode");
export const setControllerType = (value: string) => call<[string], string>("set_controller_type", value);
export const getRgb = () => call<[], RgbConfig | null>("get_rgb");
export const setRgb = (enabled: boolean, color: string, brightness: number) =>
  call<[boolean, string, number], RgbConfig>("set_rgb", enabled, color, brightness);
export const getControllerState = () => call<[], CalibrationState>("get_controller_state");
export const saveCalibration = (capture: Capture) => call<[Capture], CalibrationState>("save_calibration", capture);
export const resetCalibration = () => call<[], CalibrationState>("reset_calibration");
export const beginCalibrationSession = (token: string) => call<[string], boolean>("begin_calibration_session", token);
export const endCalibrationSession = (token: string) => call<[string], boolean>("end_calibration_session", token);
export const getFansState = () => call<[], CurvesState>("get_fans_state");
export const saveFanCurves = (fanCurves: Record<string, FanCurve>, fanSettings: FanSettings) =>
  call<[Record<string, FanCurve>, FanSettings], CurvesState>("save_fan_curves", fanCurves, fanSettings);
export const getCurrentTemp = () => call<[], number | null>("get_current_temp");
