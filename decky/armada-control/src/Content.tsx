import { toaster } from "@decky/api";
import { PanelSection } from "@decky/ui";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { getConfig, getInitialConfig, getStartupConfig, getStartupInstalledGames, saveTweaks } from "./backend";
import { TabNavigation } from "./components/TabNavigation";
import { useDebouncedSave } from "./hooks/useDebouncedSave";
import { useTabData } from "./hooks/useTabData";
import { useLocale } from "./hooks/useLocale";
import { t } from "./i18n";
import { tabIcons } from "./icons";
import { currentGame } from "./lib/games";
import { ArmadaStyles } from "./components/ArmadaStyles";
import { LoadingState } from "./components/LoadingState";
import { ConfigSection } from "./components/ConfigSection";
import { ButtonRow, SupportingText } from "./components/widgets";
import { Compatibility } from "./tabs/Compatibility";
import { Profiles } from "./tabs/Profiles";
import { Controller } from "./tabs/Controller";
import { System } from "./tabs/System";
import { RGB } from "./tabs/RGB";
import { Settings } from "./tabs/Settings";
import { About } from "./tabs/About";
import { hasAboutConfig, hasControllerConfig, hasDeviceConfig, hasExperimentalConfig, hasProfilesConfig, initialConfigFields, mergeConfigSection } from "./lib/configSections";
import { configFieldRevision } from "./lib/configMutation";
import type { AboutConfig, Config, DeviceConfig, ExperimentalConfig } from "./types";

const hasSettingsConfig = (config: Config): config is Config & ExperimentalConfig & AboutConfig => hasExperimentalConfig(config) && hasAboutConfig(config);
const hasSystemConfig = (config: Config): config is Config & DeviceConfig & ExperimentalConfig => hasDeviceConfig(config) && hasExperimentalConfig(config);

