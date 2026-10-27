import { call } from "@decky/api";
import { configChanges } from "./lib/configPatch";
import { waitForPendingSaves } from "./lib/configSaveQueue";
import type { ConfigPatch } from "./lib/configPatch";
import type { AboutConfig, CalibrationState, CompatAppliedState, ControllerConfig, CurvesState, DeviceConfig, ExperimentalConfig, FanCurve, FullConfig, InitialConfig, InstalledGame, PanelAttr, PanelCalibration, PanelRate, PanelStep, PowerProfile, ProfilesConfig, RgbConfig, SleepLogsStatus, Tweaks } from "./types";

function shareStartupRead<T>(read: () => Promise<T>): () => Promise<T> {
  let pending: Promise<T> | undefined;
  return () => pending ??= read().finally(() => { pending = undefined; });
}

export const getConfig = () => call<[], FullConfig>("get_config");
export const getInitialConfig = () => call<[], InitialConfig>("get_initial_config");
export const getProfilesConfig = () => call<[], ProfilesConfig>("get_profiles_config");
export const getControllerConfig = () => call<[], ControllerConfig>("get_controller_config");
export const getDeviceConfig = () => call<[], DeviceConfig>("get_device_config");
export const getExperimentalConfig = () => call<[], ExperimentalConfig>("get_experimental_config");
export const getAboutConfig = () => call<[], AboutConfig>("get_about_config");
export const getInstalledGames = () => call<[], InstalledGame[]>("get_installed_games");
export const getStartupConfig = shareStartupRead(async () => { await waitForPendingSaves(); return getInitialConfig(); });
export const getStartupInstalledGames = shareStartupRead(getInstalledGames);
export const getCompatMappedAppids = (tool: string) => call<[string], string[]>("get_compat_mapped_appids", tool);
export const savePowerProfile = (id: string, profile: PowerProfile) => call<[string, PowerProfile], FullConfig>("save_power_profile", id, profile);
export const saveTweaks = (data: Tweaks, baseline: Tweaks) =>
  call<[ConfigPatch[]], { tweaks: Tweaks }>("patch_tweaks", configChanges(baseline, data));
export const getCompatApplied = () => call<[], CompatAppliedState>("get_compat_applied");
export const saveCompatApplied = (appids: string[], protonDefault: string | null = null) =>
  call<[string[], string | null], CompatAppliedState>("save_compat_applied", [...appids], protonDefault);
export const setSwipeGesturesEnabled = (enabled: boolean) => call<[boolean], boolean>("set_swipe_gestures_enabled", enabled);
export const setSshEnabled = (enabled: boolean) => call<[boolean], boolean>("set_ssh_enabled", enabled);
export const setGyroEnabled = (enabled: boolean) => call<[boolean], boolean>("set_gyro_enabled", enabled);
export const setMtpEnabled = (enabled: boolean) => call<[boolean], boolean>("set_mtp_enabled", enabled);
export const getPanelCalibration = () => call<[], PanelCalibration>("get_panel_calibration");
export const getPanelRate = () => call<[], PanelRate>("get_panel_rate");
export const calibratePanel = () => call<[], { value: number; hz: number }>("calibrate_panel");
export const stepPanel = (attr: PanelAttr, direction: "faster" | "slower") =>
  call<[PanelAttr, string], PanelStep>("step_panel", attr, direction);
export const setPanel = (attr: PanelAttr, value: number) => call<[PanelAttr, number], boolean>("set_panel", attr, value);
export const savePanel = (attr: PanelAttr) => call<[PanelAttr], { saved: number | null }>("save_panel", attr);
export const setBottomScreenEnabled = (enabled: boolean) => call<[boolean], boolean>("set_bottom_screen_enabled", enabled);
export const setBottomScreenBrightness = (brightness: number) => call<[number], number>("set_bottom_screen_brightness", brightness);
export const getBottomScreenActive = () => call<[], boolean>("get_bottom_screen_active");
export const setCompanionLocked = (locked: boolean) => call<[boolean], boolean>("set_companion_locked", locked);
export const setDesktopMode = (value: string) => call<[string], string>("set_desktop_mode", value);
export const setSleepMode = (value: string) => call<[string], string>("set_sleep_mode", value);
export const getSleepLogsStatus = () => call<[], SleepLogsStatus>("get_sleep_logs_status");
export const setSleepLogsEnabled = (enabled: boolean) => call<[boolean], boolean>("set_sleep_logs_enabled", enabled);
export const reapplyPerf = () => call<[], { pids?: number }>("reapply_perf");
export const restartGameMode = () => call<[], boolean>("restart_game_mode");
export const setControllerType = (value: string) => call<[string], string>("set_controller_type", value);
export const getRgb = () => call<[], RgbConfig | null>("get_rgb");
export const setRgb = (
  enabled: boolean,
  linkBrightness: boolean,
  color: string,
  saturation: number,
  maxBrightness: number,
  brightness: number,
) =>
  call<[boolean, boolean, string, number, number, number], RgbConfig>(
    "set_rgb",
    enabled,
    linkBrightness,
    color,
    saturation,
    maxBrightness,
    brightness,
  );
export const getControllerState = () => call<[], CalibrationState>("get_controller_state");
export const startCalibrationRecording = () => call<[], CalibrationState>("start_calibration_recording");
export const saveCalibration = () => call<[], CalibrationState>("save_calibration");
export const resetCalibration = () => call<[], CalibrationState>("reset_calibration");
export const beginCalibrationSession = (token: string) => call<[string], boolean>("begin_calibration_session", token);
export const endCalibrationSession = (token: string) => call<[string], boolean>("end_calibration_session", token);
export const setChargingFanPwm = (pwm: number) => call<[number], number>("set_charging_fan_pwm", pwm);
export const getFansState = () => call<[], CurvesState>("get_fans_state");
export const saveFanCurves = (changes: Record<string, FanCurve>, deleted: string[] = []) =>
  call<[Record<string, FanCurve>, string[]], CurvesState>("save_fan_curves", changes, deleted);
export const getCurrentTemp = () => call<[], number | null>("get_current_temp");
