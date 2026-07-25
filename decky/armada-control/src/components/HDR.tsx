import { Field, SliderField, ToggleField } from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import {
  getHdrEnabled,
  getHdrSdrContentBrightness,
  HDR_SDR_CONTENT_BRIGHTNESS_DEFAULT,
  isHdrSdrContentBrightnessAvailable,
  isHdrSettingAvailable,
  setHdrEnabled,
  setHdrSdrContentBrightness,
} from "../lib/steamSettings";
import {
  HDR_SDR_BRIGHTNESS_MAX_NITS,
  HDR_SDR_BRIGHTNESS_MIN_NITS,
  hdrSdrBrightnessNitsToNormalized,
  hdrSdrBrightnessNormalizedToNits,
} from "../lib/hdrBrightness";
import { shouldShowHdrBrightnessControl } from "../lib/hdrVerification";
import { hdrRuntimeState } from "../lib/hdrRuntimeState";

const BRIGHTNESS_WRITE_THROTTLE_MS = 100;
const BRIGHTNESS_READBACK_GRACE_MS = 750;

function useHdrRuntimeSnapshot() {
  const [snapshot, setSnapshot] = useState(hdrRuntimeState.getSnapshot);
  useEffect(() => hdrRuntimeState.subscribe(setSnapshot), []);
  return snapshot;
}

function useHdrToggleState() {
  const [enabled, setEnabled] = useState(getHdrEnabled);
  const [available, setAvailable] = useState(isHdrSettingAvailable);
  const [changing, setChanging] = useState(false);
  const [actionError, setActionError] = useState("");
  const [runtimeProblem, setRuntimeProblem] = useState("");
  const changingRef = useRef(false);
  const runtimeSnapshot = useHdrRuntimeSnapshot();

  useEffect(() => {
    if (!runtimeSnapshot.initialized || changingRef.current) return;
    const nextAvailable = isHdrSettingAvailable();
    const steamEnabled = getHdrEnabled();
    setAvailable(nextAvailable);

    const runtime = runtimeSnapshot.runtime;
    if (!runtime) {
      setEnabled(steamEnabled);
      setRuntimeProblem(`Gamescope HDR readback failed: ${runtimeSnapshot.error || "unknown"}`);
      return;
    }
    const outputAgrees = runtime.available &&
      runtime.supportsHdr &&
      runtime.enabled === runtime.outputFeedback;
    const fullyAgrees = outputAgrees && steamEnabled === runtime.enabled;
    if (fullyAgrees) {
      setEnabled(runtime.enabled);
      setRuntimeProblem("");
    } else if (!runtime.available) {
      setEnabled(steamEnabled);
      setRuntimeProblem(`Gamescope HDR readback unavailable: ${runtime.reason || "unknown"}`);
    } else if (!runtime.supportsHdr) {
      setEnabled(false);
      setRuntimeProblem("Gamescope does not report HDR support for the active display.");
    } else {
      // The switch reflects confirmed output, never a Steam-only value.
      setEnabled(runtime.enabled && runtime.outputFeedback);
      setRuntimeProblem(
        `HDR state mismatch: Steam=${Number(steamEnabled)}, ` +
        `Gamescope=${Number(runtime.enabled)}, feedback=${Number(runtime.outputFeedback)}`,
      );
    }
  }, [runtimeSnapshot]);

  const onChange = async (value: boolean) => {
    const previous = enabled;
    changingRef.current = true;
    setChanging(true);
    setEnabled(value);
    setActionError("");
    setRuntimeProblem("");
    try {
      setEnabled(await setHdrEnabled(value));
    } catch (nextError) {
      setEnabled(previous);
      setActionError(String(nextError));
    } finally {
      changingRef.current = false;
      setChanging(false);
      void hdrRuntimeState.refresh();
    }
  };

  return {
    actionError,
    available,
    changing,
    enabled,
    onChange,
    runtimeProblem,
  };
}

