export {};

declare global {
  interface Window {
    SteamClient?: any;
    settingsStore?: any;
    SystemPerfStore?: any;
    appDetailsStore?: any;
    Router?: any;
  }
}
