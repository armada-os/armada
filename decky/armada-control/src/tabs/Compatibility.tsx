import {
  ButtonItem,
  DialogBody,
  DialogButton,
  DialogFooter,
  Field,
  Focusable,
  ModalRoot,
  PanelSection,
  PanelSectionRow,
  TextField,
  ToggleField,
  showModal,
} from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { getCompatMappedAppids, reapplyPerf, restartGameMode, saveCompatApplied, saveTweaks } from "../backend";
import { SelectEdit, SliderEdit, ToggleRow } from "../components/widgets";
import { t, translateLabel } from "../i18n";
import { getGlobalResolution, setGlobalResolution } from "../lib/steamSettings";
import { clone } from "../lib/util";
import { availableGames, editTargetOptions } from "../lib/games";
import {
  FOLLOW_STEAM_COMPAT,
  USE_DEFAULT_COMPAT,
  compatSelection,
  defaultWindowsCompatTool,
  getAppCompatTools,
  getProtonTools,
  handledGameAppids,
  markCompatHandled,
  migrateWindowsCompatTool,
  resetAllGamePolicies,
  resetCompatToolToDefault,
  resetLaunchOptionsForGame,
  resolveCompatState,
  resolveProfileAppids,
  setAutoApplyCompat,
  setWindowsCompatTool,
  specifyCompatTool,
} from "../lib/steamCompat";
import type { CompatTool } from "../lib/steamCompat";
import type { Config } from "../types";

const PERF_KEYS = [
  "cores", "wineTopology", "nice", "gamescopeCores",
  "gamescopeNice", "scheduler",
];

function cpulistError(text: string, cpuCount: number): string {
  const seen = new Set<number>();
  for (const part of text.split(",")) {
    const item = part.trim();
    if (!item) continue;
    const match = /^(\d+)(?:-(\d+))?$/.exec(item);
    if (!match) return t("compatibility.invalidCoreEntry", { value: item });
    const low = Number(match[1]);
    const high = match[2] !== undefined ? Number(match[2]) : low;
    if (high < low) return t("compatibility.invalidCoreRange", { value: item });
    for (let cpu = low; cpu <= high; cpu++) {
      if (cpu >= cpuCount) return t("compatibility.cpuNotFound", { value: cpu });
      if (seen.has(cpu)) return t("compatibility.duplicateCpu", { value: cpu });
      seen.add(cpu);
    }
  }
  return seen.size ? "" : t("compatibility.enterCores");
}

const resolutionOptions = [
  { data: "Default", label: "Default" },
  { data: "Native", label: "Native" },
  { data: "1280x720", label: "1280x720" },
  { data: "960x540", label: "960x540" },
];
const fexKnobs = [
  { key: "TSOEnabled", label: "TSO Enabled" },
  { key: "X87ReducedPrecision", label: "X87 Reduced Precision" },
  { key: "Multiblock", label: "Multiblock" },
  { key: "VectorTSOEnabled", label: "Vector TSO Enabled" },
  { key: "MemcpySetTSOEnabled", label: "Memcpy Set TSO Enabled" },
  { key: "HalfBarrierTSOEnabled", label: "Half Barrier TSO Enabled" },
];
const thunkModules = [
  { module: "Vulkan", label: "Host Vulkan" },
  { module: "GL", label: "Host OpenGL" },
  { module: "asound", label: "Host ALSA" },
  { module: "drm", label: "Host DRM" },
  { module: "WaylandClient", label: "Host Wayland" },
];

function ConfirmResetAllModal({ closeModal, onConfirm }: { closeModal?: () => void; onConfirm: () => void }) {
  const confirm = () => {
    closeModal?.();
    onConfirm();
  };
  return (
    <ModalRoot onCancel={closeModal}>
      <DialogBody>
        {t("compatibility.resetAllDescription")}
      </DialogBody>
      <DialogFooter>
        <DialogButton onClick={confirm}>{t("compatibility.resetAllGames")}</DialogButton>
        <DialogButton onClick={closeModal}>{t("common.cancel")}</DialogButton>
      </DialogFooter>
    </ModalRoot>
  );
}

function ConfirmResetGameModal({
  closeModal,
  gameName,
  onConfirm,
}: {
  closeModal?: () => void;
  gameName: string;
  onConfirm: () => void;
}) {
  const confirm = () => {
    closeModal?.();
    onConfirm();
  };
  return (
    <ModalRoot onCancel={closeModal}>
      <DialogBody>
        {t("compatibility.resetGameDescription", { game: gameName })}
      </DialogBody>
      <DialogFooter>
        <DialogButton onClick={confirm}>{t("compatibility.resetGame")}</DialogButton>
        <DialogButton onClick={closeModal}>{t("common.cancel")}</DialogButton>
      </DialogFooter>
    </ModalRoot>
  );
}

