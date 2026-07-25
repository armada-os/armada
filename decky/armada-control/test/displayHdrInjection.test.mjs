import assert from "node:assert/strict";
import test from "node:test";
import {
  ARMADA_HDR_INJECTION_MARKER,
  findAdvancedDisplayComponent,
  findDisplaySettingsContentComponent,
  injectAdvancedDisplayHdrControls,
} from "../src/lib/displayHdrInjection.ts";
import { RouteRenderPatchRegistry } from "../src/lib/displayHdrRoutePatchLifecycle.ts";
import {
  SYSTEM_PERF_STORE_BOOTSTRAP_TIMEOUT_MS,
  isSystemPerfStoreReady,
  shouldKeepSystemPerfStoreBootstrap,
} from "../src/lib/systemPerfStoreBootstrap.ts";

function AdvancedDisplaySection() {
  return "#Settings_Display_Advanced_Header";
}

function NativeHdrToggle() {
  return "#Settings_HDR_Enable gamescope_hdr_enabled";
}

function NativeHdrBrightness() {
  return "#Settings_HDR_SDRContentBrightness";
}

function OtherControl() {
  return null;
}

function DisplayContent() {
  return null;
}

function element(type, props = {}) {
  return { type, props };
}

function advancedOutput(childrenOverride) {
  const children = childrenOverride ?? [
    element(OtherControl),
    element(OtherControl),
    element(OtherControl),
    element(OtherControl),
    element(NativeHdrToggle, { bAdvanced: true }),
    element(NativeHdrBrightness),
    element(OtherControl),
    element(OtherControl),
  ];
  return element(OtherControl, { label: "Advanced", children });
}

test("finds exactly one Display Advanced component through nested React children", () => {
  const advanced = element(AdvancedDisplaySection);
  const tree = element(OtherControl, {
    children: [false, element(OtherControl, { children: advanced })],
  });
  assert.equal(findAdvancedDisplayComponent(tree), advanced);
});

test("finds Display content only through the exact Settings route entry", () => {
  const display = element(DisplayContent);
  const tree = element(OtherControl, {
    pages: [
      { route: "/settings/audio", content: element(OtherControl) },
      { route: "/settings/display", content: display },
    ],
  });
  assert.equal(findDisplaySettingsContentComponent(tree), display);
  assert.equal(findDisplaySettingsContentComponent(element(OtherControl, {
    pages: [{ route: "/settings/displays", content: display }],
  })), undefined);
});

test("fails closed when the Display route content is ambiguous", () => {
  const tree = element(OtherControl, {
    pages: [
      { route: "/settings/display", content: element(DisplayContent) },
      { route: "/settings/display", content: element(DisplayContent) },
    ],
  });
  assert.equal(findDisplaySettingsContentComponent(tree), undefined);
});

test("fails closed when the Advanced component fingerprint is ambiguous", () => {
  const tree = element(OtherControl, {
    children: [element(AdvancedDisplaySection), element(AdvancedDisplaySection)],
  });
  assert.equal(findAdvancedDisplayComponent(tree), undefined);
});

test("replaces only the adjacent native HDR placeholders without mutating Steam's tree", () => {
  const original = advancedOutput();
  const toggle = element(OtherControl, { [ARMADA_HDR_INJECTION_MARKER]: "toggle" });
  const brightness = element(OtherControl, { [ARMADA_HDR_INJECTION_MARKER]: "brightness" });
  const result = injectAdvancedDisplayHdrControls(original, toggle, brightness);

  assert.equal(result.status, "injected");
  assert.notEqual(result.tree, original);
  assert.notEqual(result.tree.props.children, original.props.children);
  assert.equal(result.tree.props.children[4], toggle);
  assert.equal(result.tree.props.children[5], brightness);
  assert.equal(original.props.children[4].type, NativeHdrToggle);
  assert.equal(original.props.children[5].type, NativeHdrBrightness);
});

test("passes the native brightness placeholder to a cold-store bootstrap replacement", () => {
  const original = advancedOutput();
  const nativeBrightness = original.props.children[5];
  let received;
  const replacement = element(OtherControl, { bootstrap: nativeBrightness });
  const result = injectAdvancedDisplayHdrControls(
    original,
    element(OtherControl),
    (nativeControl) => {
      received = nativeControl;
      return replacement;
    },
  );

  assert.equal(result.status, "injected");
  assert.equal(received, nativeBrightness);
  assert.equal(result.tree.props.children[5], replacement);
  assert.equal(original.props.children[5], nativeBrightness);
});