function useHdrBrightnessState() {
  const [brightness, setBrightness] = useState(
    () => getHdrSdrContentBrightness() ?? HDR_SDR_CONTENT_BRIGHTNESS_DEFAULT,
  );
  const [available, setAvailable] = useState(isHdrSdrContentBrightnessAvailable);
  const [hdrEnabled, setHdrEnabled] = useState(false);
  const [error, setError] = useState("");
  const timerRef = useRef<number | undefined>(undefined);
  const pendingRef = useRef<number | undefined>(undefined);
  const readbackAfterRef = useRef(0);
  const requestVersionRef = useRef(0);
  const inFlightRef = useRef(false);
  const mountedRef = useRef(true);
  const runtimeSnapshot = useHdrRuntimeSnapshot();

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (timerRef.current !== undefined) {
        window.clearTimeout(timerRef.current);
        timerRef.current = undefined;
      }
      const pending = pendingRef.current;
      if (pending !== undefined && !inFlightRef.current) {
        pendingRef.current = undefined;
        void setHdrSdrContentBrightness(pending).catch(() => {
          // The component is unmounting, so there is nowhere useful to report this.
        });
      }
    };
  }, []);

  useEffect(() => {
    if (!runtimeSnapshot.initialized || !mountedRef.current) return;
    const nextAvailable = isHdrSdrContentBrightnessAvailable();
    setAvailable(nextAvailable);
    if (nextAvailable && Date.now() >= readbackAfterRef.current) {
      const nextBrightness = getHdrSdrContentBrightness();
      if (nextBrightness !== undefined) setBrightness(nextBrightness);
    }
    setHdrEnabled(shouldShowHdrBrightnessControl(
      getHdrEnabled(),
      runtimeSnapshot.runtime,
    ));
  }, [runtimeSnapshot]);

  const drainPendingWrites = async () => {
    timerRef.current = undefined;
    if (inFlightRef.current) return;
    inFlightRef.current = true;

    try {
      while (pendingRef.current !== undefined) {
        const nextBrightness = pendingRef.current;
        pendingRef.current = undefined;
        const requestVersion = requestVersionRef.current;
        try {
          const appliedBrightness = await setHdrSdrContentBrightness(nextBrightness);
          if (mountedRef.current && requestVersion === requestVersionRef.current) {
            setBrightness(appliedBrightness);
            setError("");
          }
        } catch (nextError) {
          if (!mountedRef.current || requestVersion !== requestVersionRef.current) continue;
          const currentBrightness = getHdrSdrContentBrightness();
          if (currentBrightness !== undefined) setBrightness(currentBrightness);
          setError(String(nextError));
        } finally {
          void hdrRuntimeState.refresh();
        }
      }
    } finally {
      inFlightRef.current = false;
      if (pendingRef.current !== undefined && mountedRef.current) {
        timerRef.current = window.setTimeout(
          () => void drainPendingWrites(),
          BRIGHTNESS_WRITE_THROTTLE_MS,
        );
      }
    }
  };

  const onChange = (nits: number) => {
    if (!available || !Number.isFinite(nits)) return;
    const nextBrightness = hdrSdrBrightnessNitsToNormalized(nits);
    setBrightness(nextBrightness);
    setError("");
    readbackAfterRef.current = Date.now() + BRIGHTNESS_READBACK_GRACE_MS;
    pendingRef.current = nextBrightness;
    requestVersionRef.current += 1;
    if (timerRef.current === undefined && !inFlightRef.current) {
      timerRef.current = window.setTimeout(
        () => void drainPendingWrites(),
        BRIGHTNESS_WRITE_THROTTLE_MS,
      );
    }
  };

  return { available, brightness, error, hdrEnabled, onChange };
}

export function HDRToggleControl() {
  const {
    actionError,
    available,
    changing,
    enabled,
    onChange,
    runtimeProblem,
  } = useHdrToggleState();
  const description = changing
    ? "Applying the HDR setting and verifying Gamescope output."
    : undefined;
  return (
    <>
      <ToggleField
        label="Enable HDR"
        description={description}
        checked={enabled}
        disabled={!available || changing}
        onChange={onChange}
      />
      {!available && (
        <Field
          label="Steam HDR control unavailable"
          description="Steam has not exposed the Game Mode HDR setting in this session."
        />
      )}
      {actionError && <Field label="Could not change HDR" description={actionError} />}
      {!changing && runtimeProblem && (
        <Field label="HDR output is not verified" description={runtimeProblem} />
      )}
    </>
  );
}

export function HDRBrightnessControl() {
  const { available, brightness, error, hdrEnabled, onChange } = useHdrBrightnessState();
  if (!hdrEnabled) return null;
  return (
    <>
      <SliderField
        label="SDR content brightness (on HDR)"
        description="Adjust how bright SDR content appears while HDR output is enabled."
        value={Math.round(hdrSdrBrightnessNormalizedToNits(brightness))}
        min={HDR_SDR_BRIGHTNESS_MIN_NITS}
        max={HDR_SDR_BRIGHTNESS_MAX_NITS}
        step={1}
        minimumDpadGranularity={1}
        resetValue={Math.round(hdrSdrBrightnessNormalizedToNits(
          HDR_SDR_CONTENT_BRIGHTNESS_DEFAULT,
        ))}
        valueSuffix=" nits"
        showValue
        disabled={!available}
        onChange={onChange}
      />
      {!available && (
        <Field
          label="SDR-on-HDR brightness unavailable"
          description="Steam has not exposed the Game Mode SDR brightness setting in this session."
        />
      )}
      {error && <Field label="Could not change SDR-on-HDR brightness" description={error} />}
    </>
  );
}