function ConfirmGameModeRestartModal({
  closeModal,
  onRestart,
}: {
  closeModal?: () => void;
  onRestart: () => void;
}) {
  const restart = () => {
    closeModal?.();
    onRestart();
  };
  return (
    <ModalRoot onCancel={closeModal}>
      <DialogBody>
        {t("compatibility.restartGameModeDescription")}
      </DialogBody>
      <DialogFooter>
        <DialogButton onClick={restart}>{t("compatibility.restartGameMode")}</DialogButton>
        <DialogButton onClick={closeModal}>{t("common.later")}</DialogButton>
      </DialogFooter>
    </ModalRoot>
  );
}

function EnvVarModal({
  closeModal,
  initialKey,
  initialValue,
  onSave,
  onDelete,
}: {
  closeModal?: () => void;
  initialKey: string;
  initialValue: string;
  onSave: (key: string, value: string) => void;
  onDelete?: () => void;
}) {
  const [key, setKey] = useState(initialKey);
  const [value, setValue] = useState(initialValue);
  const [nameError, setNameError] = useState("");
  const save = () => {
    const name = key.trim();
    if (!name || name.includes("=") || name.includes("\0")) {
      setNameError(t("compatibility.invalidVariableName"));
      return;
    }
    onSave(name, value);
    closeModal?.();
  };
  return (
    <ModalRoot onCancel={closeModal}>
      <DialogBody>
        <TextField label={t("common.name")} value={key} onChange={(event) => setKey(event.target.value)} />
        {nameError ? <Field description={nameError} /> : null}
        <TextField label={t("common.value")} value={value} onChange={(event) => setValue(event.target.value)} />
      </DialogBody>
      <DialogFooter>
        <Focusable style={{ display: "flex", flexDirection: "row", gap: "8px", width: "100%" }}>
          <DialogButton onClick={save}>{t("common.save")}</DialogButton>
          {onDelete ? (
            <DialogButton
              onClick={() => {
                onDelete();
                closeModal?.();
              }}
            >
              {t("common.delete")}
            </DialogButton>
          ) : null}
          <DialogButton onClick={closeModal}>{t("common.cancel")}</DialogButton>
        </Focusable>
      </DialogFooter>
    </ModalRoot>
  );
}