test("is idempotent when both Armada controls are already adjacent", () => {
  const toggle = element(OtherControl, { [ARMADA_HDR_INJECTION_MARKER]: "toggle" });
  const brightness = element(OtherControl, { [ARMADA_HDR_INJECTION_MARKER]: "brightness" });
  const once = injectAdvancedDisplayHdrControls(advancedOutput(), toggle, brightness);
  const twice = injectAdvancedDisplayHdrControls(once.tree, toggle, brightness);

  assert.equal(twice.status, "already-injected");
  assert.equal(twice.tree, once.tree);
});

test("fails closed when Valve reorders the native HDR placeholders", () => {
  const children = advancedOutput().props.children.slice();
  [children[5], children[6]] = [children[6], children[5]];
  const result = injectAdvancedDisplayHdrControls(
    advancedOutput(children),
    element(OtherControl),
    element(OtherControl),
  );
  assert.equal(result.status, "fingerprint-mismatch");
});

test("fails closed on a partial prior injection", () => {
  const children = advancedOutput().props.children.slice();
  children[4] = element(OtherControl, { [ARMADA_HDR_INJECTION_MARKER]: "toggle" });
  const original = advancedOutput(children);
  const result = injectAdvancedDisplayHdrControls(
    original,
    element(OtherControl),
    element(OtherControl),
  );
  assert.equal(result.status, "partial-injection");
  assert.equal(result.tree, original);
});

test("route render patch registry replaces and releases stale wrappers", () => {
  const registry = new RouteRenderPatchRegistry();
  const releases = [];
  const first = { unpatch: () => releases.push("first") };
  const second = { unpatch: () => releases.push("second") };
  const direct = { unpatch: () => releases.push("direct") };

  registry.replace("settings-root", first);
  registry.replace("direct-display", direct);
  registry.replace("settings-root", second);

  assert.deepEqual(releases, ["first"]);
  assert.equal(registry.size, 2);

  registry.releaseAll();
  assert.deepEqual(releases, ["first", "direct", "second"]);
  assert.equal(registry.size, 0);
});

test("route render patch registry skips already-unpatched handles and contains release errors", () => {
  const registry = new RouteRenderPatchRegistry();
  const errors = [];
  let skippedCalls = 0;
  registry.replace("already", {
    hasUnpatched: true,
    unpatch: () => { skippedCalls += 1; },
  });
  registry.replace("throws", {
    unpatch: () => { throw new Error("release failed"); },
  });

  registry.releaseAll((key, error) => errors.push([key, String(error)]));

  assert.equal(skippedCalls, 0);
  assert.deepEqual(errors, [["throws", "Error: release failed"]]);
  assert.equal(registry.size, 0);
});

test("SystemPerfStore bootstrap recognizes only the callable brightness API", () => {
  assert.equal(isSystemPerfStoreReady(undefined), false);
  assert.equal(isSystemPerfStoreReady({}), false);
  assert.equal(isSystemPerfStoreReady({ SetHDRSDRContentBrightness: true }), false);
  assert.equal(isSystemPerfStoreReady({ SetHDRSDRContentBrightness() {} }), true);
});

test("SystemPerfStore bootstrap is one-shot and bounded", () => {
  const readyStore = { SetHDRSDRContentBrightness() {} };

  assert.equal(shouldKeepSystemPerfStoreBootstrap(undefined, 0), true);
  assert.equal(
    shouldKeepSystemPerfStoreBootstrap(
      undefined,
      SYSTEM_PERF_STORE_BOOTSTRAP_TIMEOUT_MS - 1,
    ),
    true,
  );
  assert.equal(shouldKeepSystemPerfStoreBootstrap(readyStore, 0), false);
  assert.equal(
    shouldKeepSystemPerfStoreBootstrap(
      undefined,
      SYSTEM_PERF_STORE_BOOTSTRAP_TIMEOUT_MS,
    ),
    false,
  );
  assert.equal(shouldKeepSystemPerfStoreBootstrap(undefined, Number.NaN), false);
});
