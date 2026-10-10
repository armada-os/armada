import assert from "node:assert/strict";
import test from "node:test";
import { centerOverlay, rangeProgress } from "../src/lib/mcuCalibration.ts";

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
