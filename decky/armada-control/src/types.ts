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

export interface InstalledGame {
  appid: string;
  name: string;
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
  backend?: string;
  saved?: boolean;
  params?: Record<string, number>;
}

export interface GameRef {
  appid: string;
  name: string;
}

export interface Config {
  power: PowerConfig;
  powerDefaults: PowerConfig;
  tweaks: Tweaks;
  installedGames: InstalledGame[];
  fexProfiles: Record<string, FexProfile>;
  cpuDeviceClass: string;
  hdrCapable: boolean;
  osVersion: string;
  sshEnabled: boolean;
  controllerType: string;
  controllerTypes: DropdownChoice[];
  calibration?: CalibrationState;
  game?: GameRef | null;
  selectedGame?: GameRef | null;
}

export interface HdrRuntimeState {
  available: boolean;
  display: string | null;
  supportsHdr: boolean;
  enabled: boolean;
  outputFeedback: boolean;
  sdrContentBrightnessNits: number | null;
  reason: string;
}

export type Capture = Record<string, { center: number; min: number; max: number; range: number }>;

export interface DropdownChoice {
  data: string;
  label: string;
}
