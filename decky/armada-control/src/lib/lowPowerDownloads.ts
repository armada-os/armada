const ENABLED_KEY = "system_enable_low_power_downloads";
const BATTERY_KEY = "system_allow_battery_low_power_downloads";
const AC_DISCONNECTED = 1;
const MIN_BATTERY_LEVEL = 0.2;

function clientSetting(key: string): [any, ((value: any) => unknown) | undefined] {
  const setting = window.settingsStore?.GetClientSetting?.(key);
  return [setting?.[0], setting?.[1]];
}

export function getLowPowerDownloadSettings() {
  return { enabled: !!clientSetting(ENABLED_KEY)[0], onBattery: !!clientSetting(BATTERY_KEY)[0] };
}

async function setClientSetting(key: string, value: boolean): Promise<void> {
  const setter = clientSetting(key)[1];
  if (!setter) throw new Error("Steam settings are unavailable");
  await Promise.resolve(setter(value));
}

export const setLowPowerDownloadsEnabled = (value: boolean) => setClientSetting(ENABLED_KEY, value);
export const setLowPowerDownloadsOnBattery = (value: boolean) => setClientSetting(BATTERY_KEY, value);

function downloading(): boolean {
  const overview = window.downloadsStore?.m_DownloadOverview;
  const current = overview?.values ? [...overview.values()][0] : undefined;
  return current?.update_state === "Downloading" && !current.paused;
}

// Same conditions as the Deck: plugged in, or allowed on battery above 20%.
function shouldOffer(): boolean {
  const settings = getLowPowerDownloadSettings();
  if (!settings.enabled || !downloading()) return false;
  const battery = window.SystemPowerStore?.batteryState;
  if (!battery?.bHasBattery || battery.eACState !== AC_DISCONNECTED) return true;
  return settings.onBattery && battery.flLevel > MIN_BATTERY_LEVEL;
}

// Steam only offers its low-power download mode on Valve and Lenovo hardware, so
// put its confirm modal in front of sleep ourselves. The modal's own Sleep button
// calls InitiateSleep while it is open, which passes through.
export function registerLowPowerDownloadEntry(): () => void {
  let restore = () => {};
  let stopped = false;
  const install = () => {
    const store = window.SuspendResumeStore;
    if (stopped || !store?.InitiateSleep || !store.SetShowConfirmSleepModal) return false;
    const original = store.InitiateSleep;
    store.InitiateSleep = function (this: any, ...args: unknown[]) {
      if (!this.ShowConfirmSleepModal && shouldOffer()) {
        this.SetShowConfirmSleepModal(true);
        return;
      }
      return original.apply(this, args);
    };
    restore = () => { store.InitiateSleep = original; };
    return true;
  };
  const timer = install() ? undefined : window.setInterval(() => {
    if (install()) window.clearInterval(timer);
  }, 1000);
  return () => {
    stopped = true;
    window.clearInterval(timer);
    restore();
  };
}
