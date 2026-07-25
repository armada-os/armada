import assert from "node:assert/strict";
import test from "node:test";
import {
  hdrSdrBrightnessNitsToNormalized,
  hdrSdrBrightnessNormalizedToNits,
} from "../src/lib/hdrBrightness.ts";

test("maps Steam's normalized SDR-on-HDR setting to compositor nits", () => {
  assert.equal(hdrSdrBrightnessNormalizedToNits(0), 80);
  assert.equal(hdrSdrBrightnessNormalizedToNits(0.25), 185);
  assert.equal(hdrSdrBrightnessNormalizedToNits(0.5), 290);
  assert.equal(hdrSdrBrightnessNormalizedToNits(0.75), 395);
  assert.equal(hdrSdrBrightnessNormalizedToNits(1), 500);
});

test("round-trips and clamps SDR-on-HDR nits", () => {
  assert.equal(hdrSdrBrightnessNitsToNormalized(80), 0);
  assert.equal(hdrSdrBrightnessNitsToNormalized(290), 0.5);
  assert.equal(hdrSdrBrightnessNitsToNormalized(500), 1);
  assert.equal(hdrSdrBrightnessNitsToNormalized(20), 0);
  assert.equal(hdrSdrBrightnessNitsToNormalized(900), 1);
});
