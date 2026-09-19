import assert from "node:assert/strict";
import test from "node:test";

import { centerOverlay } from "../src/lib/mcuCalibration.ts";

test("centerOverlay places left-stick directions in physical positions", () => {
  const overlay = centerOverlay("left", ["up", "left"], "down-right");
  assert.deepEqual(overlay.dots, [true, false, false, false, false, false, true, false]);
  assert.equal(overlay.pendingIndex, 3);
});

test("centerOverlay corrects the right stick's physical orientation", () => {
  const overlay = centerOverlay("right", ["up", "left"], "left");
  assert.deepEqual(overlay.dots, [false, false, true, false, true, false, false, false]);
  assert.equal(overlay.pendingIndex, 2);
});

test("centerOverlay ignores unknown direction names", () => {
  const overlay = centerOverlay("right", ["north"], "southwest");
  assert.deepEqual(overlay.dots, Array(8).fill(false));
  assert.equal(overlay.pendingIndex, null);
});
