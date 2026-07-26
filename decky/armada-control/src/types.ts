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

export type AutoHdrMode = 1 | 2;
export type AutoHdrScope = "global" | "game";

export interface AutoHdrPreference {
  enabled: boolean;
}

export interface AutoHdrAppOverride {
  enabled?: boolean;
}

export interface AutoHdrPreferencesSnapshot {
  version: 2;
  global: AutoHdrPreference;
  override: AutoHdrAppOverride | null;
  scope: AutoHdrScope;
  appId: string | null;
  resolved: AutoHdrPreference;
  runtime: HdrRuntimeState;
}

export interface AutoHdrPreferencePatch {
  enabled?: boolean | null;
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
  displayIsExternal: boolean | null;
  supportsHdr: boolean;
  enabled: boolean;
  outputFeedback: boolean;
  sdrContentBrightnessNits: number | null;
  autoHdrSupported: boolean;
  autoHdrEnabled: boolean;
  autoHdrSdrNits: number | null;
  autoHdrTargetNits: number | null;
  autoHdrSupportedModes: number;
  autoHdrModeProtocolPresent: boolean;
  autoHdrModeProtocol: boolean;
  autoHdrMode: AutoHdrMode | null;
  autoHdrEffectiveMode: 0 | AutoHdrMode | null;
  reason: string;
}

export type Capture = Record<string, { center: number; min: number; max: number; range: number }>;

export interface DropdownChoice {
  data: string | number;
  label: string;
}
