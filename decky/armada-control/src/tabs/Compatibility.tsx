import { showArmadaModal } from "../components/modalFocusView";
import {
  DialogBody,
  DialogButton,
  DialogButtonPrimary,
  DialogControlsSection,
  DialogControlsSectionHeader,
  Field,
  PanelSection,
} from "@decky/ui";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import { getCompatMappedAppids, getStartupInstalledGames, reapplyPerf, restartGameMode, saveCompatApplied } from "../backend";
import { ButtonRow, LabelWithBadge, NoticeSection, SectionDescription, SelectEdit, SliderEdit, Subsection, SupportingText, TextEdit, ToggleRow } from "../components/widgets";
import { ArmadaConfirmModal, ArmadaDialogFooter, ArmadaDialogHeader, ArmadaModalRoot } from "../components/ArmadaModalRoot";
import { useModalView } from "../components/useModalView";
import { LoadingState } from "../components/LoadingState";
import type { BackendState } from "../hooks/useBackendState";
import type { InitialGameSettings } from "../hooks/useGameSettingsState";
import { getCurrentLocale, t, translateLabel } from "../i18n";
import { acceptsPresetValue, findPreset, localized, resolveEnvValues } from "../lib/envPresets";
import { getGameResolution, getGlobalResolution, setGameResolution, setGlobalResolution } from "../lib/steamSettings";
import { clone } from "../lib/util";
import { availableGames } from "../lib/games";
import { changeGameProfile, gameCompatSelection, gameProfileEnabled } from "../lib/gameSettings";
import { runGameSettingsMutation } from "../lib/gameSettingsQueue";
import { trackConfigSave } from "../lib/configSaveQueue";
import { markConfigFieldChange } from "../lib/configMutation";
import { advancedChanges, advancedSettings, patchGameSettings } from "../lib/advancedSettings";
import {
  FOLLOW_STEAM_COMPAT,
  USE_DEFAULT_COMPAT,
  compatSelection,
  defaultWindowsCompatTool,
  getAppCompatTools,
  markCompatHandled,
  migrateWindowsCompatTool,
  persistHandledGames as persistCompatHandledGames,
  resetAllGamePolicies,
  resetCompatToolToDefault,
  resetLaunchOptionsForGame,
  resolveCompatState,
  resolveProfileAppids,
  setAutoApplyCompat,
  setGameCompatProfiles,
  updateGameCompatProfile,
  setWindowsCompatTool,
  specifyCompatTool,
  subscribeCompatState,
} from "../lib/steamCompat";
import type { CompatTool } from "../lib/steamCompat";
import type { Config, EnvPreset, GameRef, TurnipDriver, Tweaks } from "../types";

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

function EnvVarModal({
  closeModal,
  initialKey,
  initialValue,
  presets,
  known,
  onSave,
  onDelete,
}: {
  closeModal?: () => void;
  initialKey: string;
  initialValue: string;
  // The documented list, shipped as data in env-presets.json.
  presets: EnvPreset[];
  // Values already in effect on this profile, so picking a variable shows its current setting.
  known?: Record<string, string>;
  onSave: (key: string, value: string) => void;
  onDelete?: () => void;
}) {
  const initialPreset = findPreset(presets, initialKey);
  const initialCommonValue = acceptsPresetValue(initialPreset, initialValue);
  const startWithCommon = presets.length > 0 && (!initialKey || initialCommonValue);
  const [variableType, setVariableType] = useState<"common" | "custom">(startWithCommon ? "common" : "custom");
  const [common, setCommon] = useState({ key: initialPreset ? initialKey : "", value: initialCommonValue ? initialValue : "" });
  const [custom, setCustom] = useState({ key: initialKey, value: initialValue });
  const [nameError, setNameError] = useState("");
  const locale = getCurrentLocale();
  const { key, value } = variableType === "common" ? common : custom;
  const preset = variableType === "common" ? findPreset(presets, key) : undefined;
  const setValue = (value: string) => {
    if (variableType === "common") setCommon((current) => ({ ...current, value }));
    else setCustom((current) => ({ ...current, value }));
  };
  const pickPreset = (name: string) => {
    const current = known?.[name] ?? "";
    const value = acceptsPresetValue(findPreset(presets, name), current) ? current : "";
    setCommon({ key: name, value });
    setNameError("");
  };
  const save = () => {
    if (variableType === "common" && !acceptsPresetValue(preset, value)) return;
    const name = key.trim();
    if (!name || name.includes("=") || name.includes("\0")) {
      setNameError(t("compatibility.invalidVariableName"));
      return;
    }
    onSave(name, value);
    closeModal?.();
  };
  return (
    <ArmadaModalRoot onCancel={closeModal}>
      <ArmadaDialogHeader>{t("compatibility.environment")}</ArmadaDialogHeader>
      <DialogBody>
        <DialogControlsSection>
          <SelectEdit
            label={t("compatibility.variableType")}
            value={variableType}
            options={[
              ...(presets.length ? [{ data: "common", label: t("compatibility.commonVariable") }] : []),
              { data: "custom", label: t("compatibility.customVariable") },
            ]}
            onChange={(type) => {
              if (type === "custom" || (type === "common" && presets.length)) {
                setVariableType(type);
                setNameError("");
              }
            }}
          />
          {variableType === "common" ? (
            <SelectEdit
              label={t("common.name")}
              description={preset ? localized(preset.description, locale) : undefined}
              placeholder={t("compatibility.selectVariable")}
              value={key}
              options={presets.map((item) => ({ data: item.name, label: item.name }))}
              onChange={(name) => pickPreset(String(name))}
            />
          ) : (
            <TextEdit label={t("common.name")} value={key} onChange={(key) => {
              setCustom((current) => ({ ...current, key }));
              setNameError("");
            }} />
          )}
          {nameError ? <SupportingText className="armada-note-error">{nameError}</SupportingText> : null}
          {preset?.options ? (
            <SelectEdit
              label={t("common.value")}
              placeholder={t("compatibility.selectValue")}
              value={value}
              options={preset.options.map((option) => ({ data: option.data, label: localized(option.label, locale) }))}
              onChange={(value) => setValue(String(value))}
            />
          ) : (
            <TextEdit
              label={t("common.value")}
              description={preset?.example ? t("compatibility.exampleValue", { example: preset.example }) : undefined}
              value={value}
              onChange={setValue}
            />
          )}
        </DialogControlsSection>
      </DialogBody>
      <ArmadaDialogFooter>
        <DialogButtonPrimary disabled={variableType === "common" && !acceptsPresetValue(preset, value)} onClick={save}>{t("common.save")}</DialogButtonPrimary>
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
      </ArmadaDialogFooter>
    </ArmadaModalRoot>
  );
}