export function Compatibility({ config, setConfig }: { config: Config; setConfig: Dispatch<SetStateAction<Config | null>> }) {
  const [resolution, setResolution] = useState("Default");
  const [defaultResolution, setDefaultResolution] = useState(getGlobalResolution());
  const [resolutionMessage, setResolutionMessage] = useState("");
  const [resettingGame, setResettingGame] = useState(false);
  const [resettingAll, setResettingAll] = useState(false);
  const [customSelected, setCustomSelected] = useState(false);
  const [showThunks, setShowThunks] = useState(false);
  const [showPerf, setShowPerf] = useState(false);
  const [showEnv, setShowEnv] = useState(false);
  const [customCores, setCustomCores] = useState(false);
  const [customGsCores, setCustomGsCores] = useState(false);
  const [coresDraft, setCoresDraft] = useState<string | null>(null);
  const [gsCoresDraft, setGsCoresDraft] = useState<string | null>(null);
  const [reapplyStatus, setReapplyStatus] = useState("");
  const [switchingDefault, setSwitchingDefault] = useState(false);
  const [compatTools, setCompatTools] = useState<CompatTool[]>([]);
  const [perGameTools, setPerGameTools] = useState<CompatTool[]>([]);
  const [currentTool, setCurrentTool] = useState("");
  const [globalTool, setGlobalTool] = useState(
    String(config.tweaks?.global?.windowsCompatTool || ""),
  );
  const resolvedDefaultTool = defaultWindowsCompatTool(
    compatTools, config.protonDefaults,
  );
  // The setting is kept rather than rewritten: reinstalling the tool restores the choice.
  const globalToolMissing = !!globalTool && globalTool !== FOLLOW_STEAM_COMPAT && compatTools.length > 0
    && !compatTools.some((tool) => tool.id === globalTool);
  const activeGlobalTool = !globalTool || globalToolMissing ? resolvedDefaultTool : globalTool;
  const runtimeGame = config.game;
  const games = availableGames(config);
  const selectedGame = config.selectedGame || runtimeGame || null;
  const game = selectedGame;
  const selectedAppidRef = useRef("");
  const activeGlobalToolRef = useRef(activeGlobalTool);
  activeGlobalToolRef.current = activeGlobalTool;
  selectedAppidRef.current = game?.appid || "";
  const tweaks = config.tweaks;
  const tweaksRef = useRef(tweaks);
  tweaksRef.current = tweaks;
  const apps = window.SteamClient?.Apps;
  const persistHandledGames = () => saveCompatApplied(handledGameAppids()).catch(() => {});
  // null means the pin state could not be established, which callers must not read as "none".
  const pinnedToMissingTool = async (): Promise<string[] | null | undefined> => {
    if (!compatTools.length) return null;
    if (!globalToolMissing) return undefined;
    return getCompatMappedAppids(globalTool).catch(() => null);
  };
  useEffect(() => {
    let cancelled = false;
    async function loadResolution() {
      if (!game?.appid || !apps?.GetResolutionOverrideForApp) {
        setResolution("Default");
        setResolutionMessage("");
        return;
      }
      try {
        const current = await apps.GetResolutionOverrideForApp(Number(game.appid));
        if (!cancelled) {
          setResolution(current || "Default");
          setResolutionMessage("");
        }
      } catch (error) {
        if (!cancelled) setResolutionMessage(t("compatibility.resolutionUnavailable"));
      }
    }
    loadResolution();
    return () => {
      cancelled = true;
    };
  }, [apps, game?.appid]);
  useEffect(() => {
    setCustomSelected(false);
    setCustomCores(false);
    setCustomGsCores(false);
    setCoresDraft(null);
    setGsCoresDraft(null);
    setReapplyStatus("");
  }, [game?.appid]);
  useEffect(() => {
    let cancelled = false;
    getProtonTools().then((tools) => {
      if (!cancelled) setCompatTools(tools);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  useEffect(() => {
    if (!game?.appid) {
      setCurrentTool("");
      setPerGameTools([]);
      return;
    }
    const appid = game.appid;
    let cancelled = false;
    setCurrentTool(FOLLOW_STEAM_COMPAT);
    resolveCompatState(appid).then((state) => {
      if (!cancelled) setCurrentTool(compatSelection(state, activeGlobalTool));
    });
    getAppCompatTools(appid).then((tools) => {
      if (!cancelled) setPerGameTools(tools);
    });
    return () => {
      cancelled = true;
    };
  }, [game?.appid, activeGlobalTool]);
  useEffect(() => {
    if (!apps?.RegisterForAppOverviewChanges) return;
    let cancelled = false;
    let timer: number | undefined;
    const handle = apps.RegisterForAppOverviewChanges(() => {
      const appid = selectedAppidRef.current;
      if (!appid || cancelled) return;
      if (timer !== undefined) window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        resolveCompatState(appid).then((state) => {
          if (!cancelled && selectedAppidRef.current === appid) {
            setCurrentTool(compatSelection(state, activeGlobalToolRef.current));
          }
        }).catch(() => {});
      }, 250);
    });
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
      try {
        handle?.unregister?.();
      } catch (error) {
      }
    };
  }, [apps]);
  useEffect(() => {
    setDefaultResolution(getGlobalResolution());
  }, []);
  const gameSettings = game?.appid ? tweaks.games[game.appid] || {} : {};
  const editingDefault = !game?.appid;
  const values = editingDefault ? tweaks.global : { ...tweaks.global, ...gameSettings };
  const patchSettings = (patch: Record<string, any>) => {
    setConfig((current) => {
      if (!current) return current;
      const next = clone(current);
      let target: Record<string, any> | undefined;
      if (editingDefault) {
        target = next.tweaks.global;
      } else if (game?.appid) {
        const existing = next.tweaks.games[game.appid] || {};
        target = next.tweaks.games[game.appid] = { ...existing, name: game.name || "" };
      }
      if (target) {
        for (const [key, value] of Object.entries(patch)) {
          if (value === undefined) delete target[key];
          else target[key] = value;
        }
      }
      return next;
    });
  };
  const resetGame = async (appid: string) => {
    if (resettingGame || resettingAll) return;
    setResettingGame(true);
    setConfig((current) => {
      if (!current) return current;
      const next = clone(current);
      delete next.tweaks.games[appid];
      return next;
    });
    try {
      try {
        const tool = await resetCompatToolToDefault(appid, await pinnedToMissingTool());
        if (selectedAppidRef.current === appid) {
          setCurrentTool(tool === activeGlobalTool ? USE_DEFAULT_COMPAT : tool || FOLLOW_STEAM_COMPAT);
        }
        persistHandledGames();
      } catch (error) {
      }
      await resetLaunchOptionsForGame(appid);
      if (apps?.SetAppResolutionOverride) {
        try {
          await apps.SetAppResolutionOverride(Number(appid), "Default");
          if (selectedAppidRef.current === appid) {
            setResolution("Default");
            setResolutionMessage("");
          }
        } catch (error) {
        }
      }
    } finally {
      setResettingGame(false);
    }
  };
  const setSteamResolution = async (value: string) => {
    setResolution(value);
    if (!game?.appid || !apps?.SetAppResolutionOverride) return;
    try {
      await apps.SetAppResolutionOverride(Number(game.appid), value);
      setResolutionMessage("");
    } catch (error) {
      setResolutionMessage(t("compatibility.setResolutionError"));
    }
  };
  const setSteamDefaultResolution = async (value: string) => {
    setDefaultResolution(value);
    try {
      const applied = await setGlobalResolution(value);
      setResolutionMessage("");
      setDefaultResolution(applied || "Default");
    } catch (error) {
      setResolutionMessage(t("compatibility.setDefaultResolutionError"));
    }
  };
  const resetAllGames = async () => {
    if (resettingAll || resettingGame) return;
    const selectedAppid = selectedAppidRef.current;
    setResettingAll(true);
    setConfig((current) => {
      if (!current) return current;
      const next = clone(current);
      next.tweaks.games = {};
      return next;
    });
    try {
      const gameAppids = await resolveProfileAppids(games.map((installed) => installed.appid));
      const pinned = await pinnedToMissingTool();
      let nextResolution = 0;
      const resetResolution = async () => {
        while (nextResolution < gameAppids.length) {
          const appid = gameAppids[nextResolution++];
          if (!apps?.SetAppResolutionOverride) continue;
          try {
            await apps.SetAppResolutionOverride(Number(appid), "Default");
          } catch (error) {
          }
        }
      };
      await Promise.all([
        resetAllGamePolicies(gameAppids, pinned),
        Promise.all(Array.from({ length: Math.min(10, gameAppids.length) }, resetResolution)),
      ]);
      await saveCompatApplied(handledGameAppids());
      setResolution("Default");
      if (selectedAppid && selectedAppidRef.current === selectedAppid) {
        const state = await resolveCompatState(selectedAppid);
        if (selectedAppidRef.current === selectedAppid) setCurrentTool(compatSelection(state, activeGlobalTool));
      }
    } catch (error) {
    } finally {
      setResettingAll(false);
    }
  };
  const confirmResetAllGames = () => {
    showModal(<ConfirmResetAllModal onConfirm={() => { void resetAllGames(); }} />);
  };
  const confirmResetGame = () => {
    if (!game?.appid || resettingGame || resettingAll) return;
    const appid = game.appid;
    showModal(
      <ConfirmResetGameModal
        gameName={game.name || t("games.thisGame")}
        onConfirm={() => { void resetGame(appid); }}
      />,
    );
  };
  const gameOptions = editTargetOptions(config);
  // "" is the explicit Default target, not "nothing selected"; store a sentinel
  // so it doesn't fall back to the running game in the selectedGame derivation.
  const setSelectedGame = (appid: any) => {
    const id = String(appid);
    if (!id) {
      setConfig((current) => (current ? { ...current, selectedGame: { appid: "", name: "Default" } } : current));
      return;
    }
    const saved = games.find((candidate) => candidate.appid === id);
    setConfig((current) => (current ? { ...current, selectedGame: saved || null } : current));
  };

  const toolOptions = [
    { data: FOLLOW_STEAM_COMPAT, label: t("compatibility.followSteam") },
    ...compatTools.map((tool) => ({ data: tool.id, label: tool.label })),
  ];
  const onSelectGlobalDefault = async (choice: any) => {
    if (switchingDefault) return;
    const name = String(choice);
    const oldTool = activeGlobalTool;
    setSwitchingDefault(true);
    try {
      const pinned = await pinnedToMissingTool();
      setGlobalTool(name);
      setWindowsCompatTool(name);
      patchSettings({ windowsCompatTool: name });
      await migrateWindowsCompatTool(
        config.installedGames.filter((installed) => !installed.nonSteam).map((installed) => installed.appid),
        oldTool,
        name,
        pinned,
      );
      persistHandledGames();
    } finally {
      setSwitchingDefault(false);
    }
  };
  const selectableTools = new Map<string, CompatTool>();
  for (const tool of [...perGameTools, ...compatTools]) selectableTools.set(tool.id, tool);
  if (currentTool && currentTool !== USE_DEFAULT_COMPAT && currentTool !== FOLLOW_STEAM_COMPAT && !selectableTools.has(currentTool)) {
    selectableTools.set(currentTool, { id: currentTool, label: currentTool });
  }
  const perGameToolOptions = [
    { data: USE_DEFAULT_COMPAT, label: t("common.useDefault") },
    { data: FOLLOW_STEAM_COMPAT, label: t("compatibility.followSteam") },
    ...Array.from(selectableTools.values()).map((tool) => ({ data: tool.id, label: tool.label })),
  ];
  const onSelectPerGameTool = async (choice: any) => {
    if (!game?.appid) return;
    const selection = String(choice);
    if (selection === USE_DEFAULT_COMPAT && !activeGlobalTool) return;
    const target = selection === USE_DEFAULT_COMPAT
      ? activeGlobalTool
      : selection === FOLLOW_STEAM_COMPAT
        ? ""
        : selection;
    try {
      await specifyCompatTool(game.appid, target);
      if (!game.nonSteam) {
        markCompatHandled(game.appid);
        persistHandledGames();
      }
      setCurrentTool(selection);
    } catch (error) {
    }
  };

  const presets = config.fexProfiles || {};
  const presetEntries = Object.entries(presets);
  const storedProfile = values.fexProfile as string | undefined;
  const storedConfig = values.fexConfig as Record<string, string> | undefined;
  const ownConfig = (editingDefault ? tweaks.global.fexConfig : gameSettings.fexConfig) as Record<string, string> | undefined;
  const hasPreset = !!(storedProfile && presets[storedProfile]);
  const isCustom = customSelected || (!hasPreset && !!storedConfig);
  const fexValue = isCustom ? "custom" : hasPreset ? storedProfile! : "default";
  const fexConfig: Record<string, string> = (isCustom ? storedConfig : presets[fexValue]?.config) || presets.default?.config || {};
  const fexOptions = [...presetEntries.map(([id, profile]) => ({ data: id, label: translateLabel(profile.label) })), { data: "custom", label: t("common.custom") }];
  const onSelectFex = (id: any) => {
    if (id === "custom") {
      setCustomSelected(true);
      patchSettings({ fexProfile: "custom", fexConfig: { ...(ownConfig || fexConfig) } });
      return;
    }
    setCustomSelected(false);
    patchSettings({ fexProfile: id });
  };
  const setKnob = (key: string, on: boolean) => patchSettings({ fexProfile: "custom", fexConfig: { ...fexConfig, [key]: on ? "1" : "0" } });
  const thunks: Record<string, boolean> = values.thunks || {};
  const setThunk = (module: string, on: boolean) => patchSettings({ thunks: { ...thunks, [module]: on } });

  // Performance knobs: flat keys in the same merge as the FEX settings.
  // "" in a dropdown means unset (fall back to global default / built-in).
  const perf = config.perf;
  const presetIds = ["all", ...(perf?.corePresets || []).map((option) => option.data)];
  const coreOptions = [
    { data: "", label: t("common.default") },
    ...(perf?.corePresets || [{ data: "all", label: "All Cores" }]).map((option) => ({ ...option, label: translateLabel(option.label) })),
    { data: "custom", label: t("common.custom") },
  ];
  const coresValue = String(values.cores ?? "");
  const coresIsCustom = customCores || (coresValue !== "" && !presetIds.includes(coresValue));
  const cpuCount = perf?.cpuCount || 8;
  const coresText = coresDraft ?? (presetIds.includes(coresValue) ? "" : coresValue);
  const coresError = coresIsCustom ? cpulistError(coresText, cpuCount) : "";
  const gsCoresValue = String(values.gamescopeCores ?? "");
  const gsCoresIsCustom = customGsCores || (gsCoresValue !== "" && !presetIds.includes(gsCoresValue));
  const gsCoresText = gsCoresDraft ?? (presetIds.includes(gsCoresValue) ? "" : gsCoresValue);
  const gsCoresError = gsCoresIsCustom ? cpulistError(gsCoresText, cpuCount) : "";
  const onSelectCores = (choice: any) => {
    const id = String(choice);
    if (id === "custom") {
      setCustomCores(true);
      return;
    }
    setCustomCores(false);
    setCoresDraft(null);
    patchSettings({ cores: id || undefined });
  };
  const schedulerOptions = [
    { data: "", label: t("common.default") },
    ...(perf?.schedulers || ["eevdf"]).map((name) => ({ data: name, label: name.toUpperCase() })),
  ];
  const gamescopeCoreOptions = [
    { data: "", label: t("common.default") },
    ...(perf?.corePresets || [{ data: "all", label: "All Cores" }]).map((option) => ({ ...option, label: translateLabel(option.label) })),
    { data: "custom", label: t("common.custom") },
  ];
  const hasGamePerfOverrides = !editingDefault
    && PERF_KEYS.some((key) => Object.prototype.hasOwnProperty.call(gameSettings, key));
  const resetGamePerformance = () => patchSettings(
    Object.fromEntries(PERF_KEYS.map((key) => [key, undefined])),
  );
  // env merges per-entry; unchecking a default var stores a null tombstone
  const ownEnv = ((editingDefault ? tweaks.global.env : gameSettings.env) || {}) as Record<string, string | null>;
  const globalEnv = ((!editingDefault && tweaks.global.env) || {}) as Record<string, string>;
  const patchOwnEnv = (mutate: (next: Record<string, string | null>) => void) => {
    const next = { ...ownEnv };
    mutate(next);
    patchSettings({ env: Object.keys(next).length ? next : undefined });
  };
  const saveEnvVar = (oldKey: string | null, key: string, value: string) => {
    patchOwnEnv((next) => {
      if (oldKey && oldKey !== key) delete next[oldKey];
      next[key] = value;
    });
  };
  const deleteEnvVar = (key: string) => {
    patchOwnEnv((next) => {
      delete next[key];
    });
  };
  const openEnvVar = (key: string | null) => {
    showModal(
      <EnvVarModal
        initialKey={key || ""}
        initialValue={key ? String(ownEnv[key] ?? "") : ""}
        onSave={(nextKey, nextValue) => saveEnvVar(key, nextKey, nextValue)}
        onDelete={key ? () => deleteEnvVar(key) : undefined}
      />,
    );
  };
  const runningSelectedGame = !!game?.appid && game.appid === runtimeGame?.appid;
  const onReapply = async () => {
    setReapplyStatus(t("common.applying"));
    try {
      // flush the debounce: the daemon re-reads the on-disk tweaks
      await saveTweaks(config.tweaks);
      await reapplyPerf();
      setReapplyStatus(t("compatibility.appliedToRunningGame"));
    } catch (error) {
      setReapplyStatus(String(error));
    }
  };
  const restartWithTweaks = async () => {
    setReapplyStatus(t("compatibility.restartingGameMode"));
    try {
      await saveTweaks(tweaksRef.current);
      await restartGameMode();
    } catch (error) {
      setReapplyStatus(t("compatibility.restartError", { error: String(error) }));
    }
  };
  const setGamescopeVulkanRealtime = (on: boolean) => {
    setConfig((current) => {
      if (!current) return current;
      const nextTweaks = clone(current.tweaks);
      nextTweaks.global.gamescopeVulkanRealtime = on;
      return { ...current, tweaks: nextTweaks };
    });
    showModal(
      <ConfirmGameModeRestartModal
        onRestart={() => { void restartWithTweaks(); }}
      />,
    );
  };
  const perfControls = (
    <>
      <div className="armada-subheader">{t("compatibility.game")}</div>
      <SelectEdit label={t("compatibility.cpuCores")} value={coresIsCustom ? "custom" : coresValue} options={coreOptions} onChange={onSelectCores} />
      {coresIsCustom ? (
        <PanelSectionRow>
          <TextField
            label={t("compatibility.customCoresDescription")}
            value={coresText}
            onChange={(event) => {
              // draft-local until valid: invalid text must never persist
              const text = event.target.value;
              setCoresDraft(text);
              if (!cpulistError(text, cpuCount)) patchSettings({ cores: text });
            }}
          />
        </PanelSectionRow>
      ) : null}
      {coresError && coresText ? <div className="armada-field-note">{coresError}</div> : null}
      {coresValue ? (
        <ToggleField
          label={t("compatibility.wineCpuTopology")}
          checked={values.wineTopology !== false}
          onChange={(on) => patchSettings({ wineTopology: on })}
        />
      ) : null}
      <SliderEdit label={t("compatibility.nice")} value={values.nice ?? 0} min={-20} max={19} step={1} onChange={(v) => patchSettings({ nice: v })} />
      <div className="armada-subheader">{t("compatibility.gamescope")}</div>
      <SelectEdit
        label={t("compatibility.cpuCores")}
        value={gsCoresIsCustom ? "custom" : gsCoresValue}
        options={gamescopeCoreOptions}
        onChange={(choice) => {
          const id = String(choice);
          if (id === "custom") {
            setCustomGsCores(true);
            return;
          }
          setCustomGsCores(false);
          patchSettings({ gamescopeCores: id || undefined });
        }}
      />
      {gsCoresIsCustom ? (
        <PanelSectionRow>
          <TextField
            label={t("compatibility.customCores")}
            value={gsCoresText}
            onChange={(event) => {
              const text = event.target.value;
              setGsCoresDraft(text);
              if (!cpulistError(text, cpuCount)) patchSettings({ gamescopeCores: text });
            }}
          />
        </PanelSectionRow>
      ) : null}
      {gsCoresError && gsCoresText ? <div className="armada-field-note">{gsCoresError}</div> : null}
      <SliderEdit label={t("compatibility.nice")} value={values.gamescopeNice ?? 0} min={-20} max={19} step={1} onChange={(v) => patchSettings({ gamescopeNice: v })} />
      {editingDefault ? (
        <ToggleField
          label={t("compatibility.vulkanRealtimeQueue")}
          checked={!!tweaks.global.gamescopeVulkanRealtime}
          onChange={setGamescopeVulkanRealtime}
        />
      ) : null}
      <div className="armada-subheader">{t("settings.system")}</div>
      <SelectEdit
        label={t("compatibility.cpuScheduler")}
        value={String(values.scheduler ?? "")}
        options={schedulerOptions}
        onChange={(v) => patchSettings({ scheduler: String(v) || undefined })}
      />
      {hasGamePerfOverrides ? (
        <ButtonItem layout="below" onClick={resetGamePerformance}>
          {t("compatibility.resetPerformance")}
        </ButtonItem>
      ) : null}
      {runningSelectedGame ? (
        <ButtonItem layout="below" onClick={() => { void onReapply(); }}>
          {t("compatibility.reapplyRunningGame")}
        </ButtonItem>
      ) : null}
      {reapplyStatus ? <Field label={t("common.status")} description={reapplyStatus} /> : null}
    </>
  );
  const inheritedEnvEntries = Object.entries(globalEnv).filter(([key]) => typeof ownEnv[key] !== "string");
  const ownEnvEntries = Object.entries(ownEnv).filter(([, value]) => typeof value === "string") as [string, string][];
  const envControls = (
    <>
      {inheritedEnvEntries.length ? <div className="armada-subheader">{t("compatibility.defaultVariables")}</div> : null}
      {inheritedEnvEntries.map(([key, value]) => (
        <ToggleField
          key={key}
          label={String(value) ? `${key}=${String(value)}` : key}
          checked={ownEnv[key] !== null}
          onChange={(on) => patchOwnEnv((next) => {
            if (on) delete next[key];
            else next[key] = null;
          })}
        />
      ))}
      {inheritedEnvEntries.length ? <div className="armada-subheader">{t("compatibility.perGameVariables")}</div> : null}
      {ownEnvEntries.map(([key, value]) => (
        <ButtonItem key={key} layout="below" onClick={() => openEnvVar(key)}>
          <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", textAlign: "left" }}>
            {value ? `${key}=${value}` : key}
          </div>
        </ButtonItem>
      ))}
      <ButtonItem layout="below" onClick={() => openEnvVar(null)}>
        {t("compatibility.addVariable")}
      </ButtonItem>
    </>
  );

  return (
    <>
      <PanelSection title={t("compatibility.editGameProfile")}>
        <SelectEdit value={game?.appid || ""} options={gameOptions} onChange={setSelectedGame} />
        <div className="armada-compat-note">{t("compatibility.nextLaunchNotice")}</div>
      </PanelSection>
      <PanelSection title={t("compatibility.gameProfileSettings")}>
        {editingDefault ? (
          <>
            <SelectEdit
              labelBelow
              label={t("compatibility.defaultProton")}
              value={globalTool || activeGlobalTool}
              options={toolOptions}
              onChange={onSelectGlobalDefault}
              disabled={switchingDefault}
              placeholder={globalToolMissing ? t("compatibility.chooseProton") : undefined}
            />
            {globalToolMissing ? (
              <div className="armada-compat-note armada-note-error">
                {t("compatibility.missingTool", { tool: globalTool })}
              </div>
            ) : null}
            {activeGlobalTool === FOLLOW_STEAM_COMPAT ? (
              <div className="armada-compat-note">{t("compatibility.followSteamDescription")}</div>
            ) : (
              <ToggleField
                label={t("compatibility.applyToNewGames")}
                checked={tweaks.global.autoApplyCompat !== false}
                onChange={(enabled) => {
                  setAutoApplyCompat(enabled);
                  patchSettings({ autoApplyCompat: enabled });
                }}
              />
            )}
            <SelectEdit label={t("compatibility.gameResolution")} value={defaultResolution} options={resolutionOptions.map((option) => ({ ...option, label: translateLabel(option.label) }))} onChange={setSteamDefaultResolution} />
          </>
        ) : (
          <>
            <SelectEdit labelBelow label={t("compatibility.tool")} value={currentTool} options={perGameToolOptions} onChange={onSelectPerGameTool} />
            <SelectEdit label={t("compatibility.gameResolution")} value={resolution} options={resolutionOptions.map((option) => ({ ...option, label: translateLabel(option.label) }))} onChange={setSteamResolution} />
          </>
        )}
        {resolutionMessage ? <Field label={t("common.status")} description={resolutionMessage} /> : null}
        <SelectEdit label={t("compatibility.fexPreset")} value={fexValue} options={fexOptions} onChange={onSelectFex} />
        {isCustom
          ? fexKnobs.map((knob) => (
              <ToggleField key={knob.key} label={translateLabel(knob.label)} checked={fexConfig[knob.key] === "1"} onChange={(value) => setKnob(knob.key, value)} />
            ))
          : null}
      </PanelSection>
      {config.touchscreenTrackpadSupported ? <PanelSection title={t("touchscreen.title")}>
        <SelectEdit label={t("touchscreen.mode")} value={editingDefault ? (values.touchscreenMode || "direct") : (gameSettings.touchscreenMode || "default")} options={[
          ...(!editingDefault ? [{ data: "default", label: t("touchscreen.useDefault", { mode: t(tweaks.global.touchscreenMode === "trackpad" ? "touchscreen.trackpad" : "touchscreen.direct") }) }] : []),
          { data: "direct", label: t("touchscreen.direct") },
          { data: "trackpad", label: t("touchscreen.trackpad") },
        ]} onChange={(value) => patchSettings({ touchscreenMode: value === "default" ? undefined : value })} />
        {values.touchscreenMode === "trackpad" ? <>
          <SliderEdit label={t("touchscreen.sensitivity")} value={Math.round((values.touchscreenSensitivity ?? 1) * 100)} min={25} max={300} step={25}
            onChange={(value) => patchSettings({ touchscreenSensitivity: value / 100 })} />
          <ToggleRow label={t("touchscreen.tapToClick")} value={values.touchscreenTapToClick !== false}
            onChange={(value) => patchSettings({ touchscreenTapToClick: value })} />
        </> : null}
      </PanelSection> : null}
      <PanelSection title={t("common.advanced")}>
        <ButtonItem layout="below" onClick={() => setShowPerf((value) => !value)}>
          {showPerf ? t("compatibility.hidePerformance") : t("options.performance")}
        </ButtonItem>
        {showPerf ? <div className="armada-advanced-group">{perfControls}</div> : null}
        <ButtonItem layout="below" onClick={() => setShowThunks((value) => !value)}>
          {showThunks ? t("compatibility.hideHostThunks") : t("compatibility.hostThunks")}
        </ButtonItem>
        {showThunks ? (
          <div className="armada-advanced-group">
            {thunkModules.map((thunk) => (
              <ToggleField key={thunk.module} label={translateLabel(thunk.label)} checked={thunks[thunk.module] !== false} onChange={(value) => setThunk(thunk.module, value)} />
            ))}
          </div>
        ) : null}
        <ButtonItem layout="below" onClick={() => setShowEnv((value) => !value)}>
          {showEnv ? t("compatibility.hideEnvironment") : t("compatibility.environment")}
        </ButtonItem>
        {showEnv ? <div className="armada-advanced-group">{envControls}</div> : null}
      </PanelSection>
      {!editingDefault ? (
        <PanelSection>
          <ButtonItem layout="below" disabled={resettingGame || resettingAll} onClick={confirmResetGame}>
            {resettingGame ? t("common.resetting") : t("common.resetToDefault")}
          </ButtonItem>
        </PanelSection>
      ) : (
        <PanelSection>
          <ButtonItem layout="below" disabled={resettingAll || resettingGame} onClick={confirmResetAllGames}>
            {resettingAll ? t("common.resetting") : t("compatibility.resetAllGames")}
          </ButtonItem>
        </PanelSection>
      )}
    </>
  );
}
