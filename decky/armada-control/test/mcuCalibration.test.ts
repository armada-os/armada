import assert from "node:assert/strict";
import test from "node:test";
import { centerOverlay } from "../src/lib/mcuCalibration.ts";

test("centerOverlay renders physical directions from either stick without remapping", () => {
  const overlay = centerOverlay(["up", "left"], "down-right");
  assert.deepEqual(overlay.dots, [true, false, false, false, false, false, true, false]);
  assert.equal(overlay.pendingIndex, 3);
});

test("centerOverlay ignores unknown directions and preserves the north index zero", () => {
  assert.equal(centerOverlay([], "up").pendingIndex, 0);
  assert.deepEqual(centerOverlay(["north"], "southwest"), { dots: Array(8).fill(false), pendingIndex: null });
});
