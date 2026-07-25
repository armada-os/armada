import assert from "node:assert/strict";
import test from "node:test";
import {
  brightnessRequestStoredWhileHdrOff,
  brightnessRequestConverged,
  brightnessRuntimeReady,
  hdrRequestConverged,
  shouldShowHdrBrightnessControl,
} from "../src/lib/hdrVerification.ts";

function runtime(overrides = {}) {
  return {
    available: true,
    display: ":0",
    supportsHdr: true,
    enabled: true,
    outputFeedback: true,
    sdrContentBrightnessNits: 400,
    reason: "ok",
    ...overrides,
  };
}

test("HDR on converges only when Steam, Gamescope, and output feedback agree", () => {
  assert.equal(hdrRequestConverged(true, true, runtime()), true);
  assert.equal(hdrRequestConverged(true, false, runtime()), false);
  assert.equal(hdrRequestConverged(true, true, runtime({ enabled: false })), false);
  assert.equal(hdrRequestConverged(true, true, runtime({ outputFeedback: false })), false);
  assert.equal(hdrRequestConverged(true, true, runtime({ supportsHdr: false })), false);
  assert.equal(hdrRequestConverged(true, true, undefined), false);
});

test("HDR off requires real Gamescope off feedback, not only a false Steam setting", () => {
  assert.equal(hdrRequestConverged(false, false, runtime({
    enabled: false,
    outputFeedback: false,
  })), true);
  assert.equal(hdrRequestConverged(false, false, runtime({
    enabled: true,
    outputFeedback: false,
  })), false);
  assert.equal(hdrRequestConverged(false, false, runtime({
    enabled: false,
    outputFeedback: true,
  })), false);
});

test("SDR-on-HDR brightness is visible only while HDR is verified active", () => {
  assert.equal(shouldShowHdrBrightnessControl(true, runtime()), true);
  assert.equal(shouldShowHdrBrightnessControl(false, runtime({
    enabled: false,
    outputFeedback: false,
  })), false);
  assert.equal(shouldShowHdrBrightnessControl(true, runtime({ outputFeedback: false })), false);
  assert.equal(shouldShowHdrBrightnessControl(true, undefined), false);
});

test("brightness changes require matching Steam readback and a moved compositor atom", () => {
  const input = {
    requested: 0.5,
    expectedNits: 350,
    readback: 0.5,
    beforeReadback: 0.25,
    beforeRuntime: runtime({ sdrContentBrightnessNits: 200 }),
    runtime: runtime({ sdrContentBrightnessNits: 350 }),
  };
  assert.equal(brightnessRequestConverged(input), true);
  assert.equal(brightnessRequestConverged({
    ...input,
    readback: 0.25,
  }), false);
  assert.equal(brightnessRequestConverged({
    ...input,
    runtime: runtime({ sdrContentBrightnessNits: 200 }),
  }), false);
  assert.equal(brightnessRequestConverged({
    ...input,
    runtime: runtime({ sdrContentBrightnessNits: 349.5 }),
  }), false);
  assert.equal(brightnessRequestConverged({
    ...input,
    runtime: runtime({ enabled: false, sdrContentBrightnessNits: 350 }),
  }), false);
  assert.equal(brightnessRequestConverged({
    ...input,
    runtime: runtime({ outputFeedback: false, sdrContentBrightnessNits: 350 }),
  }), false);
});

test("brightness baseline is ready only with active HDR output feedback and nits", () => {
  assert.equal(brightnessRuntimeReady(runtime()), true);
  assert.equal(brightnessRuntimeReady(runtime({ outputFeedback: false })), false);
  assert.equal(brightnessRuntimeReady(runtime({ enabled: false })), false);
  assert.equal(brightnessRuntimeReady(runtime({ sdrContentBrightnessNits: null })), false);
  assert.equal(brightnessRuntimeReady(undefined), false);
});

test("brightness preference can be stored while real HDR output remains off", () => {
  const offRuntime = runtime({ enabled: false, outputFeedback: false });
  assert.equal(brightnessRequestStoredWhileHdrOff(0.5, 0.5, false, offRuntime), true);
  assert.equal(brightnessRequestStoredWhileHdrOff(0.5, 0.25, false, offRuntime), false);
  assert.equal(brightnessRequestStoredWhileHdrOff(0.5, 0.5, true, offRuntime), false);
  assert.equal(brightnessRequestStoredWhileHdrOff(
    0.5,
    0.5,
    false,
    runtime({ enabled: false, outputFeedback: true }),
  ), false);
});

test("brightness no-op accepts stable compositor nits after exact readback", () => {
  assert.equal(brightnessRequestConverged({
    requested: 0.5,
    expectedNits: 350,
    readback: 0.5,
    beforeReadback: 0.5,
    beforeRuntime: runtime({ sdrContentBrightnessNits: 350 }),
    runtime: runtime({ sdrContentBrightnessNits: 350 }),
  }), true);
});
