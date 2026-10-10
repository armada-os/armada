import { toaster } from "@decky/api";
import { ButtonItem, Field, PanelSection, showModal } from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { getVirtualTrackpads, resetVirtualTrackpads, setVirtualTrackpads } from "../backend";
import { SelectEdit, SliderEdit, ToggleRow } from "../components/widgets";
import { TrackpadShortcutModal } from "../components/TrackpadShortcutModal";
import { trackpadText as t } from "../lib/trackpadText";
import type { Config, EditableTrackpadsConfig } from "../types";

export function Trackpads({ config, setConfig }: {
  config: Config;
  setConfig: Dispatch<SetStateAction<Config | null>>;
}) {
  const timer = useRef<number | null>(null);
  const request = useRef(Promise.resolve());
  const pendingSaves = useRef(0);
  const editRevision = useRef(0);
  const latestPads = useRef(config.virtualTrackpads);
  latestPads.current = config.virtualTrackpads;
  const [resetting, setResetting] = useState(false);

  useEffect(() => () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      if (timer.current !== null || pendingSaves.current > 0) return;
      try {
        const latest = await getVirtualTrackpads();
        if (!cancelled && timer.current === null && pendingSaves.current === 0) {
          setConfig((current) => {
            if (!current || (
              current.virtualTrackpads.enabled === latest.enabled &&
              current.virtualTrackpads.blockTouchscreen === latest.blockTouchscreen &&
              current.virtualTrackpads.leftEnabled === latest.leftEnabled &&
              current.virtualTrackpads.rightEnabled === latest.rightEnabled &&
              current.virtualTrackpads.mode === latest.mode &&
              current.virtualTrackpads.screen === latest.screen &&
              current.virtualTrackpads.secondaryAvailable === latest.secondaryAvailable
            )) return current;
            return { ...current, virtualTrackpads: { ...current.virtualTrackpads, ...latest } };
          });
        }
      } catch (_) { /* Keep the last known settings if the service is unavailable. */ }
    };
    const interval = window.setInterval(refresh, 1500);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [setConfig]);

  const refreshAfterError = async (revision: number) => {
    if (editRevision.current !== revision) return;
    try {
      const confirmed = await getVirtualTrackpads();
      if (editRevision.current !== revision) return;
      latestPads.current = confirmed;
      setConfig((current) => current && editRevision.current === revision
        ? { ...current, virtualTrackpads: confirmed } : current);
    } catch (_) { /* Keep the draft if the server cannot confirm its state. */ }
  };

  const update = (change: Partial<EditableTrackpadsConfig>, immediate = false) => {
    const revision = ++editRevision.current;
    // A shortcut may toggle the feature while its settings dialog is open.
    // Save the edited buttons against the latest state, not the modal's snapshot.
    const next = { ...latestPads.current, ...change };
    latestPads.current = next;
    setConfig((current) => current ? { ...current, virtualTrackpads: next } : current);
    window.dispatchEvent(new Event("armada-trackpads-preview"));
    if (timer.current !== null) window.clearTimeout(timer.current);
    const save = () => {
      timer.current = null;
      const { supported: _supported, secondaryAvailable: _secondaryAvailable, ...payload } = next;
      pendingSaves.current += 1;
      request.current = request.current
        .catch(() => {})
        .then(async () => {
          const applied = await setVirtualTrackpads(payload);
          const { controllerType, ...trackpads } = applied;
          // Older acknowledgements must not overwrite a newer toggle or draft.
          if (editRevision.current !== revision) return;
          setConfig((current) => current ? {
            ...current,
            controllerType: controllerType || current.controllerType,
            virtualTrackpads: editRevision.current === revision
              ? { ...current.virtualTrackpads, ...trackpads, supported: true }
              : current.virtualTrackpads,
          } : current);
        })
        .catch(async (error) => {
          toaster.toast({ title: t("trackpads.saveError"), body: String(error) });
          await refreshAfterError(revision);
        })
        .finally(() => { pendingSaves.current -= 1; });
    };
    timer.current = window.setTimeout(save, immediate ? 0 : 300);
  };

  const resetDefaults = () => {
    if (resetting) return;
    const revision = ++editRevision.current;
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    setResetting(true);
    pendingSaves.current += 1;
    request.current = request.current
      .catch(() => {})
      .then(async () => {
        const applied = await resetVirtualTrackpads();
        const { controllerType, ...trackpads } = applied;
        if (editRevision.current !== revision) return;
        setConfig((current) => current ? {
          ...current,
          controllerType: controllerType || current.controllerType,
          virtualTrackpads: editRevision.current === revision
            ? { ...current.virtualTrackpads, ...trackpads, supported: true }
            : current.virtualTrackpads,
        } : current);
        window.dispatchEvent(new Event("armada-trackpads-preview"));
      })
      .catch(async (error) => {
        toaster.toast({ title: t("trackpads.saveError"), body: String(error) });
        await refreshAfterError(revision);
      })
      .finally(() => {
        pendingSaves.current -= 1;
        setResetting(false);
      });
  };

  if (!config.virtualTrackpads.supported) {
    return <Field label={t("trackpads.title")} description={t("trackpads.unsupported")} />;
  }
  const pads = config.virtualTrackpads;
  const screenMode = pads.mode === "halves" || pads.mode === "fullLeft" || pads.mode === "fullRight";
  const modeDescription = t(`trackpads.mode${pads.mode[0].toUpperCase()}${pads.mode.slice(1)}Description` as
    | "trackpads.modeSimpleDescription"
    | "trackpads.modeCornersDescription"
    | "trackpads.modeFloatingDescription"
    | "trackpads.modeHalvesDescription"
    | "trackpads.modeFullLeftDescription"
    | "trackpads.modeFullRightDescription");
  const deckControllerSelected = config.controllerType === "deck-uhid";
  const settingsDisabled = !pads.enabled || resetting;
  const controlsDisabled = settingsDisabled || screenMode;
  const visualDisabled = controlsDisabled;
  const centerDotDisabled = visualDisabled || pads.mode === "floating";
  return (
    <div className="armada-trackpads-tab">
      <PanelSection title={t("trackpads.title")}>
        <ToggleRow
          label={t("trackpads.master")}
          description={deckControllerSelected ? t("trackpads.masterDescription") : t("trackpads.selectDeckFirst")}
          value={pads.enabled}
          disabled={!deckControllerSelected || resetting}
          onChange={(enabled) => update(enabled && !pads.leftEnabled && !pads.rightEnabled
            ? { enabled, blockTouchscreen: false, leftEnabled: true, rightEnabled: true }
            : { enabled, ...(enabled ? { blockTouchscreen: false } : {}) }, true)}
        />
        <ToggleRow
          label={t("trackpads.blockTouchscreen")}
          description={t("trackpads.blockTouchscreenDescription")}
          value={pads.blockTouchscreen}
          disabled={resetting}
          onChange={(blockTouchscreen) => update(blockTouchscreen
            ? { blockTouchscreen, enabled: false }
            : { blockTouchscreen }, true)}
        />
        <ToggleRow
          label={t("trackpads.gameModeOnly")}
          description={t("trackpads.gameModeOnlyDescription")}
          value={pads.gameModeOnly}
          disabled={resetting}
          onChange={(gameModeOnly) => update({ gameModeOnly }, true)}
        />
        <SelectEdit
          label={t("trackpads.mode")}
          value={pads.mode}
          disabled={settingsDisabled}
          options={[
            { data: "simple", label: t("trackpads.modeSimple") },
            { data: "corners", label: t("trackpads.modeCorners") },
            { data: "floating", label: t("trackpads.modeFloating") },
            { data: "halves", label: t("trackpads.modeHalves") },
            { data: "fullLeft", label: t("trackpads.modeFullLeft") },
            { data: "fullRight", label: t("trackpads.modeFullRight") },
          ]}
          onChange={(mode) => update(mode === "fullLeft" || mode === "fullRight"
            ? { mode, leftEnabled: mode === "fullLeft", rightEnabled: mode === "fullRight" }
            : mode === "halves" || screenMode
              ? { mode, leftEnabled: true, rightEnabled: true }
              : { mode }, true)}
        />
        <div className="armada-trackpads-note">{modeDescription}</div>
        {screenMode && <div className="armada-trackpads-note">{t("trackpads.screenModeSettings")}</div>}
      </PanelSection>
      <PanelSection title={t("trackpads.shortcut")}>
        <ToggleRow
          label={t("trackpads.shortcutEnabled")}
          value={pads.shortcutEnabled}
          disabled={resetting}
          description={t("trackpads.shortcutDescription")}
          onChange={(shortcutEnabled) => update({ shortcutEnabled }, true)}
        />
        <ButtonItem
          layout="below"
          label={t("trackpads.shortcutButtons")}
          disabled={!pads.shortcutEnabled || resetting}
          onClick={() => showModal(<TrackpadShortcutModal
            initial={pads.shortcutButtons}
            onSave={(shortcutButtons) => update({ shortcutButtons }, true)}
          />)}
        >
          {pads.shortcutButtons.join(" + ")}
        </ButtonItem>
        <SelectEdit
          label={t("trackpads.shortcutActivation")}
          value={String(pads.shortcutHoldSeconds)}
          disabled={!pads.shortcutEnabled || resetting}
          options={[
            { data: "0", label: t("trackpads.shortcutImmediate") },
            { data: "3", label: t("trackpads.shortcutHold") },
          ]}
          onChange={(duration) => update({ shortcutHoldSeconds: duration === "0" ? 0 : 3 }, true)}
        />
      </PanelSection>
      <PanelSection title={t("trackpads.touchscreen")}>
        <SelectEdit
          label={t("trackpads.screen")}
          value={pads.screen}
          disabled={resetting || !pads.secondaryAvailable}
          options={[
            { data: "primary", label: t("trackpads.screenPrimary") },
            ...(pads.secondaryAvailable ? [{ data: "secondary", label: t("trackpads.screenSecondary") }] : []),
          ]}
          onChange={(screen) => update({ screen }, true)}
        />
        <div className="armada-trackpads-note">{t(pads.secondaryAvailable ? "trackpads.screenDescription" : "trackpads.screenSingle")}</div>
      </PanelSection>
      <PanelSection title={t("trackpads.zones")}>
        <ToggleRow
          label={t("trackpads.left")}
          description={!deckControllerSelected ? t("trackpads.selectDeckFirst") : undefined}
          value={pads.leftEnabled}
          disabled={!deckControllerSelected || controlsDisabled}
          onChange={(leftEnabled) => update({ leftEnabled }, true)}
        />
        <ToggleRow
          label={t("trackpads.right")}
          description={!deckControllerSelected ? t("trackpads.selectDeckFirst") : undefined}
          value={pads.rightEnabled}
          disabled={!deckControllerSelected || controlsDisabled}
          onChange={(rightEnabled) => update({ rightEnabled }, true)}
        />
        <SliderEdit
          label={t("trackpads.sharedSize")}
          value={pads.leftSize}
          min={15}
          max={80}
          step={1}
          disabled={controlsDisabled}
          onChange={(size) => update({ leftSize: size, rightSize: size })}
        />
        <SliderEdit
          label={t("trackpads.edgeGap")}
          value={pads.edgeGap}
          min={0}
          max={160}
          step={1}
          disabled={controlsDisabled || pads.mode === "floating"}
          onChange={(edgeGap) => update({ edgeGap })}
        />
      </PanelSection>
      <PanelSection title={t("trackpads.feedback")}>
        <ToggleRow
          label={t("trackpads.limitToBounds")}
          description={t("trackpads.limitToBoundsDescription")}
          value={pads.limitToBounds}
          disabled={controlsDisabled}
          onChange={(limitToBounds) => update({ limitToBounds }, true)}
        />
        <SliderEdit
          label={t("trackpads.hapticStrength")}
          value={pads.hapticStrength}
          min={0}
          max={100}
          step={5}
          disabled={controlsDisabled}
          onChange={(hapticStrength) => update({ hapticStrength })}
        />
      </PanelSection>
      <PanelSection title={t("trackpads.appearance")}>
        <ToggleRow
          label={t("trackpads.autoHide")}
          value={pads.autoHide}
          disabled={visualDisabled}
          onChange={(autoHide) => update({ autoHide }, true)}
        />
        <SliderEdit
          label={t("trackpads.hideDelay")}
          value={pads.hideDelay}
          min={1}
          max={5}
          step={1}
          disabled={visualDisabled || !pads.autoHide}
          onChange={(hideDelay) => update({ hideDelay })}
        />
        <SliderEdit
          label={t("trackpads.borderOpacity")}
          value={pads.borderOpacity}
          min={0}
          max={50}
          step={5}
          disabled={visualDisabled}
          onChange={(borderOpacity) => update({ borderOpacity })}
        />
        <SliderEdit
          label={t("trackpads.borderWidth")}
          value={pads.borderWidth}
          min={1}
          max={10}
          step={1}
          disabled={visualDisabled}
          onChange={(borderWidth) => update({ borderWidth })}
        />
        <SliderEdit
          label={t("trackpads.borderRadius")}
          value={pads.borderRadius}
          min={0}
          max={100}
          step={1}
          disabled={visualDisabled}
          onChange={(borderRadius) => update({ borderRadius })}
        />
        <SelectEdit
          label={t("trackpads.backgroundStyle")}
          value={pads.backgroundStyle}
          disabled={visualDisabled}
          options={[
            { data: "dots", label: t("trackpads.backgroundDots") },
            { data: "solid", label: t("trackpads.backgroundSolid") },
            { data: "none", label: t("trackpads.backgroundNone") },
          ]}
          onChange={(backgroundStyle) => update({ backgroundStyle }, true)}
        />
        <SliderEdit
          label={t("trackpads.backgroundOpacity")}
          value={pads.backgroundOpacity}
          min={0}
          max={50}
          step={5}
          disabled={visualDisabled || pads.backgroundStyle === "none"}
          onChange={(backgroundOpacity) => update({ backgroundOpacity })}
        />
        <SliderEdit
          label={t("trackpads.dotSize")}
          value={pads.dotSize}
          min={1}
          max={6}
          step={1}
          disabled={visualDisabled || pads.backgroundStyle !== "dots"}
          onChange={(dotSize) => update({ dotSize })}
        />
        <SliderEdit
          label={t("trackpads.dotGap")}
          value={pads.dotGap}
          min={2}
          max={24}
          step={1}
          disabled={visualDisabled || pads.backgroundStyle !== "dots"}
          onChange={(dotGap) => update({ dotGap })}
        />
      </PanelSection>
      <PanelSection title={t("trackpads.centerIndicator")}>
        <ToggleRow
          label={t("trackpads.centerDot")}
          description={t("trackpads.centerDotDescription")}
          value={pads.centerDotEnabled}
          disabled={centerDotDisabled}
          onChange={(centerDotEnabled) => update({ centerDotEnabled }, true)}
        />
        <SliderEdit
          label={t("trackpads.centerDotSize")}
          value={pads.centerDotSize}
          min={1}
          max={32}
          step={1}
          disabled={centerDotDisabled || !pads.centerDotEnabled}
          onChange={(centerDotSize) => update({ centerDotSize })}
        />
        <SliderEdit
          label={t("trackpads.centerDotOpacity")}
          value={pads.centerDotOpacity}
          min={0}
          max={50}
          step={5}
          disabled={centerDotDisabled || !pads.centerDotEnabled}
          onChange={(centerDotOpacity) => update({ centerDotOpacity })}
        />
      </PanelSection>
      <PanelSection>
        <ButtonItem layout="below" onClick={resetDefaults} disabled={resetting}>
          {t("trackpads.resetDefaults")}
        </ButtonItem>
        <div className="armada-trackpads-note">{t("trackpads.resetDefaultsDescription")}</div>
      </PanelSection>
    </div>
  );
}
