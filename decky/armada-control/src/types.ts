export interface PowerProfile {
  label: string;
  cpu_governor: string;
  cpu_max: string;
  cpu_underclock: string;
  gpu_max: string;
  gpu_max_mhz: number | null;
  gpu_min: string;
  gpu_min_mhz: number | null;
  fan_curve: string;
  [key: `cpu_max_policy${number}`]: number | null;
}

export interface CpuPolicy {
  id: number;
  cpus: string;
  khz: number[];
  mhz: number[];
}

export interface FreqLimits {
  gpuMhz: number[];
  gpuStockMaxMhz: number;
  cpuPolicies: CpuPolicy[];
  cpuTopology?: CpuTopology;
}

export interface CpuTopology {
  big: string;
  prime: string;
  little: string;
}

export interface SleepLogsStatus {
  enabled: boolean;
  directory: string | null;
}

export interface FanCurve extends FanSettings {
  label: string;
  curve: string;
}

export interface PowerConfig {
  general: { default_profile: string };
  profiles: Record<string, PowerProfile>;
  fan_curves: Record<string, FanCurve>;
  fan: Record<string, string>;
  underclocks: Record<string, Record<string, Record<string, string>>>;
}

export interface GameTweak {
  enabled?: boolean;
  name?: string;
  fexProfile?: string;
  fexConfig?: Record<string, string>;
  steamCompatTool?: string;
  steamResolution?: string;
  turnipDriver?: string;
  thunks?: Record<string, boolean>;
  [key: string]: any;
}

export interface Tweaks {
  global: Record<string, any>;
  games: Record<string, GameTweak>;
}

export interface CompatAppliedState {
  appids: string[];
  protonDefault: string;
}

export interface InstalledGame {
  appid: string;
  name: string;
  nonSteam?: boolean;
}

export interface FexProfile {
  label: string;
  config?: Record<string, string>;
}

export interface TurnipDriver {
  id: string;
  label: string;
  version: string;
}

// A text in env-presets.json is either one string or one string per locale, so a
// label that needs no translation does not cost four lines.
export type LocalizedText = string | Record<string, string>;

export interface EnvPresetOption {
  data: string;
  label: LocalizedText;
}

export interface EnvPreset {
  name: string;
  description: LocalizedText;
  // Closed list of values; absent means the value is free text.
  options?: EnvPresetOption[];
  // A hint only. The docs show these inside examples and never state a default.
  example?: string;
}

export interface AbsControl {
  value: number;
  min: number;
  max: number;
  flat: number;
  fuzz: number;
  resolution: number;
}

export interface CalibrationState {
  supported: boolean;
  reason: string;
  controls: Record<string, AbsControl>;
  event: any;
  canApply?: boolean;
  backend?: string;
  saved?: boolean;
  calibratedAt?: string | null;
  hasCalibration?: boolean;
  params?: Record<string, number>;
  progress?: CalibrationProgress;
}

export type StickSide = "left" | "right" | "up" | "down";

export type StickProgress = Record<StickSide, number>;

export interface CalibrationProgress {
  left_stick: StickProgress;
  right_stick: StickProgress;
  left_trigger: number;
  right_trigger: number;
  ready: boolean;
}

export interface RgbConfig {
  version: number;
  enabled: boolean;
  linkBrightness: boolean;
  maxBrightness: number;
  brightness: number;
  color: string;
  saturation: number;
}

export interface GameRef {
  appid: string;
  name: string;
  nonSteam?: boolean;
}

export interface PerfInfo {
  governors: string[];
  schedulers: string[];
  corePresets: DropdownChoice[];
  cpuCount: number;
}

export interface InitialConfig {
  tweaks: Tweaks;
  tweaksDefaults?: Tweaks;
  installedGames: InstalledGame[];
  fexProfiles: Record<string, FexProfile>;
  turnipDrivers?: TurnipDriver[];
  envPresets: EnvPreset[];
  perf?: PerfInfo;
  cpuDeviceClass: string;
  rgbSupported: boolean;
  protonDefaults: string[];
  game?: GameRef | null;
  selectedGame?: GameRef | null;
}

export interface ProfilesConfig {
  power: PowerConfig;
  powerDefaults: PowerConfig;
  freqLimits: FreqLimits;
}

export interface AboutConfig {
  osVersion: string;
  ablVersion: string;
  sshEnabled: boolean;
}

export interface DeviceConfig {
  panelCalibrationSupported: boolean;
  chargingFanSupported: boolean;
  chargingFanPwm: number;
}

export interface ExperimentalConfig {
  bottomScreenSupported: boolean;
  bottomScreenEnabled: boolean;
  bottomScreenBrightnessSupported: boolean;
  bottomScreenActive: boolean;
  bottomScreenBrightness: number;
  swipeGesturesEnabled: boolean;
  mtpEnabled: boolean;
  desktopMode: string;
  desktopModes: DropdownChoice[];
  sleepMode: string;
  sleepModes: DropdownChoice[];
}

export interface ControllerConfig {
  gyro: { supported: boolean; enabled: boolean };
  controllerType: string;
  controllerTypes: DropdownChoice[];
  calibratedAt: string | null;
  hasCalibration: boolean;
}

export type FullConfig = InitialConfig & ProfilesConfig & ControllerConfig & DeviceConfig & ExperimentalConfig & AboutConfig;
export type Config = InitialConfig & Partial<ProfilesConfig & ControllerConfig & DeviceConfig & ExperimentalConfig & AboutConfig>;

export interface DropdownChoice {
  data: string;
  label: string;
}

export interface ProfileSummary {
  label: string;
  fan_curve: string;
}

export interface FanSettings {
  ramp_up: number;
  ramp_down: number;
  smoothing: number;
  min_pwm: number;
}

export interface CurvesState {
  fanCurves: Record<string, FanCurve>;
  factoryFanCurves: Record<string, FanCurve>;
  profiles: Record<string, ProfileSummary>;
  // Falls back to the configured default, then any profile, if the daemon state can't be read.
  activeProfile: string;
}

export type PanelAttr = "frame_len_120" | "frame_len_60";
export type PanelValues = Record<PanelAttr, number | null>;

export interface PanelCalibration {
  supported: boolean;
  saved?: PanelValues;
  live?: PanelValues;
  defaults?: PanelValues;
}

export interface PanelRate {
  hz: number | null;
  attr: PanelAttr | null;
}

export interface PanelStep {
  value: number;
  hz: number | null;
  limit: "range" | null;
}
