export interface PowerProfile {
  label: string;
  cpu_governor: string;
  cpu_max: string;
  cpu_underclock: string;
  gpu_max: string;
  gpu_min: string;
  fan_curve: string;
}

export interface FanCurve {
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
  canCalibrateTriggers?: boolean;
  backend?: string;
  saved?: boolean;
  params?: Record<string, number>;
}

export interface McuCalibrationCapability {
  available: boolean;
  abiVersion: number;
  writeEnabled: boolean;
  phases: Array<"center" | "range">;
  writeDelaySeconds?: number;
}

export interface McuCalibrationSample {
  timestampNs: number;
  generation: number;
  sequence: number;
  length: number;
  dropped: number;
  logicalX: number;
  logicalY: number;
  rawX?: number;
  rawY?: number;
  rawZ?: number;
}

export interface McuCalibrationPreview {
  active: boolean;
  stick: "left" | "right";
  phase: "center" | "range";
  sampleCount: number;
  rawSampleCount: number;
  generationGaps: number;
  sequenceGaps: number;
  captureGaps: number;
  droppedBaseline: number | null;
  dropped: number | null;
  error: string;
  latest: McuCalibrationSample | null;
  complete: boolean;
  progress: {
    coveredDirections?: string[];
    directionCount?: number;
    directionGoal?: number;
    pendingDirection?: string | null;
    stableSamples?: number;
    stableGoal?: number;
    turns?: number;
    turnGoal?: number;
    coveredHeadings?: number;
    headingGoal?: number;
    samplesPerHeading?: number[];
    coveredSectors?: number;
    sectorGoal?: number;
  };
  result: {
    centerWords?: number[];
    centerHex?: string;
    returnSpread?: number[];
    derivedWords?: number[];
    tableWords?: number[];
    tableHex?: string;
    traceSampleCount?: number;
    traceSha256?: string;
    capturePath?: string;
    captureSha256?: string;
  } | null;
}

export interface RgbConfig {
  version: number;
  enabled: boolean;
  brightness: number;
  color: string;
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

export interface Config {
  power: PowerConfig;
  powerDefaults: PowerConfig;
  tweaks: Tweaks;
  installedGames: InstalledGame[];
  fexProfiles: Record<string, FexProfile>;
  perf?: PerfInfo;
  cpuDeviceClass: string;
  rgbSupported: boolean;
  protonDefaults: string[];
  osVersion: string;
  ablVersion: string;
  ablAutoEnabled: boolean;
  bottomScreenSupported: boolean;
  bottomScreenEnabled: boolean;
  bottomScreenBrightnessSupported: boolean;
  bottomScreenBrightness: number;
  sshEnabled: boolean;
  mtpEnabled: boolean;
  desktopMode: string;
  desktopModes: DropdownChoice[];
  sleepMode: string;
  sleepModes: DropdownChoice[];
  controllerType: string;
  controllerTypes: DropdownChoice[];
  calibration?: CalibrationState;
  game?: GameRef | null;
  selectedGame?: GameRef | null;
}

export type Capture = Record<string, { center: number; min: number; max: number; range: number }>;

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
  fanSettings: FanSettings;
  factoryFanSettings: FanSettings;
  profiles: Record<string, ProfileSummary>;
  // Falls back to the configured default, then any profile, if the daemon state can't be read.
  activeProfile: string;
  // Live marker instead polls get_current_temp (see hooks/useCurrentTemp).
  currentTemp: number | null;
}
