import type { Config } from "../types";

export const initialConfigFields = ["tweaks", "tweaksDefaults", "fexProfiles", "turnipDrivers", "envPresets", "perf", "cpuDeviceClass", "rgbSupported", "protonDefaults"] as const;
export const profilesConfigFields = ["power", "powerDefaults", "freqLimits"] as const;
export const controllerConfigFields = ["gyro", "controllerType", "controllerTypes", "calibratedAt", "hasCalibration"] as const;
export const deviceConfigFields = ["panelCalibrationSupported", "chargingFanSupported", "chargingFanPwm"] as const;
export const experimentalConfigFields = [
  "bottomScreenSupported", "bottomScreenEnabled", "bottomScreenBrightnessSupported", "bottomScreenActive", "bottomScreenBrightness",
  "swipeGesturesEnabled", "mtpEnabled", "desktopMode", "desktopModes", "sleepMode", "sleepModes",
] as const;
export const aboutConfigFields = ["osVersion", "ablVersion", "sshEnabled"] as const;

function hasFields<K extends keyof Config>(fields: readonly K[]) {
  return (config: Config): config is Config & Required<Pick<Config, K>> => fields.every((field) => config[field] !== undefined);
}

export const hasProfilesConfig = hasFields(profilesConfigFields);
export const hasControllerConfig = hasFields(controllerConfigFields);
export const hasDeviceConfig = hasFields(deviceConfigFields);
export const hasExperimentalConfig = hasFields(experimentalConfigFields);
export const hasAboutConfig = hasFields(aboutConfigFields);

export function mergeConfigSection(current: Config, baseline: Config, loaded: Partial<Config>, fields: readonly (keyof Config)[], unchanged: (field: keyof Config) => boolean): Config {
  const patch: Partial<Config> = {};
  for (const field of fields) {
    if (field in loaded && unchanged(field) && JSON.stringify(current[field]) === JSON.stringify(baseline[field])) {
      Object.assign(patch, { [field]: loaded[field] });
    }
  }
  return { ...current, ...patch };
}
