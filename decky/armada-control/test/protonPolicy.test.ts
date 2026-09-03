import assert from "node:assert/strict";
import test from "node:test";

import {
  defaultWindowsCompatTool,
  factoryDefaultTransition,
} from "../src/lib/protonPolicy.ts";

const tool = (id: string) => ({ id, label: id });
const experimental = "proton-experimental-arm64";
const stable = "proton_11-arm64";
const cachyos = "proton-cachyos-11.0-arm64";
const defaults = [experimental, stable, cachyos];

test("candidate order wins over Steam-reported tool order", () => {
  assert.equal(defaultWindowsCompatTool([
    tool(cachyos),
    tool(stable),
    tool(experimental),
  ], defaults), experimental);
});

test("missing candidates are skipped", () => {
  assert.equal(defaultWindowsCompatTool([
    tool(stable),
    tool(cachyos),
  ], defaults), stable);
});

test("a device-specific list can require CachyOS", () => {
  assert.equal(defaultWindowsCompatTool([
    tool(experimental),
    tool(cachyos),
  ], [cachyos]), cachyos);
});

test("no unavailable candidate is selected", () => {
  assert.equal(defaultWindowsCompatTool([
    tool("proton_experimental"),
    tool("proton-stable"),
  ], defaults), "");
});

test("legacy factory default transitions from CachyOS", () => {
  assert.deepEqual(
    factoryDefaultTransition(undefined, true, "", experimental),
    { oldTool: cachyos, newTool: experimental },
  );
  assert.deepEqual(
    factoryDefaultTransition(undefined, true, "", cachyos),
    { oldTool: cachyos, newTool: cachyos },
  );
});

test("stored factory default is used for later transitions", () => {
  assert.deepEqual(
    factoryDefaultTransition(undefined, true, stable, experimental),
    { oldTool: stable, newTool: experimental },
  );
});

test("factory transition requires trusted state and a resolved implicit default", () => {
  assert.equal(factoryDefaultTransition(cachyos, true, stable, experimental), null);
  assert.equal(factoryDefaultTransition(undefined, false, stable, experimental), null);
  assert.equal(factoryDefaultTransition(undefined, true, stable, ""), null);
  assert.equal(factoryDefaultTransition(undefined, true, experimental, experimental), null);
});
