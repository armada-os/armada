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
import { SelectEdit, SliderEdit } from "../components/widgets";
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
  "gamescopeNice", "gamescopeRr", "scheduler",
];

function cpulistError(text: string, cpuCount: number): string {
  const seen = new Set<number>();
  for (const part of text.split(",")) {
    const item = part.trim();
    if (!item) continue;
    const match = /^(\d+)(?:-(\d+))?$/.exec(item);
    if (!match) return `Invalid entry: ${item}`;
    const low = Number(match[1]);
    const high = match[2] !== undefined ? Number(match[2]) : low;
    if (high < low) return `Invalid range: ${item}`;
    for (let cpu = low; cpu <= high; cpu++) {
      if (cpu >= cpuCount) return `No such CPU: ${cpu}`;
      if (seen.has(cpu)) return `Duplicate CPU: ${cpu}`;
      seen.add(cpu);
    }
  }
  return seen.size ? "" : "Enter cores, e.g. 7,3-6";
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
        Restores Armada defaults for launch options, resolution, and compatibility across all games.
      </DialogBody>
      <DialogFooter>
        <DialogButton onClick={confirm}>Reset All Games</DialogButton>
        <DialogButton onClick={closeModal}>Cancel</DialogButton>
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
        Restores Armada defaults for {gameName}. Custom launch options and per-game settings will be removed.
      </DialogBody>
      <DialogFooter>
        <DialogButton onClick={confirm}>Reset Game</DialogButton>
        <DialogButton onClick={closeModal}>Cancel</DialogButton>
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
        Gamescope must restart before this change takes effect. This closes any running game and restarts Steam.
      </DialogBody>
      <DialogFooter>
        <DialogButton onClick={restart}>Restart Game Mode</DialogButton>
        <DialogButton onClick={closeModal}>Later</DialogButton>
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
      setNameError("Invalid name: must be non-empty, no '='");
      return;
    }
    onSave(name, value);
    closeModal?.();
  };
  return (
    <ModalRoot onCancel={closeModal}>
      <DialogBody>
        <TextField label="Name" value={key} onChange={(event) => setKey(event.target.value)} />
        {nameError ? <Field description={nameError} /> : null}
        <TextField label="Value" value={value} onChange={(event) => setValue(event.target.value)} />
      </DialogBody>
      <DialogFooter>
        <Focusable style={{ display: "flex", flexDirection: "row", gap: "8px", width: "100%" }}>
          <DialogButton onClick={save}>Save</DialogButton>
          {onDelete ? (
            <DialogButton
              onClick={() => {
                onDelete();
                closeModal?.();
              }}
            >
              Delete
            </DialogButton>
          ) : null}
          <DialogButton onClick={closeModal}>Cancel</DialogButton>
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
  const globalToolMissing = !!globalTool && compatTools.length > 0
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
        if (!cancelled) setResolutionMessage("Resolution override is unavailable");
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
      setResolutionMessage("Failed to set resolution override");
    }
  };
  const setSteamDefaultResolution = async (value: string) => {
    setDefaultResolution(value);
    try {
      const applied = await setGlobalResolution(value);
      setResolutionMessage("");
      setDefaultResolution(applied || "Default");
    } catch (error) {
      setResolutionMessage("Failed to set default resolution");
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
        gameName={game.name || "this game"}
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

  const toolOptions = compatTools.map((tool) => ({ data: tool.id, label: tool.label }));
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
    { data: USE_DEFAULT_COMPAT, label: "Use Default" },
    { data: FOLLOW_STEAM_COMPAT, label: "Follow Steam" },
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
  const fexOptions = [...presetEntries.map(([id, profile]) => ({ data: id, label: profile.label })), { data: "custom", label: "Custom" }];
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
    { data: "", label: "Default" },
    ...(perf?.corePresets || [{ data: "all", label: "All Cores" }]),
    { data: "custom", label: "Custom" },
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
    { data: "", label: "Default" },
    ...(perf?.schedulers || ["eevdf"]).map((name) => ({ data: name, label: name.toUpperCase() })),
  ];
  const gamescopeCoreOptions = [
    { data: "", label: "Default" },
    ...(perf?.corePresets || [{ data: "all", label: "All Cores" }]),
    { data: "custom", label: "Custom" },
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
    setReapplyStatus("Applying...");
    try {
      // flush the debounce: the daemon re-reads the on-disk tweaks
      await saveTweaks(config.tweaks);
      await reapplyPerf();
      setReapplyStatus("Applied to running game");
    } catch (error) {
      setReapplyStatus(String(error));
    }
  };
  const restartWithTweaks = async () => {
    setReapplyStatus("Restarting Game Mode...");
    try {
      await saveTweaks(tweaksRef.current);
      await restartGameMode();
    } catch (error) {
      setReapplyStatus(`Restart failed: ${String(error)}`);
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
      <div className="armada-subheader">Game</div>
      <SelectEdit label="CPU Cores" value={coresIsCustom ? "custom" : coresValue} options={coreOptions} onChange={onSelectCores} />
      {coresIsCustom ? (
        <PanelSectionRow>
          <TextField
            label="Custom cores (ordered, e.g. 7,3-6)"
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
          label="Wine CPU Topology"
          checked={values.wineTopology !== false}
          onChange={(on) => patchSettings({ wineTopology: on })}
        />
      ) : null}
      <SliderEdit label="Nice" value={values.nice ?? 0} min={-20} max={19} step={1} onChange={(v) => patchSettings({ nice: v })} />
      <div className="armada-subheader">Gamescope</div>
      <SelectEdit
        label="CPU Cores"
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
            label="Custom cores"
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
      <SliderEdit label="Nice" value={values.gamescopeNice ?? 0} min={-20} max={19} step={1} onChange={(v) => patchSettings({ gamescopeNice: v })} />
      <ToggleField
        label="CPU Realtime Scheduling"
        checked={!!values.gamescopeRr}
        onChange={(on) => patchSettings({ gamescopeRr: on })}
      />
      {editingDefault ? (
        <ToggleField
          label="Vulkan Realtime Queue"
          checked={!!tweaks.global.gamescopeVulkanRealtime}
          onChange={setGamescopeVulkanRealtime}
        />
      ) : null}
      <div className="armada-subheader">System</div>
      <SelectEdit
        label="CPU Scheduler"
        value={String(values.scheduler ?? "")}
        options={schedulerOptions}
        onChange={(v) => patchSettings({ scheduler: String(v) || undefined })}
      />
      {hasGamePerfOverrides ? (
        <ButtonItem layout="below" onClick={resetGamePerformance}>
          Reset Performance to Default
        </ButtonItem>
      ) : null}
      {runningSelectedGame ? (
        <ButtonItem layout="below" onClick={() => { void onReapply(); }}>
          Re-apply to Running Game
        </ButtonItem>
      ) : null}
      {reapplyStatus ? <Field label="Status" description={reapplyStatus} /> : null}
    </>
  );
  const inheritedEnvEntries = Object.entries(globalEnv).filter(([key]) => typeof ownEnv[key] !== "string");
  const ownEnvEntries = Object.entries(ownEnv).filter(([, value]) => typeof value === "string") as [string, string][];
  const envControls = (
    <>
      {inheritedEnvEntries.length ? <div className="armada-subheader">Default Variables</div> : null}
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
      {inheritedEnvEntries.length ? <div className="armada-subheader">Per-Game Variables</div> : null}
      {ownEnvEntries.map(([key, value]) => (
        <ButtonItem key={key} layout="below" onClick={() => openEnvVar(key)}>
          <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", textAlign: "left" }}>
            {value ? `${key}=${value}` : key}
          </div>
        </ButtonItem>
      ))}
      <ButtonItem layout="below" onClick={() => openEnvVar(null)}>
        + Add Variable
      </ButtonItem>
    </>
  );

  return (
    <>
      <PanelSection title="EDIT GAME PROFILE">
        <SelectEdit value={game?.appid || ""} options={gameOptions} onChange={setSelectedGame} />
        <div className="armada-compat-note">Compatibility changes apply on next launch</div>
      </PanelSection>
      <PanelSection title="PROFILE SETTINGS">
        {editingDefault ? (
          <>
            <SelectEdit
              labelBelow
              label="Default Proton"
              value={globalTool || activeGlobalTool}
              options={toolOptions}
              onChange={onSelectGlobalDefault}
              disabled={switchingDefault}
              placeholder={globalToolMissing ? "Choose a Proton" : undefined}
            />
            {globalToolMissing ? (
              <div className="armada-compat-note armada-note-error">
                {globalTool} is no longer installed. Choose a new default for your games.
              </div>
            ) : null}
            <ToggleField
              label="Apply to New Games"
              checked={tweaks.global.autoApplyCompat !== false}
              onChange={(enabled) => {
                setAutoApplyCompat(enabled);
                patchSettings({ autoApplyCompat: enabled });
              }}
            />
            <SelectEdit label="Game Resolution" value={defaultResolution} options={resolutionOptions} onChange={setSteamDefaultResolution} />
          </>
        ) : (
          <>
            <SelectEdit labelBelow label="Compatibility Tool" value={currentTool} options={perGameToolOptions} onChange={onSelectPerGameTool} />
            <SelectEdit label="Game Resolution" value={resolution} options={resolutionOptions} onChange={setSteamResolution} />
          </>
        )}
        {resolutionMessage ? <Field label="Status" description={resolutionMessage} /> : null}
        <SelectEdit label="FEX Preset" value={fexValue} options={fexOptions} onChange={onSelectFex} />
        {isCustom
          ? fexKnobs.map((knob) => (
              <ToggleField key={knob.key} label={knob.label} checked={fexConfig[knob.key] === "1"} onChange={(value) => setKnob(knob.key, value)} />
            ))
          : null}
      </PanelSection>
      <PanelSection title="ADVANCED">
        <ButtonItem layout="below" onClick={() => setShowPerf((value) => !value)}>
          {showPerf ? "Hide Performance" : "Performance"}
        </ButtonItem>
        {showPerf ? <div className="armada-advanced-group">{perfControls}</div> : null}
        <ButtonItem layout="below" onClick={() => setShowThunks((value) => !value)}>
          {showThunks ? "Hide Host Thunks" : "Host Thunks"}
        </ButtonItem>
        {showThunks ? (
          <div className="armada-advanced-group">
            {thunkModules.map((thunk) => (
              <ToggleField key={thunk.module} label={thunk.label} checked={thunks[thunk.module] !== false} onChange={(value) => setThunk(thunk.module, value)} />
            ))}
          </div>
        ) : null}
        <ButtonItem layout="below" onClick={() => setShowEnv((value) => !value)}>
          {showEnv ? "Hide Environment" : "Environment"}
        </ButtonItem>
        {showEnv ? <div className="armada-advanced-group">{envControls}</div> : null}
      </PanelSection>
      {!editingDefault ? (
        <PanelSection>
          <ButtonItem layout="below" disabled={resettingGame || resettingAll} onClick={confirmResetGame}>
            {resettingGame ? "Resetting..." : "Reset to Default"}
          </ButtonItem>
        </PanelSection>
      ) : (
        <PanelSection>
          <ButtonItem layout="below" disabled={resettingAll || resettingGame} onClick={confirmResetAllGames}>
            {resettingAll ? "Resetting..." : "Reset All Games"}
          </ButtonItem>
        </PanelSection>
      )}
    </>
  );
}
