export {};

declare global {
  interface Window {
    SteamClient?: any;
    settingsStore?: any;
    securitystore?: any;
    SuspendResumeStore?: any;
    downloadsStore?: any;
    SystemPowerStore?: any;
    appDetailsStore?: any;
    Router?: any;
  }
}
