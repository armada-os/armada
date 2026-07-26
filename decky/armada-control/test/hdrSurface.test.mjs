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
const qamPatchSource = readFileSync(
  new URL("../src/lib/performanceHdrQamPatch.tsx", import.meta.url),
  "utf8",
);
const autoHdrVerificationSource = readFileSync(
  new URL("../src/lib/autoHdrVerification.ts", import.meta.url),
  "utf8",
);

test("Armada Control does not import or mount fallback HDR controls", () => {
  assert.doesNotMatch(settingsSource, /components\/HDR/);
  assert.doesNotMatch(settingsSource, /<HDR\b/);
  assert.doesNotMatch(hdrSource, /export function HDR\(/);
  assert.doesNotMatch(contentSource, /config\.hdrCapable/);
});

test("Steam Display retains native HDR and SDR brightness controls", () => {
  assert.match(routePatchSource, /<HDRToggleControl\s*\/>/);
  assert.match(routePatchSource, /<AutoHDRToggleControl\s*\/>/);
  assert.doesNotMatch(routePatchSource, /AutoHDRProfileControl/);
  assert.match(routePatchSource, /<HDRBrightnessControl\s*\/>/);
});

test("Performance QAM places the contextual AutoHDR toggle in the native tree", () => {
  assert.match(qamPatchSource, /AutoHDRQamToggleControl/);
  assert.doesNotMatch(qamPatchSource, /AutoHDRQamProfileControl/);
  assert.match(qamPatchSource, /injectPerformanceHdrControls/);
  assert.doesNotMatch(qamPatchSource, /HDRToggleControl/);
  assert.doesNotMatch(qamPatchSource, /HDRBrightnessControl/);
  assert.match(hdrSource, /export function AutoHDRQamToggleControl/);
  assert.doesNotMatch(hdrSource, /AutoHDRQamProfileControl/);
  assert.match(
    hdrSource,
    /target === "active"\s*\?\s*shouldKeepAutoHdrControlVisible\(getHdrEnabled\(\), runtime\)/,
  );
});

test("Performance QAM uses one root-owned bounded probe session", () => {
  assert.match(qamPatchSource, /MAX_PERFORMANCE_PROBES = 32/);
  assert.match(qamPatchSource, /createPerformanceProbeSession/);
  assert.match(qamPatchSource, /disposePerformanceProbeSession/);
  assert.match(qamPatchSource, /claimPerformanceHdrProbeOwner\(session, holder\)/);
  assert.match(
    qamPatchSource,
    /releasePerformanceHdrProbeOwner\(session, owned\.holder\)/,
  );
  assert.doesNotMatch(qamPatchSource, /advancedVerified|toggleSatisfied/);
});

test("contextual badge feedback contract remains fail-closed in Decky", () => {
  assert.match(
    autoHdrVerificationSource,
    /runtime\.outputFeedback === true/,
  );
  assert.match(
    hdrSource,
    /shouldKeepAutoHdrControlVisible\(getHdrEnabled\(\), runtime\)/,
  );
});

test("Performance QAM AutoHDR toggle uses the native row and icon contracts", () => {
  assert.match(
    hdrSource,
    /target === "active"\s*\?\s*<PanelSectionRow>\{toggle\}<\/PanelSectionRow>/,
  );
  assert.match(hdrSource, /icon=\{target === "active" \? <AutoHdrQamIcon \/> : undefined\}/);
  assert.match(hdrSource, /width="36"/);
  assert.match(hdrSource, /height="36"/);
  assert.match(hdrSource, /stroke="currentColor"/);
});

test("AutoHDR copy and toggle-only surface match the release contract", () => {
  assert.match(
    hdrSource,
    /Convert SDR games to HDR\. You may need to adjust in-game brightness for best results\./,
  );
  assert.doesNotMatch(hdrSource, /AutoHDR Profile/);
  assert.doesNotMatch(hdrSource, /label: "Eco"/);
  assert.doesNotMatch(hdrSource, /label: "Quality"/);
  assert.doesNotMatch(hdrSource, /label="Auto HDR/);
});

test("QAM preference display and writes share one coordinator scope snapshot", () => {
  assert.match(hdrSource, /preferences\?\.scope \?\? "global"/);
  assert.match(hdrSource, /preferences\?\.appId \?\? null/);
  assert.doesNotMatch(hdrSource, /currentSteamAutoHdrScope/);
});
