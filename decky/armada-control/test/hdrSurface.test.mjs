import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const settingsSource = readFileSync(
  new URL("../src/tabs/Settings.tsx", import.meta.url),
  "utf8",
);
const hdrSource = readFileSync(
  new URL("../src/components/HDR.tsx", import.meta.url),
  "utf8",
);
const contentSource = readFileSync(
  new URL("../src/Content.tsx", import.meta.url),
  "utf8",
);
const routePatchSource = readFileSync(
  new URL("../src/lib/displayHdrRoutePatch.tsx", import.meta.url),
  "utf8",
);

test("Armada Control does not import or mount fallback HDR controls", () => {
  assert.doesNotMatch(settingsSource, /components\/HDR/);
  assert.doesNotMatch(settingsSource, /<HDR\b/);
  assert.doesNotMatch(hdrSource, /export function HDR\(/);
  assert.doesNotMatch(contentSource, /config\.hdrCapable/);
});

test("Steam Display injection remains the sole HDR control surface", () => {
  assert.match(routePatchSource, /<HDRToggleControl\s*\/>/);
  assert.match(routePatchSource, /<HDRBrightnessControl\s*\/>/);
});