export function Content() {
  useLocale();
  const [tab, setTab] = useState(() => currentGame() ? "Compatibility" : "GlobalSettings");
  const [gameBack, setGameBack] = useState<(() => void) | null>(null);
  const updateGameBack = useCallback((handler: (() => void) | null) => setGameBack(() => handler), []);
  const [config, setConfig] = useState<Config | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const savedTweaksSnapshot = useRef("");
  const latestConfig = useRef(config);
  latestConfig.current = config;
  const mounted = useRef(true);
  const loadRequest = useRef(0);
  const load = useCallback(async (read: () => Promise<Config> = getConfig) => {
    if (!mounted.current) return;
    const request = ++loadRequest.current;
    setLoadError(null);
    const baseline = latestConfig.current;
    const revisions = new Map<keyof Config, number>(initialConfigFields.map((field) => [field, configFieldRevision(setConfig, field)]));
    try {
      const next = { ...await read(), game: currentGame() };
      if (!mounted.current || request !== loadRequest.current) return;
      savedTweaksSnapshot.current = JSON.stringify(next.tweaks);
      const reconcile = (current: Config | null): Config => current && baseline ? {
        ...mergeConfigSection(current, baseline, next, initialConfigFields,
          (field) => configFieldRevision(setConfig, field) === revisions.get(field)),
        game: next.game,
      } : { ...next, selectedGame: current?.selectedGame, installedGames: current?.installedGames || next.installedGames };
      const recovered = reconcile(latestConfig.current);
      setConfig(reconcile);
      return { config: recovered, saved: next };
    } catch (error) {
      if (mounted.current && request === loadRequest.current) setLoadError(String(error));
    }
  }, []);
  useEffect(() => {
    mounted.current = true;
    void load(getStartupConfig);
    return () => {
      mounted.current = false;
      loadRequest.current++;
    };
  }, [load]);
  useEffect(() => {
    if (!config) return;
    let cancelled = false;
    getStartupInstalledGames()
      .then((installedGames) => {
        if (cancelled) return;
        setConfig((current) => (current ? { ...current, installedGames } : current));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [!!config]);
  useEffect(() => {
    if (!config) return;
    let cancelled = false;
    const refreshRuntime = async () => {
      try {
        const runtimeGame = currentGame();
        if (cancelled) return;
        setConfig((current) => {
          if (!current) return current;
          const currentApp = current.game?.appid || "";
          const nextApp = runtimeGame?.appid || "";
          const currentName = current.game?.name || "";
          const nextName = runtimeGame?.name || "";
          if (currentApp === nextApp && currentName === nextName) return current;
          return { ...current, game: runtimeGame };
        });
      } catch (error) {
      }
    };
    const timer = window.setInterval(refreshRuntime, 2000);
    refreshRuntime();
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [!!config]);
  const host = useRef<HTMLDivElement>(null);
  const data = useTabData(config, setConfig, tab, host);
  const saveTweaksNow = useDebouncedSave({ config, snapshot: savedTweaksSnapshot, save: saveTweaks, setConfig, onError: (error) => {
    toaster.toast({ title: t("navigation.games"), body: t("gameSettings.updateError", { error: String(error) }) });
    return load();
  } });
  const startup = loadError !== null ? <PanelSection>
    <div role="alert">
      <SupportingText className="armada-note-error">{t("common.loadError")}: {loadError}</SupportingText>
    </div>
    <ButtonRow layout="below" onClick={() => { void load(getInitialConfig); }}>{t("common.retry")}</ButtonRow>
  </PanelSection> : <LoadingState label={t("common.loadingSettings")} />;
  const panels: Record<string, ReactNode> = config ? {
    Compatibility: <Compatibility mode="game" onBackChange={updateGameBack} config={config} setConfig={setConfig} saveTweaksNow={saveTweaksNow} state={data.game} />,
    GlobalSettings: <Compatibility mode="global" config={config} setConfig={setConfig} saveTweaksNow={saveTweaksNow} state={data.game} />,
    RGB: <RGB state={data.rgb} />,
    Controller: <ConfigSection config={config} state={data.controller} loaded={hasControllerConfig}>
      {(current) => <Controller config={current} setConfig={setConfig} />}
    </ConfigSection>,
    Profiles: <ConfigSection config={config} state={data.profiles} loaded={hasProfilesConfig}>
      {(current) => <Profiles config={current} setConfig={setConfig} state={data.fans} />}
    </ConfigSection>,
    Settings: <ConfigSection config={config} state={data.experimental} loaded={hasExperimentalConfig}>
      {current => <ConfigSection config={current} state={data.about} loaded={hasSettingsConfig}>
        {loaded => <Settings config={loaded} setConfig={setConfig} />}
      </ConfigSection>}
    </ConfigSection>,
    System: <ConfigSection config={config} state={data.device} loaded={hasDeviceConfig}>
      {current => <ConfigSection config={current} state={data.experimental} loaded={hasSystemConfig}>
        {loaded => <System config={loaded} setConfig={setConfig} logsState={data.logs} savingLogs={data.savingLogs} setSavingLogs={data.setSavingLogs} />}
      </ConfigSection>}
    </ConfigSection>,
    About: <ConfigSection config={config} state={data.about} loaded={hasAboutConfig}>
      {(current) => <About config={current} />}
    </ConfigSection>,
  } : {};
  return <>
    <ArmadaStyles />
    <TabNavigation
      rootRef={host}
      activeTab={tab}
      onShowTab={setTab}
      onBack={tab === "Compatibility" ? gameBack : null}
      tabs={[
        { id: "GlobalSettings", title: t("gameLibrary.globalTab"), icon: tabIcons.GlobalSettings },
        { id: "Compatibility", title: t("gameLibrary.gameTab"), icon: tabIcons.Compatibility },
        { id: "Profiles", title: t("navigation.profiles"), icon: tabIcons.Power },
        { id: "Controller", title: t("navigation.controller"), icon: tabIcons.Controller },
        ...(config?.rgbSupported ? [{ id: "RGB", title: t("navigation.rgb"), icon: tabIcons.RGB }] : []),
        { id: "Settings", title: t("navigation.settings"), icon: tabIcons.DeviceSettings },
        { id: "System", title: t("navigation.system"), icon: tabIcons.System },
        { id: "About", title: t("navigation.about"), icon: tabIcons.About },
      ].map((item) => ({ ...item, content: config ? panels[item.id] : startup }))}
    />
  </>;
}