type CompatibilityProps = {
  config: Config;
  setConfig: Dispatch<SetStateAction<Config | null>>;
  saveTweaksNow: (update: (current: Tweaks) => Tweaks) => Promise<Config>;
};

export function Compatibility({ state, ...props }: CompatibilityProps & { state: BackendState<InitialGameSettings> }) {
  const { value, loading, error, refresh, setValue } = state;
  const updatePolicy = useCallback((policy: { resolution: string; selection: string; tools: CompatTool[] }) => {
    setValue((current) => {
      if (!current?.policy) return current;
      const next = { ...current.policy, ...policy };
      return JSON.stringify(next) === JSON.stringify(current.policy) ? current : { ...current, policy: next };
    });
  }, [setValue]);
  useEffect(() => () => { void refresh(); }, [refresh]);
  if (loading) return <LoadingState label={t("common.loadingSettings")} />;
  if (!value) return <PanelSection>
    <SupportingText className="armada-note-error">{t("common.loadError")}: {error}</SupportingText>
    <ButtonRow layout="below" onClick={() => { void refresh(); }}>{t("common.retry")}</ButtonRow>
  </PanelSection>;
  return <GameSettingsContent {...props} initial={value} onPolicyChange={updatePolicy} />;
}

export function GameSettingsContent({ config, setConfig, saveTweaksNow, initial, onPolicyChange }: CompatibilityProps & { initial: InitialGameSettings; onPolicyChange?: (policy: { resolution: string; selection: string; tools: CompatTool[] }) => void }) {
  const compatTools = initial.compatTools;
  const [resetVersion, setResetVersion] = useState(0);
  const [defaultResolution, setDefaultResolution] = useState(getGlobalResolution());
  const [resetting, setResetting] = useState<"game" | "all" | null>(null);
  const [changingProfile, setChangingProfile] = useState(false);
  const tweaksRef = useRef(config.tweaks);
  tweaksRef.current = config.tweaks;
  const selectedGame = config.selectedGame === undefined ? config.game || null : config.selectedGame;
  const games = availableGames(config);
  if (selectedGame?.appid && !games.some((game) => game.appid === selectedGame.appid)) games.unshift(selectedGame);

  return (
    <>
      <NoticeSection title={t("common.information")}>{t("compatibility.nextLaunchNotice")}</NoticeSection>
      <PanelSection title={t("gameSettings.perGame")}>
        <SectionDescription>{t("gameSettings.overrides")}</SectionDescription>
        <SelectEdit
          value={selectedGame?.appid || ""}
          options={[
            { data: "", label: t("gameSettings.selectGame") },
            ...games.map((game) => ({ data: game.appid, label: game.name })),
          ]}
          onChange={(appid: string) => setConfig((current) => current
            ? { ...current, selectedGame: games.find((game) => game.appid === appid) || null }
            : current)}
        />
      </PanelSection>
      {selectedGame?.appid ? (
        <CompatibilitySettings
          key={`${selectedGame.appid}-${resetVersion}`}
          config={config}
          setConfig={setConfig}
          saveTweaksNow={saveTweaksNow}
          tweaksRef={tweaksRef}
          game={selectedGame}
          initialPolicy={initial.policy}
          onPolicyChange={onPolicyChange}
          compatTools={compatTools}
          defaultResolution={defaultResolution}
          setDefaultResolution={setDefaultResolution}
          resetting={resetting}
          setResetting={setResetting}
          changingProfile={changingProfile}
          setChangingProfile={setChangingProfile}
        />
      ) : null}
      <PanelSection title={t("gameSettings.defaults")}>
        <SectionDescription>{t("gameSettings.defaultsDescription")}</SectionDescription>
      </PanelSection>
      <CompatibilitySettings
        config={config}
        setConfig={setConfig}
        saveTweaksNow={saveTweaksNow}
        tweaksRef={tweaksRef}
        game={null}
        compatTools={compatTools}
        defaultResolution={defaultResolution}
        setDefaultResolution={setDefaultResolution}
        resetting={resetting}
        setResetting={setResetting}
        changingProfile={changingProfile}
        setChangingProfile={setChangingProfile}
        onResetAll={() => {
          onPolicyChange?.({ resolution: "Default", selection: USE_DEFAULT_COMPAT, tools: initial.policy?.tools || [] });
          setResetVersion((version) => version + 1);
        }}
      />
    </>
  );
}

