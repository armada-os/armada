import assert from "node:assert/strict";
import test from "node:test";
import { centerOverlay, rangeProgress } from "../src/lib/mcuCalibration.ts";
import { normalizedValue } from "../src/lib/calibration.ts";
import type { CalibrationState } from "../src/types.ts";

test("centre display uses the measured physical reference without altering normal display", () => {
  const state = { controls: { right_x: { value: -190, min: -1024, max: 1024 } } } as unknown as CalibrationState;
  assert.equal(normalizedValue(state, "right_x", -190), 0);
  assert.equal(normalizedValue(state, "right_x"), -190 / 1024);
  state.controls.right_x.value = 410;
  assert.equal(normalizedValue(state, "right_x", -190), 600 / 1024);
});

test("centerOverlay renders physical directions from either stick without remapping", () => {
  const overlay = centerOverlay(["up", "left"], "down-right");
  assert.deepEqual(overlay.dots, [true, false, false, false, false, false, true, false]);
  assert.equal(overlay.pendingIndex, 3);
});

test("centerOverlay ignores unknown directions and preserves the north index zero", () => {
  assert.equal(centerOverlay([], "up").pendingIndex, 0);
  assert.deepEqual(centerOverlay(["north"], "southwest"), { dots: Array(8).fill(false), pendingIndex: null });
});

test("range progress cannot complete while raw sectors are still missing", () => {
  const progress = { turns: 4.2, coveredHeadings: 8, coveredSectors: 36 };
  assert.equal(rangeProgress(progress), 0.5);
  assert.equal(rangeProgress({ ...progress, coveredSectors: 72 }), 1);
  assert.equal(rangeProgress({ ...progress, coveredSectors: 72, turns: 2 }), 0.5);
  assert.equal(rangeProgress({ ...progress, coveredSectors: 72, coveredHeadings: 4 }), 0.5);
});
