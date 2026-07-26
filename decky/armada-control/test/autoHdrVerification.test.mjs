import assert from "node:assert/strict";
import test from "node:test";
import {
  shouldKeepAutoHdrControlVisible,
  shouldShowAutoHdrControl,
} from "../src/lib/autoHdrVerification.ts";
import { hasHdrControlCapability } from "../src/lib/hdrCapability.ts";

function runtime(overrides = {}) {
  return {
    available: true,
    display: ":0",
    displayIsExternal: false,
    supportsHdr: true,
    enabled: true,
    outputFeedback: true,
    sdrContentBrightnessNits: 203,
    autoHdrSupported: true,
    autoHdrEnabled: false,
    autoHdrSdrNits: 203,
    autoHdrTargetNits: 650,
    autoHdrSupportedModes: 2,
    autoHdrModeProtocolPresent: true,
    autoHdrModeProtocol: true,
    autoHdrMode: 1,
    autoHdrEffectiveMode: 0,
    reason: "ok",
    ...overrides,
  };
}

test("Auto HDR appears only for verified native HDR output and compositor support", () => {
  assert.equal(shouldShowAutoHdrControl(true, runtime()), true);
  assert.equal(shouldShowAutoHdrControl(false, runtime()), false);
  assert.equal(shouldShowAutoHdrControl(true, runtime({ enabled: false })), false);
  assert.equal(shouldShowAutoHdrControl(true, runtime({ outputFeedback: false })), false);
  assert.equal(shouldShowAutoHdrControl(true, runtime({ autoHdrSupported: false })), false);
  assert.equal(shouldShowAutoHdrControl(true, runtime({ autoHdrModeProtocol: false })), false);
  assert.equal(shouldShowAutoHdrControl(true, runtime({ autoHdrSupportedModes: 1 })), false);
  assert.equal(shouldShowAutoHdrControl(true, runtime({ displayIsExternal: true })), false);
  assert.equal(shouldShowAutoHdrControl(true, runtime({ displayIsExternal: null })), false);
  assert.equal(shouldShowAutoHdrControl(true, undefined), false);
});

test("inactive Auto HDR stays hidden outside the exact predicate", () => {
  assert.equal(shouldKeepAutoHdrControlVisible(true, runtime({ outputFeedback: false })), false);
  assert.equal(shouldKeepAutoHdrControlVisible(true, runtime({ displayIsExternal: true })), false);
  assert.equal(shouldKeepAutoHdrControlVisible(true, runtime({ autoHdrSupported: false })), false);
});

test("active Auto HDR remains reachable during a transient state for disabling", () => {
  assert.equal(shouldKeepAutoHdrControlVisible(
    true,
    runtime({ outputFeedback: false, autoHdrEnabled: true }),
  ), true);
  assert.equal(shouldKeepAutoHdrControlVisible(
    false,
    runtime({ enabled: false, outputFeedback: false, autoHdrEnabled: true }),
  ), false);
});

test("Display controls qualify through immutable policy or verified live support", () => {
  assert.equal(hasHdrControlCapability({ hdrCapable: true }, undefined), true);
  assert.equal(hasHdrControlCapability(undefined, runtime()), true);
  assert.equal(hasHdrControlCapability(
    { hdrCapable: false },
    runtime({ available: false }),
  ), false);
});
