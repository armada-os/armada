export interface LaunchSpec {
  name: string;
  exe: string;
  startDir: string;
  launchOptions: string;
}

export interface CatalogApp {
  id: string;
  name: string;
  summary: string;
  category: string;
  icon: string;
  note: string;
  installType: "flatpak" | "appimage" | "deckyplugin" | "system" | "";
  desktopOnly: boolean;
  launch: LaunchSpec | null;
}

export interface Catalog {
  apps: CatalogApp[];
  home?: string;
}

export interface Job {
  appId: string;
  action: "install" | "uninstall" | "replace";
  phase: string;
  percent: number | null;
  error: string;
}

export interface Conflict {
  type: "flatpak" | "appimage";
  ref?: string;
  filename?: string;
}

export interface InstalledInfo {
  installed: boolean;
  version?: string;
  conflicts?: Conflict[];
}

export interface Status {
  jobs: Job[];
  installed: Record<string, InstalledInfo>;
  shortcuts: Record<string, number>;
  pending: string[];
}