function CompatibilitySettings({ config, setConfig, saveTweaksNow, tweaksRef, game, compatTools, initialPolicy, defaultResolution, setDefaultResolution, resetting, setResetting, changingProfile, setChangingProfile, onResetAll, onPolicyChange }: {
  config: Config;
  setConfig: Dispatch<SetStateAction<Config | null>>;
  saveTweaksNow: (update: (current: Tweaks) => Tweaks) => Promise<Config>;
  tweaksRef: MutableRefObject<Tweaks>;
  game: GameRef | null;
  compatTools: CompatTool[];
  initialPolicy?: InitialGameSettings["policy"];
  onPolicyChange?: (policy: { resolution: string; selection: string; tools: CompatTool[] }) => void;
  defaultResolution: string;
  setDefaultResolution: (value: string) => void;
  resetting: "game" | "all" | null;
  setResetting: (value: "game" | "all" | null) => void;
  changingProfile: boolean;
  setChangingProfile: (value: boolean) => void;
  onResetAll?: () => void;
}) {
  const [resolution, setResolution] = useState(game ? config.tweaks.games[game.appid]?.steamResolution ?? initialPolicy?.resolution ?? "Default" : "Default");
  const [resolutionMessage, setResolutionMessage] = useState("");
  const [profileMessage, setProfileMessage] = useState("");
  const [switchingProfile, setSwitchingProfile] = useState(false);
  const profileTransition = useRef(false);
  const [mappingVersion, setMappingVersion] = useState(0);
  const resettingGame = resetting === "game";
  const resettingAll = resetting === "all";
  const defaultResolutionLabel = translateLabel(
    resolutionOptions.find((option) => option.data === defaultResolution)?.label || defaultResolution,
  );
  const [customSelected, setCustomSelected] = useState(false);
  const advancedModal = useRef<ReturnType<typeof showArmadaModal> | null>(null);
  const [advancedDraft, setAdvancedDraft] = useState<Record<string, any> | null>(null);
  const initialAdvanced = useRef<Record<string, any>>({});
  const initialThunks = useRef<Record<string, boolean>>({});
  const restoredAdvanced = useRef(false);
  const [advancedAction, setAdvancedAction] = useState<"saving" | "applying" | null>(null);
  const advancedSaving = advancedAction !== null;
  const [advancedError, setAdvancedError] = useState("");
  const advancedBusy = useRef(false);
  const [customCores, setCustomCores] = useState(false);
  const [customGsCores, setCustomGsCores] = useState(false);
  const [coresDraft, setCoresDraft] = useState<string | null>(null);
  const [gsCoresDraft, setGsCoresDraft] = useState<string | null>(null);
  const [reapplyStatus, setReapplyStatus] = useState("");
  const [switchingDefault, setSwitchingDefault] = useState(false);
  const [retryDefault, setRetryDefault] = useState<string | null>(null);
  const [perGameTools, setPerGameTools] = useState<CompatTool[]>(initialPolicy?.tools || []);
  const globalTool = String(config.tweaks?.global?.windowsCompatTool || "");
  const resolvedDefaultTool = defaultWindowsCompatTool(
    compatTools, config.protonDefaults,
  );
  // The setting is kept rather than rewritten: reinstalling the tool restores the choice.
  const globalToolMissing = !!globalTool && globalTool !== FOLLOW_STEAM_COMPAT && compatTools.length > 0
    && !compatTools.some((tool) => tool.id === globalTool);
  const activeGlobalTool = !globalTool || globalToolMissing ? resolvedDefaultTool : globalTool;
  const [currentTool, setCurrentTool] = useState(() => initialPolicy && game ? gameCompatSelection(config.tweaks.games[game.appid] || {}, initialPolicy.state, activeGlobalTool, initialPolicy.selection) : "");
  const toolRequest = useRef(0);
  const resolutionRequest = useRef(0);
  const defaultResolutionRequest = useRef(0);
  const pendingTool = useRef(0);
  const pendingResolution = useRef(0);
  const initialResolution = useRef(!!initialPolicy);
  const initialCompat = useRef(!!initialPolicy);
  const runtimeGame = config.game;
  const games = availableGames(config);
  const selectedAppidRef = useRef("");
  selectedAppidRef.current = game?.appid || "";
  const tweaks = config.tweaks;
  const apps = window.SteamClient?.Apps;
  const currentGlobalTool = () => {
    const saved = String(tweaksRef.current.global.windowsCompatTool || "");
    return saved && (saved === FOLLOW_STEAM_COMPAT || compatTools.some((tool) => tool.id === saved))
      ? saved : resolvedDefaultTool;
  };
  const currentSettings = () => game ? tweaksRef.current.games[game.appid] || {} : {};
  useEffect(() => {
    if (game && initialPolicy && !pendingResolution.current) setResolution(currentSettings().steamResolution ?? initialPolicy.resolution);
  }, [initialPolicy?.resolution, game?.appid]);
  useEffect(() => {
    if (game && initialPolicy && !pendingTool.current) setCurrentTool(gameCompatSelection(currentSettings(), initialPolicy.state, currentGlobalTool(), initialPolicy.selection));
  }, [initialPolicy?.state, game?.appid]);
  useEffect(() => {
    if (initialPolicy) setPerGameTools(initialPolicy.tools);
  }, [initialPolicy?.tools]);
  useEffect(() => {
    if (game && currentTool) onPolicyChange?.({ resolution, selection: currentTool, tools: perGameTools });
  }, [resolution, currentTool, perGameTools, onPolicyChange, game?.appid]);
  const persistHandledGames = () => persistCompatHandledGames(saveCompatApplied).catch(() => {});
  // null means the pin state could not be established, which callers must not read as "none".
  const pinnedToMissingTool = async (): Promise<string[] | null | undefined> => {
    if (!compatTools.length) return null;
    const saved = String(tweaksRef.current.global.windowsCompatTool || "");
    if (!saved || saved === FOLLOW_STEAM_COMPAT || compatTools.some((tool) => tool.id === saved)) return undefined;
    return getCompatMappedAppids(saved).catch(() => null);
  };
  useEffect(() => {
    if (initialResolution.current) { initialResolution.current = false; return; }
    let cancelled = false;
    async function loadResolution() {
      if (!game?.appid || !apps?.GetResolutionOverrideForApp) {
        setResolution("Default");
        setResolutionMessage("");
        return;
      }
      try {
        const revision = resolutionRequest.current;
        const current = await getGameResolution(game.appid);
        if (!cancelled && !pendingResolution.current && revision === resolutionRequest.current) {
          setResolution(currentSettings().steamResolution ?? current ?? "Default");
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
  }, [apps, game?.appid, mappingVersion]);
  useEffect(() => {
    setCustomSelected(false);
    setCustomCores(false);
    setCustomGsCores(false);
    setCoresDraft(null);
    setGsCoresDraft(null);
    setReapplyStatus("");
  }, [game?.appid]);
  useEffect(() => {
    if (!game?.appid) {
      setCurrentTool("");
      setPerGameTools([]);
      return;
    }
    if (initialCompat.current) { initialCompat.current = false; return; }
    const appid = game.appid;
    let cancelled = false;
    const revision = toolRequest.current;
    resolveCompatState(appid).then((state) => {
      if (!cancelled && !pendingTool.current && revision === toolRequest.current) setCurrentTool(gameCompatSelection(currentSettings(), state, currentGlobalTool()));
    }).catch(() => {});
    getAppCompatTools(appid).then((tools) => {
      if (!cancelled) setPerGameTools(tools);
    }).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [game?.appid, mappingVersion]);
  useEffect(() => {
    if (!game?.appid) return;
    const appid = game.appid;
    return subscribeCompatState(appid, (state) => {
      if (!pendingTool.current && selectedAppidRef.current === appid) {
        setCurrentTool(gameCompatSelection(currentSettings(), state, currentGlobalTool()));
      }
    });
  }, [game?.appid]);
  const gameSettings = game?.appid ? tweaks.games[game.appid] || {} : {};
  const editingDefault = !game?.appid;
  const profileEnabled = editingDefault || gameProfileEnabled(gameSettings, currentTool, resolution);
  const values = editingDefault ? tweaks.global : { ...tweaks.global, ...gameSettings };
  const draft = advancedDraft ?? advancedSettings(editingDefault ? tweaks.global : gameSettings, editingDefault);
  const advancedValues = editingDefault ? draft : { ...tweaks.global, ...draft };
  const patchAdvanced = (patch: Record<string, any> | ((current: Record<string, any>) => Record<string, any>)) => {
    if (advancedBusy.current) return;
    setAdvancedDraft((current) => {
      const next = { ...current, ...(typeof patch === "function" ? patch(current || {}) : patch) };
      for (const key of Object.keys(next)) if (next[key] === undefined) delete next[key];
      return next;
    });
  };
  const patchSettings = (patch: Record<string, any>) => {
    markConfigFieldChange(setConfig, "tweaks", Object.keys(patch).map((key) => game ? ["games", game.appid, key] : ["global", key]));
    const update = (current: Tweaks) => patchGameSettings(current, game, patch);
    tweaksRef.current = update(tweaksRef.current);
    if (game?.appid) {
      const policy = Object.fromEntries(Object.entries(patch).filter(([key]) => key === "enabled" || key === "steamCompatTool"));
      if (Object.keys(policy).length) updateGameCompatProfile(game.appid, policy);
    }
    setConfig((current) => current ? { ...current, tweaks: update(current.tweaks) } : current);
  };
  const persistSettings = async (patch: Record<string, any>) => {
    markConfigFieldChange(setConfig, "tweaks", Object.keys(patch).map((key) => game ? ["games", game.appid, key] : ["global", key]));
    const saved = await saveTweaksNow((current) => patchGameSettings(current, game, patch));
    tweaksRef.current = saved.tweaks;
    if (game?.appid) {
      const policy = Object.fromEntries(Object.entries(patch).filter(([key]) => key === "enabled" || key === "steamCompatTool"));
      if (Object.keys(policy).length) updateGameCompatProfile(game.appid, policy);
    }
  };
  const mutateAndSave = <T,>(mutate: () => Promise<T>) => trackConfigSave(runGameSettingsMutation(mutate));
  const changeNativeGameProfile = (appid: string, enabled: boolean, persist?: (patch: Partial<Tweaks["games"][string]>) => Promise<void>) => {
    if (!apps?.GetResolutionOverrideForApp || !apps.SetAppResolutionOverride) {
      throw new Error("Steam resolution settings are unavailable");
    }
    return changeGameProfile(tweaksRef.current.games[appid] || {}, enabled, {
      readCompat: () => resolveCompatState(appid),
      readResolution: () => getGameResolution(appid),
      selectCompat: async (selection) => {
        if (selection === USE_DEFAULT_COMPAT) {
          await resetCompatToolToDefault(appid, await pinnedToMissingTool());
        } else {
          await specifyCompatTool(appid, selection);
        }
      },
      restoreCompat: (state) => specifyCompatTool(appid, state.priority >= 250 ? state.tool : ""),
      writeResolution: (value) => setGameResolution(appid, value),
      compatSelection: (state) => compatSelection(state, currentGlobalTool()),
      persist,
    });
  };
  const setGameProfileEnabled = async (enabled: boolean) => {
    if (!game?.appid || resetting || changingProfile || profileTransition.current) return;
    const appid = game.appid;
    profileTransition.current = true;
    setSwitchingProfile(true);
    setChangingProfile(true);
    setProfileMessage("");
    try {
      await mutateAndSave(async () => {
        await changeNativeGameProfile(appid, enabled, persistSettings);
        if (!game.nonSteam) {
          markCompatHandled(appid);
          persistHandledGames();
        }
        setMappingVersion((version) => version + 1);
      });
    } catch (error) {
      setProfileMessage(t("gameSettings.updateError", { error: String(error) }));
    } finally {
      profileTransition.current = false;
      setSwitchingProfile(false);
      setChangingProfile(false);
    }
  };
  const resetGame = async (appid: string) => {
    if (resetting || changingProfile) return;
    setResetting("game");
    setProfileMessage("");
    try {
      await mutateAndSave(async () => {
        if (!(await resetLaunchOptionsForGame(appid))) throw new Error("Could not reset Steam launch options");
        await changeNativeGameProfile(appid, false);
        markConfigFieldChange(setConfig, "tweaks", [["games", appid]]);
        const saved = await saveTweaksNow((current) => {
          const next = clone(current);
          delete next.games[appid];
          return next;
        });
        tweaksRef.current = saved.tweaks;
        updateGameCompatProfile(appid, null);
        persistHandledGames();
        setResolution("Default");
        setCurrentTool(USE_DEFAULT_COMPAT);
        setResolutionMessage("");
        setMappingVersion((version) => version + 1);
      });
    } catch (error) {
      setProfileMessage(t("gameSettings.updateError", { error: String(error) }));
    } finally {
      setResetting(null);
    }
  };
  const setSteamResolution = async (value: string) => {
    if (!game?.appid || !apps?.SetAppResolutionOverride) return;
    const revision = ++resolutionRequest.current;
    pendingResolution.current++;
    setResolution(value);
    setResolutionMessage("");
    try {
      await mutateAndSave(async () => {
        const before = await getGameResolution(game.appid);
        await setGameResolution(game.appid, value);
        try {
          await persistSettings({ steamResolution: value });
        } catch (error) {
          await setGameResolution(game.appid, before);
          throw error;
        }
      });
    } catch (error) {
      if (revision === resolutionRequest.current) {
        const saved = await getGameResolution(game.appid).catch(() => "Default");
        if (revision === resolutionRequest.current) {
          setResolution(currentSettings().steamResolution ?? saved ?? "Default");
          setResolutionMessage(t("compatibility.setResolutionError"));
        }
      }
    } finally {
      pendingResolution.current--;
      if (!pendingResolution.current) setMappingVersion((version) => version + 1);
    }
  };
  const setSteamDefaultResolution = async (value: string) => {
    const revision = ++defaultResolutionRequest.current;
    setDefaultResolution(value);
    try {
      await mutateAndSave(async () => {
        const applied = await setGlobalResolution(value);
        if (revision === defaultResolutionRequest.current) {
          setResolutionMessage("");
          setDefaultResolution(applied || "Default");
        }
      });
    } catch (error) {
      if (revision === defaultResolutionRequest.current) {
        setDefaultResolution(getGlobalResolution());
        setResolutionMessage(t("compatibility.setDefaultResolutionError"));
      }
    }
  };
  const resetAllGames = async () => {
    if (resetting || changingProfile) return;
    const knownAppids = Array.from(new Set([...games.map((installed) => installed.appid), ...Object.keys(tweaksRef.current.games)]));
    setResetting("all");
    setProfileMessage("");
    try {
      await mutateAndSave(async () => {
        const gameAppids = await resolveProfileAppids(knownAppids);
        const pinned = await pinnedToMissingTool();
        let nextResolution = 0;
        const resetResolution = async () => {
          while (nextResolution < gameAppids.length) {
            const appid = gameAppids[nextResolution++];
            if (!apps?.SetAppResolutionOverride) throw new Error("Steam resolution settings are unavailable");
            await setGameResolution(appid, "Default");
          }
        };
        const results = await Promise.allSettled([
          resetAllGamePolicies(gameAppids, pinned),
          ...Array.from({ length: Math.min(10, gameAppids.length) }, resetResolution),
        ]);
        const failed = results.find((result) => result.status === "rejected");
        if (failed?.status === "rejected") throw failed.reason;
        markConfigFieldChange(setConfig, "tweaks", [["games"]]);
        const saved = await saveTweaksNow((current) => ({ ...current, games: {} }));
        tweaksRef.current = saved.tweaks;
        setGameCompatProfiles({});
        persistHandledGames();
        setResolution("Default");
        onResetAll?.();
      });
    } catch (error) {
      setProfileMessage(t("gameSettings.updateError", { error: String(error) }));
    } finally {
      setResetting(null);
    }
  };
  const confirmResetAllGames = () => {
    showArmadaModal(<ArmadaConfirmModal
      title={t("compatibility.resetAllGames")}
      description={t("compatibility.resetAllDescription")}
      confirmText={t("compatibility.resetAllGames")}
      cancelText={t("common.cancel")}
      closeBeforeConfirm
      onConfirm={() => { void resetAllGames(); }}
    />);
  };
  const confirmResetGame = () => {
    if (!game?.appid || resetting || changingProfile) return;
    const appid = game.appid;
    showArmadaModal(
      <ArmadaConfirmModal
        title={t("compatibility.resetGame")}
        description={t("compatibility.resetGameDescription", { game: game.name || t("games.thisGame") })}
        confirmText={t("compatibility.resetGame")}
        cancelText={t("common.cancel")}
        closeBeforeConfirm
        onConfirm={() => { void resetGame(appid); }}
      />,
    );
  };
  const toolOptions = [
    { data: FOLLOW_STEAM_COMPAT, label: t("compatibility.followSteam") },
    ...compatTools.map((tool) => ({ data: tool.id, label: tool.label })),
  ];
  const onSelectGlobalDefault = async (choice: any) => {
    if (switchingDefault) return;
    const name = String(choice);
    setSwitchingDefault(true);
    setRetryDefault(null);
    setProfileMessage("");
    try {
      await mutateAndSave(async () => {
        const oldTool = currentGlobalTool();
        const pinned = await pinnedToMissingTool();
        setWindowsCompatTool(name);
        try {
          await persistSettings({ windowsCompatTool: name });
        } catch (error) {
          setWindowsCompatTool(oldTool);
          throw error;
        }
        const installed = await getStartupInstalledGames();
        const appids = Array.from(new Set([
          ...installed.filter((game) => !game.nonSteam).map((game) => game.appid),
          ...config.installedGames.filter((game) => !game.nonSteam).map((game) => game.appid),
          ...Object.keys(tweaksRef.current.games),
        ]));
        await migrateWindowsCompatTool(
          appids,
          oldTool,
          name,
          pinned,
        );
        persistHandledGames();
      });
    } catch (error) {
      setRetryDefault(name);
      setProfileMessage(t("gameSettings.updateError", { error: String(error) }));
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
    { data: USE_DEFAULT_COMPAT, label: t("gameSettings.inherit", { value: toolOptions.find((option) => option.data === activeGlobalTool)?.label || activeGlobalTool }) },
    { data: FOLLOW_STEAM_COMPAT, label: t("compatibility.followSteam") },
    ...Array.from(selectableTools.values()).map((tool) => ({ data: tool.id, label: tool.label })),
  ];
  const onSelectPerGameTool = async (choice: any) => {
    if (!game?.appid) return;
    const selection = String(choice);
    if (selection === USE_DEFAULT_COMPAT && !activeGlobalTool) return;
    const revision = ++toolRequest.current;
    pendingTool.current++;
    setCurrentTool(selection);
    setProfileMessage("");
    try {
      await mutateAndSave(async () => {
        const target = selection === USE_DEFAULT_COMPAT ? currentGlobalTool()
          : selection === FOLLOW_STEAM_COMPAT ? "" : selection;
        const before = await resolveCompatState(game.appid);
        if (!before) throw new Error("Steam compatibility settings are unavailable");
        await specifyCompatTool(game.appid, target);
        try {
          await persistSettings({ steamCompatTool: selection });
        } catch (error) {
          await specifyCompatTool(game.appid, before.priority >= 250 ? before.tool : "");
          throw error;
        }
        if (!game.nonSteam) {
          markCompatHandled(game.appid);
          persistHandledGames();
        }
      });
    } catch (error) {
      if (revision === toolRequest.current) {
        const state = await resolveCompatState(game.appid).catch(() => null);
        if (revision === toolRequest.current) {
          setCurrentTool(gameCompatSelection(currentSettings(), state, currentGlobalTool()));
          setProfileMessage(t("gameSettings.updateError", { error: String(error) }));
        }
      }
    } finally {
      pendingTool.current--;
      if (!pendingTool.current) setMappingVersion((version) => version + 1);
    }
  };

  const presets = config.fexProfiles || {};
  const presetEntries = Object.entries(presets);
  const storedProfile = values.fexProfile as string | undefined;
  const storedConfig = values.fexConfig as Record<string, string> | undefined;
  const hasPreset = !!(storedProfile && presets[storedProfile]);
  const isCustom = customSelected || (!hasPreset && !!storedConfig);
  const inheritedFex = !editingDefault && !Object.prototype.hasOwnProperty.call(gameSettings, "fexProfile")
    && !Object.prototype.hasOwnProperty.call(gameSettings, "fexConfig");
  const fexValue = isCustom ? "custom" : hasPreset ? storedProfile! : "default";
  const fexConfig: Record<string, string> = (isCustom ? storedConfig : presets[fexValue]?.config) || presets.default?.config || {};
  const fexOptions = [
    ...(!editingDefault ? [{ data: "", label: t("gameSettings.inherit", { value: translateLabel(presets[tweaks.global.fexProfile || "default"]?.label || t("common.custom")) }) }] : []),
    ...presetEntries.map(([id, profile]) => ({ data: id, label: translateLabel(profile.label) })),
    { data: "custom", label: t("common.custom") },
  ];
  const latestFexConfig = (restoreSaved = false) => {
    const own = editingDefault ? tweaksRef.current.global : tweaksRef.current.games[game.appid] || {};
    const current = editingDefault ? own : { ...tweaksRef.current.global, ...own };
    return (restoreSaved && own.fexConfig) || presets[current.fexProfile || ""]?.config || current.fexConfig || presets.default?.config || {};
  };
  const onSelectFex = (id: any) => {
    if (id === "" && !editingDefault) {
      setCustomSelected(false);
      patchSettings({ fexProfile: undefined, fexConfig: undefined });
      return;
    }
    if (id === "custom") {
      setCustomSelected(true);
      patchSettings({ fexProfile: "custom", fexConfig: { ...latestFexConfig(true) } });
      return;
    }
    setCustomSelected(false);
    patchSettings({ fexProfile: id });
  };
  const setKnob = (key: string, on: boolean) => patchSettings({ fexProfile: "custom", fexConfig: { ...latestFexConfig(), [key]: on ? "1" : "0" } });
  const turnipDrivers = config.turnipDrivers || [];
  const turnipLabel = (driver: TurnipDriver) => {
    const name = driver.id === "stable" ? t("compatibility.turnipStable") : driver.label;
    return driver.version ? `${name} (${driver.version})` : name;
  };
  const turnipOptions = [
    ...(editingDefault ? [] : [{ data: "", label: t("common.useDefault") }]),
    ...turnipDrivers.map((driver) => ({ data: driver.id, label: turnipLabel(driver) })),
  ];
  const ownTurnip = draft.turnipDriver;
  const knownTurnip = (id: unknown) => turnipDrivers.some((driver) => driver.id === id);
  // A saved driver that is no longer installed launches on Stable, so show Stable.
  const turnipValue = knownTurnip(ownTurnip) ? String(ownTurnip) : editingDefault || ownTurnip ? "stable" : "";
  const thunks: Record<string, boolean> = advancedValues.thunks || {};
  const setThunk = (module: string, on: boolean) => patchAdvanced((current) => ({ thunks: { ...(current.thunks ?? tweaksRef.current.global.thunks), [module]: on } }));

  // Performance knobs: flat keys in the same merge as the FEX settings.
  // "" in a dropdown means unset (fall back to global default / built-in).
  const perf = config.perf;
  const presetIds = ["all", ...(perf?.corePresets || []).map((option) => option.data)];
  const coreOptions = [
    { data: "", label: t("common.default") },
    ...(perf?.corePresets || [{ data: "all", label: "All Cores" }]).map((option) => ({ ...option, label: translateLabel(option.label) })),
    { data: "custom", label: t("common.custom") },
  ];
  const coresValue = String((editingDefault ? tweaks.global : gameSettings).cores ?? "");
  const coresIsCustom = customCores || (coresValue !== "" && !presetIds.includes(coresValue));
  const cpuCount = perf?.cpuCount || 8;
  const coresText = coresDraft ?? (presetIds.includes(coresValue) ? "" : coresValue);
  const coresError = coresIsCustom ? cpulistError(coresText, cpuCount) : "";
  const gsCoresValue = String(draft.gamescopeCores ?? "");
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
  const restoreAdvanced = () => {
    if (advancedBusy.current || (editingDefault && !config.tweaksDefaults)) return;
    restoredAdvanced.current = true;
    setCustomGsCores(false);
    setGsCoresDraft(null);
    setAdvancedDraft(editingDefault ? advancedSettings(config.tweaksDefaults!.global, true) : {});
  };
  // env merges per-entry; unchecking a default var stores a null tombstone
  const ownEnv = ((editingDefault ? tweaks.global.env : gameSettings.env) || {}) as Record<string, string | null>;
  const globalEnv = ((!editingDefault && tweaks.global.env) || {}) as Record<string, string>;
  const patchOwnEnv = (mutate: (next: Record<string, string | null>) => void) => {
    const current = editingDefault ? tweaksRef.current.global : tweaksRef.current.games[game.appid];
    const next = { ...current?.env } as Record<string, string | null>;
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
    showArmadaModal(
      <EnvVarModal
        initialKey={key || ""}
        initialValue={key ? String(ownEnv[key] ?? "") : ""}
        presets={config.envPresets}
        known={resolveEnvValues(ownEnv, globalEnv)}
        onSave={(nextKey, nextValue) => saveEnvVar(key, nextKey, nextValue)}
        onDelete={key ? () => deleteEnvVar(key) : undefined}
      />,
    );
  };
  const runningSelectedGame = !!game?.appid && game.appid === runtimeGame?.appid;
  const onReapply = async () => {
    if (advancedBusy.current || advancedDirty) return;
    advancedBusy.current = true;
    setAdvancedAction("applying");
    setReapplyStatus(t("common.applying"));
    try {
      // flush the debounce: the daemon re-reads the on-disk tweaks
      await saveTweaksNow((current) => current);
      await reapplyPerf();
      setReapplyStatus(t("compatibility.appliedToRunningGame"));
    } catch (error) {
      setReapplyStatus(String(error));
    } finally {
      advancedBusy.current = false;
      setAdvancedAction(null);
    }
  };
  const restartWithTweaks = async () => {
    setReapplyStatus(t("compatibility.restartingGameMode"));
    try {
      await saveTweaksNow((current) => current);
      await restartGameMode();
    } catch (error) {
      setReapplyStatus(t("compatibility.restartError", { error: String(error) }));
    }
  };
  const confirmGameModeRestart = () => {
    showArmadaModal(
      <ArmadaConfirmModal
        title={t("compatibility.restartGameMode")}
        description={t("compatibility.restartGameModeDescription")}
        confirmText={t("compatibility.restartGameMode")}
        cancelText={t("common.later")}
        closeBeforeConfirm
        onConfirm={() => { void restartWithTweaks(); }}
      />,
    );
  };
  const cpuControls = (
    <>
      <SelectEdit label={t("compatibility.gameCpuCores")} value={coresIsCustom ? "custom" : coresValue} options={coreOptions} onChange={onSelectCores} />
      {coresIsCustom ? (
        <TextEdit
          label={t("compatibility.customCoresDescription")}
          value={coresText}
          onChange={(text) => {
            // Invalid drafts must never persist.
            setCoresDraft(text);
            if (!cpulistError(text, cpuCount)) patchSettings({ cores: text });
          }}
        />
      ) : null}
      {coresError ? <SupportingText className="armada-note-error">{coresError}</SupportingText> : null}
      {values.cores ? (
        <ToggleRow
          label={t("compatibility.wineCpuTopology")}
          value={values.wineTopology !== false}
          onChange={(on) => patchSettings({ wineTopology: on })}
        />
      ) : null}
    </>
  );
  const perfControls = (
    <>
      <SliderEdit
        label={t("compatibility.gameProcessPriority")}
        description={t("compatibility.processPriorityDescription")}
        value={advancedValues.nice ?? 0}
        min={-20} max={19} step={1}
        disabled={advancedSaving}
        onChange={(v) => patchAdvanced({ nice: v })}
      />
      <SliderEdit
        label={t("compatibility.gamescopeProcessPriority")}
        description={t("compatibility.processPriorityDescription")}
        value={advancedValues.gamescopeNice ?? 0}
        min={-20} max={19} step={1}
        disabled={advancedSaving}
        onChange={(v) => patchAdvanced({ gamescopeNice: v })}
      />
      <SelectEdit
        label={t("compatibility.gamescopeCpuCores")}
        value={gsCoresIsCustom ? "custom" : gsCoresValue}
        options={coreOptions}
        disabled={advancedSaving}
        onChange={(choice) => {
          const id = String(choice);
          if (id === "custom") {
            setCustomGsCores(true);
            return;
          }
          setCustomGsCores(false);
          setGsCoresDraft(null);
          patchAdvanced({ gamescopeCores: id || undefined });
        }}
      />
      {gsCoresIsCustom ? (
        <TextEdit
          label={t("compatibility.customCores")}
          value={gsCoresText}
          disabled={advancedSaving}
          onChange={(text) => {
            setGsCoresDraft(text);
            if (!cpulistError(text, cpuCount)) patchAdvanced({ gamescopeCores: text });
          }}
        />
      ) : null}
      {gsCoresError ? <SupportingText className="armada-note-error">{gsCoresError}</SupportingText> : null}
      <SelectEdit
        label={t("compatibility.cpuScheduler")}
        value={String(draft.scheduler ?? "")}
        options={schedulerOptions}
        disabled={advancedSaving}
        onChange={(v) => patchAdvanced({ scheduler: String(v) || undefined })}
      />
      {editingDefault ? (
        <ToggleRow
          label={t("compatibility.vulkanRealtimeQueue")}
          value={!!advancedValues.gamescopeVulkanRealtime}
          disabled={advancedSaving}
          onChange={(enabled) => patchAdvanced({ gamescopeVulkanRealtime: enabled })}
        />
      ) : null}
    </>
  );
  const inheritedEnvEntries = Object.entries(globalEnv).filter(([key]) => typeof ownEnv[key] !== "string");
  const ownEnvEntries = Object.entries(ownEnv).filter(([, value]) => typeof value === "string") as [string, string][];
  const envControls = (
    <>
      {inheritedEnvEntries.map(([key, value]) => (
        <ToggleRow
          key={key}
          label={<LabelWithBadge badge={t("compatibility.globalVariable")}>{value ? `${key}=${value}` : key}</LabelWithBadge>}
          value={ownEnv[key] !== null}
          onChange={(on) => patchOwnEnv((next) => {
            if (on) delete next[key];
            else next[key] = null;
          })}
        />
      ))}
      {ownEnvEntries.map(([key, value]) => (
        <ButtonRow key={key} layout="below" onClick={() => openEnvVar(key)}>
          {editingDefault ? (
            <LabelWithBadge badge={t("compatibility.globalVariable")}>{value ? `${key}=${value}` : key}</LabelWithBadge>
          ) : (
            <div className="armada-truncated-label">{value ? `${key}=${value}` : key}</div>
          )}
        </ButtonRow>
      ))}
      <ButtonRow variant="primary" layout="below" onClick={() => openEnvVar(null)}>
        {t("compatibility.addVariable")}
      </ButtonRow>
    </>
  );

  const closeAdvanced = () => {
    if (advancedBusy.current) return;
    const modal = advancedModal.current;
    advancedModal.current = null;
    setAdvancedDraft(null);
    modal?.Close();
  };
  const advancedPatch = advancedChanges(initialAdvanced.current, draft);
  const advancedDirty = Object.keys(advancedPatch).length > 0;
  const saveAdvanced = async () => {
    if (advancedBusy.current || !advancedDirty || gsCoresError) return;
    advancedBusy.current = true;
    setAdvancedAction("saving");
    setAdvancedError("");
    let restartRequired = false;
    try {
      await saveTweaksNow((current) => {
        const patch = { ...advancedPatch };
        if ("thunks" in patch && !restoredAdvanced.current) {
          const target = game ? current.games[game.appid] : current.global;
          const inherited = game ? current.global.thunks : undefined;
          const changed = advancedChanges(initialThunks.current, draft.thunks || {});
          patch.thunks = { ...(target?.thunks || inherited || {}), ...changed };
        }
        const next = patchGameSettings(current, game, patch);
        restartRequired = editingDefault
          && !!current.global.gamescopeVulkanRealtime !== !!next.global.gamescopeVulkanRealtime;
        return next;
      });
      markConfigFieldChange(setConfig, "tweaks", Object.keys(advancedPatch).map((key) => game ? ["games", game.appid, key] : ["global", key]));
      advancedBusy.current = false;
      closeAdvanced();
      if (restartRequired) confirmGameModeRestart();
    } catch (error) {
      setAdvancedError(String(error));
    } finally {
      advancedBusy.current = false;
      setAdvancedAction(null);
    }
  };
  const advancedView = useModalView(
    <ArmadaModalRoot closeModal={closeAdvanced} onCancel={closeAdvanced} bAllowFullSize bCancelDisabled={advancedSaving} bDisableBackgroundDismiss={advancedSaving}>
      <ArmadaDialogHeader>{t("compatibility.advancedSettings")}</ArmadaDialogHeader>
      <DialogBody>
        {advancedError ? <div role="alert"><SupportingText className="armada-note-error">{advancedError}</SupportingText></div> : null}
        <DialogControlsSection>
          <DialogControlsSectionHeader>{t("options.performance")}</DialogControlsSectionHeader>
          {perfControls}
        </DialogControlsSection>
        {turnipDrivers.length > 1 ? (
          <DialogControlsSection>
            <DialogControlsSectionHeader>{t("compatibility.drivers")}</DialogControlsSectionHeader>
            <SelectEdit label="Turnip" value={turnipValue} options={turnipOptions} disabled={advancedSaving} onChange={(id) => patchAdvanced({ turnipDriver: String(id) || undefined })}
              description={turnipValue ? t(turnipValue.startsWith("user:") ? "compatibility.turnipUserNote" : "compatibility.turnipBuiltinNote") : undefined} />
          </DialogControlsSection>
        ) : null}
        <DialogControlsSection>
          <DialogControlsSectionHeader>{t("compatibility.hostThunks")}</DialogControlsSectionHeader>
          {thunkModules.map((thunk) => (
            <ToggleRow key={thunk.module} label={translateLabel(thunk.label)} value={thunks[thunk.module] !== false} disabled={advancedSaving} onChange={(value) => setThunk(thunk.module, value)} />
          ))}
        </DialogControlsSection>
        {reapplyStatus ? <Field label={t("common.status")} description={reapplyStatus} bottomSeparator="none" /> : null}
      </DialogBody>
      <ArmadaDialogFooter>
        <DialogButtonPrimary disabled={advancedSaving || !advancedDirty || !!gsCoresError} onClick={() => { void saveAdvanced(); }}>{advancedAction === "saving" ? t("common.saving") : t("common.saveChanges")}</DialogButtonPrimary>
        <DialogButton disabled={advancedSaving} onClick={closeAdvanced}>{t("common.cancel")}</DialogButton>
        <DialogButton disabled={advancedSaving || (editingDefault && !config.tweaksDefaults)} onClick={restoreAdvanced}>{t("common.resetToDefault")}</DialogButton>
        {runningSelectedGame ? (
          <DialogButton disabled={advancedSaving || advancedDirty} onClick={() => { void onReapply(); }}>{advancedAction === "applying" ? t("common.applying") : t("compatibility.reapplyRunningGame")}</DialogButton>
        ) : null}
      </ArmadaDialogFooter>
    </ArmadaModalRoot>,
  );
  useEffect(() => () => {
    const modal = advancedModal.current;
    advancedModal.current = null;
    modal?.Close();
  }, []);
  useEffect(() => {
    if (!profileEnabled || switchingProfile) closeAdvanced();
  }, [profileEnabled, switchingProfile]);
  const openAdvanced = () => {
    if (advancedModal.current) return;
    initialAdvanced.current = advancedSettings(editingDefault ? tweaksRef.current.global : tweaksRef.current.games[game!.appid] || {}, editingDefault);
    initialThunks.current = clone(thunks);
    restoredAdvanced.current = false;
    setAdvancedDraft(clone(initialAdvanced.current));
    setCustomGsCores(false);
    setGsCoresDraft(null);
    setAdvancedError("");
    setReapplyStatus("");
    advancedModal.current = showArmadaModal(advancedView, undefined, {
      fnOnClose: () => {
        advancedModal.current = null;
        setAdvancedDraft(null);
      },
    });
  };

  return (
    <>
      {!editingDefault ? (
        <PanelSection>
          <ToggleRow
            label={t("gameSettings.usePerGame")}
            description={t("gameSettings.usePerGameDescription")}
            value={profileEnabled}
            disabled={!!resetting || changingProfile || switchingProfile}
            onChange={(enabled) => { void setGameProfileEnabled(enabled); }}
          />
        </PanelSection>
      ) : null}
      {profileMessage ? <SupportingText className="armada-note-error">{profileMessage}</SupportingText> : null}
      {profileEnabled && !switchingProfile ? (
        <PanelSection>
          {editingDefault ? (
            <>
              <SelectEdit
                label={t("compatibility.defaultProton")}
                value={globalTool || activeGlobalTool}
                options={toolOptions}
                onChange={onSelectGlobalDefault}
                disabled={switchingDefault}
                placeholder={globalToolMissing ? t("compatibility.chooseProton") : undefined}
                description={globalToolMissing
                  ? <span className="armada-note-error">{t("compatibility.missingTool", { tool: globalTool })}</span>
                  : activeGlobalTool === FOLLOW_STEAM_COMPAT ? t("compatibility.followSteamDescription") : undefined}
              />
              {retryDefault !== null ? <ButtonRow layout="below" disabled={switchingDefault} onClick={() => { void onSelectGlobalDefault(retryDefault); }}>{t("common.retry")}</ButtonRow> : null}
              {activeGlobalTool !== FOLLOW_STEAM_COMPAT ? (
                <ToggleRow
                  label={t("compatibility.applyToNewGames")}
                  value={tweaks.global.autoApplyCompat !== false}
                  onChange={(enabled) => {
                    setAutoApplyCompat(enabled);
                    patchSettings({ autoApplyCompat: enabled });
                  }}
                />
              ) : null}
              <SelectEdit label={t("compatibility.gameResolution")} value={defaultResolution} options={resolutionOptions.map((option) => ({ ...option, label: translateLabel(option.label) }))} onChange={setSteamDefaultResolution} />
            </>
          ) : (
            <>
              <SelectEdit label={t("compatibility.tool")} value={currentTool} options={perGameToolOptions} onChange={onSelectPerGameTool} />
              <SelectEdit label={t("compatibility.gameResolution")} value={resolution} options={resolutionOptions.map((option) => ({
                ...option,
                label: option.data === "Default"
                  ? t("gameSettings.inherit", { value: defaultResolutionLabel })
                  : translateLabel(option.label),
              }))} onChange={setSteamResolution} />
            </>
          )}
          {resolutionMessage ? <Field className="armada-note-error" label={t("common.status")} description={resolutionMessage} bottomSeparator="none" /> : null}
          <SelectEdit label={t("compatibility.fexPreset")} value={inheritedFex ? "" : fexValue} options={fexOptions} onChange={onSelectFex} />
          {isCustom ? (
            <Subsection title={t("compatibility.fexSettings")}>
              {fexKnobs.map((knob) => (
                <ToggleRow key={knob.key} label={translateLabel(knob.label)} value={fexConfig[knob.key] === "1"} onChange={(value) => setKnob(knob.key, value)} />
              ))}
            </Subsection>
          ) : null}
          <Subsection title={t("profiles.cpuSettings")}>{cpuControls}</Subsection>
          <Subsection title={t("compatibility.environment")}>{envControls}</Subsection>
          <Subsection title={t("compatibility.advanced")}>
            <ButtonRow layout="below" onClick={openAdvanced}>{t("compatibility.advancedSettings")}</ButtonRow>
            {editingDefault ? (
              <ButtonRow layout="below" disabled={!!resetting || changingProfile} onClick={confirmResetAllGames}>
                {resettingAll ? t("common.resetting") : t("compatibility.resetAllGames")}
              </ButtonRow>
            ) : (
              <ButtonRow layout="below" disabled={!!resetting || changingProfile} onClick={confirmResetGame}>
                {resettingGame ? t("common.resetting") : t("common.resetToDefault")}
              </ButtonRow>
            )}
          </Subsection>
        </PanelSection>
      ) : null}
    </>
  );
}
