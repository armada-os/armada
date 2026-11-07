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
import { DeviceSettings } from "./tabs/DeviceSettings";
import { Experimental } from "./tabs/Experimental";
import { About } from "./tabs/About";
import { hasAboutConfig, hasControllerConfig, hasDeviceConfig, hasExperimentalConfig, hasProfilesConfig, initialConfigFields, mergeConfigSection } from "./lib/configSections";
import { configFieldRevision } from "./lib/configMutation";
import type { Config } from "./types";

export function Content() {
  useLocale();
  const [tab, setTab] = useState("Compatibility");
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
    Compatibility: <Compatibility config={config} setConfig={setConfig} saveTweaksNow={saveTweaksNow} state={data.game} />,
    RGB: <ConfigSection config={config} state={data.device} loaded={hasDeviceConfig}>
      {(current) => <DeviceSettings config={current} setConfig={setConfig} rgbState={data.rgb} />}
    </ConfigSection>,
    Controller: <ConfigSection config={config} state={data.controller} loaded={hasControllerConfig}>
      {(current) => <Controller config={current} setConfig={setConfig} />}
    </ConfigSection>,
    Profiles: <ConfigSection config={config} state={data.profiles} loaded={hasProfilesConfig}>
      {(current) => <Profiles config={current} setConfig={setConfig} state={data.fans} />}
    </ConfigSection>,
    Experimental: <ConfigSection config={config} state={data.experimental} loaded={hasExperimentalConfig}>
      {(current) => <Experimental config={current} setConfig={setConfig} />}
    </ConfigSection>,
    About: <ConfigSection config={config} state={data.about} loaded={hasAboutConfig}>
      {(current) => <About config={current} setConfig={setConfig} state={data.logs} saving={data.savingLogs} setSaving={data.setSavingLogs} />}
    </ConfigSection>,
  } : {};
  return <>
    <ArmadaStyles />
    <TabNavigation
      rootRef={host}
      activeTab={tab}
      onShowTab={setTab}
      tabs={[
        { id: "Compatibility", title: t("navigation.games"), icon: tabIcons.Compatibility },
        { id: "RGB", title: t("navigation.rgb"), icon: tabIcons.DeviceSettings },
        { id: "Controller", title: t("navigation.controller"), icon: tabIcons.Controller },
        { id: "Profiles", title: t("navigation.profiles"), icon: tabIcons.Power },
        { id: "Experimental", title: t("navigation.experimental"), icon: tabIcons.Experimental },
        { id: "About", title: t("navigation.about"), icon: tabIcons.About },
      ].map((item) => ({ ...item, content: config ? panels[item.id] : startup }))}
    />
  </>;
}
