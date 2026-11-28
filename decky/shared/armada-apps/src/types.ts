export interface LaunchSpec {
  name: string;
  exe: string;
  startDir: string;
  launchOptions: string;
  compatTool?: string;
  controllerTemplate?: string;
}

export interface CatalogApp {
  id: string;
  name: string;
  summary: string;
  category: string;
  icon: string;
  note: string;
  installType: "flatpak" | "appimage" | "deckyplugin" | "proton" | "turnip" | "system" | "android" | "";
  imported: boolean;
  canInstall?: boolean;
  retired?: boolean;
  desktopOnly: boolean;
  removable: boolean;
  // The app has config templates it can restore.
  hasConfig?: boolean;
  launch: LaunchSpec | null;
}

export interface CatalogCategory {
  id: string;
  // A plain string, or text per UI language with "en" always present. Empty
  // for the Store's own "other" section.
  name: string | Record<string, string>;
  // The section icon as an SVG data: URI, or empty when there is none.
  icon: string;
}

export interface Catalog {
  apps: CatalogApp[];
  categories: CatalogCategory[];
  // Shown above the sections, for a plugin that can't act on this image.
  notice?: string;
  home?: string;
  revision?: string;
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
  // When the installed release asset was uploaded.
  date?: string;
  conflicts?: Conflict[];
}

export interface Status {
  catalogRevision?: string;
  jobs: Job[];
  installed: Record<string, InstalledInfo>;
  shortcuts: Record<string, number>;
  pending: string[];
  // Updated plugins, by Decky name, still running their old code.
  reload?: string[];
}

export interface AndroidPage {
  kind: "bundle" | "cluster";
  url: string;
}
