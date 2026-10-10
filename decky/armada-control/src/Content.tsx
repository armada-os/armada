import { Field, PanelSection, Tabs } from "@decky/ui";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { getConfig, getInstalledGames, savePowerConfig, saveTweaks } from "./backend";
import { RgbLighting } from "./components/RgbLighting";
import { useDebouncedSave } from "./hooks/useDebouncedSave";
import { useLocale } from "./hooks/useLocale";
import { t } from "./i18n";
import { tabIcons } from "./icons";
import { currentGame } from "./lib/games";
import { styles } from "./styles";
import { Compatibility } from "./tabs/Compatibility";
import { Fans } from "./tabs/Fans";
import { Power } from "./tabs/Power";
import { Settings } from "./tabs/Settings";
import { Trackpads } from "./tabs/Trackpads";
import type { Config } from "./types";

export function Content() {
  useLocale();
  const [tab, setTab] = useState("Compatibility");
  const [config, setConfig] = useState<Config | null>(null);
  const [message, setMessage] = useState("Loading");
  const savedPowerSnapshot = useRef("");
  const savedTweaksSnapshot = useRef("");
  const installedGamesRequested = useRef(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const load = useCallback(async () => {
    try {
      const next = await getConfig();
      next.game = currentGame();
      next.selectedGame = next.game || null;
      savedPowerSnapshot.current = JSON.stringify(next.power);
      savedTweaksSnapshot.current = JSON.stringify(next.tweaks);
      setConfig((current) => ({ ...next, installedGames: current?.installedGames || next.installedGames }));
    } catch (error) {
      setMessage(String(error));
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (!config || installedGamesRequested.current) return;
    installedGamesRequested.current = true;
    let cancelled = false;
    getInstalledGames()
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
  useDebouncedSave({ config, field: "power", snapshot: savedPowerSnapshot, save: savePowerConfig, setConfig, onError: load });
  useDebouncedSave({ config, field: "tweaks", snapshot: savedTweaksSnapshot, save: saveTweaks, setConfig, onError: load });
  useLayoutEffect(() => {
    const menu = menuRef.current;
    const view = menu?.ownerDocument.defaultView;
    if (!menu || !view) return;
    const measure = () => {
      const rect = menu.getBoundingClientRect();
      if (!rect.width || !menu.offsetWidth) return;
      const scale = rect.width / menu.offsetWidth;
      // The QAM reserves 40 logical pixels for the controller footer. Measure
      // from this plugin's actual top so tabs cannot extend underneath it.
      const height = Math.max(0, Math.floor((view.innerHeight - rect.top) / scale - 40));
      menu.style.setProperty("--armada-menu-height", `${height}px`);
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (menu.parentElement) observer.observe(menu.parentElement);
    view.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      view.removeEventListener("resize", measure);
    };
  }, [!!config]);
  if (!config) return <PanelSection title="Armada Control"><Field label={message === "Loading" ? t("common.loading") : message} /></PanelSection>;
  const tabContent = (content: ReactNode) => (
    <div className="armada-control-tab-content">{content}</div>
  );
  return (
    <>
      <div className="armada-control-tabs" ref={menuRef}>
        <style>{styles}</style>
        <Tabs
          activeTab={tab}
          onShowTab={setTab}
          tabs={[
            { id: "Compatibility", title: tabIcons.Compatibility, content: tabContent(<Compatibility config={config} setConfig={setConfig} />) },
            { id: "Power", title: tabIcons.Power, content: tabContent(<Power config={config} setConfig={setConfig} />) },
            { id: "Fans", title: tabIcons.Fans, content: tabContent(<Fans setConfig={setConfig} />) },
            ...(config.rgbSupported ? [
              { id: "RGB", title: tabIcons.RGB, content: tabContent(<RgbLighting />) },
            ] : []),
            { id: "Trackpads", title: tabIcons.Trackpads, content: tabContent(<Trackpads config={config} setConfig={setConfig} />) },
            { id: "Advanced", title: tabIcons.Advanced, content: tabContent(<Settings config={config} setConfig={setConfig} />) },
          ]}
        />
      </div>
    </>
  );
}
