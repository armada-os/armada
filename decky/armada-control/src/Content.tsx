import { Field, PanelSection, Tabs } from "@decky/ui";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { getConfig, getInstalledGames, savePowerConfig, saveRGBConfig, saveTweaks } from "./backend";
import { useDebouncedSave } from "./hooks/useDebouncedSave";
import { tabIcons } from "./icons";
import { currentGame } from "./lib/games";
import { styles } from "./styles";
import { Compatibility } from "./tabs/Compatibility";
import { Power } from "./tabs/Power";
import { RGB } from "./tabs/RGB";
import { Settings } from "./tabs/Settings";
import type { Config } from "./types";

export function Content() {
  const [tab, setTab] = useState("Compatibility");
  const [config, setConfig] = useState<Config | null>(null);
  const [message, setMessage] = useState("Loading");
  const savedPowerSnapshot = useRef("");
  const savedTweaksSnapshot = useRef("");
  const savedRgbSnapshot = useRef("");
  const installedGamesRequested = useRef(false);
  const load = useCallback(async () => {
    try {
      const next = await getConfig();
      next.game = currentGame();
      next.selectedGame = next.game || null;
      savedPowerSnapshot.current = JSON.stringify(next.power);
      savedTweaksSnapshot.current = JSON.stringify(next.tweaks);
      savedRgbSnapshot.current = JSON.stringify(next.rgb);
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
  if (!config) return <PanelSection title="Armada Control"><Field label={message} /></PanelSection>;
  const tabContent = (content: ReactNode) => (
    <div className="armada-control-tab-content">{content}</div>
  );
  return (
    <div className="armada-control-tabs">
      <style>{styles}</style>
      <Tabs
        activeTab={tab}
        onShowTab={setTab}
        tabs={[
          {
            id: "Compatibility",
            title: tabIcons.Compatibility,
            content: tabContent(tab === "Compatibility" ? <Compatibility config={config} setConfig={setConfig} /> : null),
          },
          {
            id: "Power",
            title: tabIcons.Power,
            content: tabContent(tab === "Power" ? <Power config={config} setConfig={setConfig} /> : null),
          },
          ...(config.rgbSupported !== false
            ? [
                {
                  id: "RGB",
                  title: tabIcons.RGB,
                  content: tabContent(tab === "RGB" ? <RGB config={config} setConfig={setConfig} /> : null),
                },
              ]
            : []),
          {
            id: "Advanced",
            title: tabIcons.Advanced,
            content: tabContent(tab === "Advanced" ? <Settings config={config} setConfig={setConfig} /> : null),
          },
        ]}
      />
    </div>
  );
}
