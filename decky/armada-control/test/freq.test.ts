import assert from "node:assert/strict";
import test from "node:test";
import { clusterRoles, derivedKhz, indexAtMost, isOverclocked, presetKhz } from "../src/lib/freq.ts";

const ladder = [305, 400, 441, 587, 925];

test("indexAtMost picks the largest entry at or below the value", () => {
  assert.equal(indexAtMost(ladder, 441), 2);
  assert.equal(indexAtMost(ladder, 600), 3);
  assert.equal(indexAtMost(ladder, 100), 0);
});

test("isOverclocked compares against a known stock maximum", () => {
  assert.equal(isOverclocked(650, 587), true);
  assert.equal(isOverclocked(587, 587), false);
  assert.equal(isOverclocked(925, 0), false);
});

test("derivedKhz mirrors the powerd per policy fallback", () => {
  assert.equal(derivedKhz(2841600, 1843200, 0.65, true), 1843200);
  assert.equal(derivedKhz(2841600, undefined, 0.65, true), 2841600);
  assert.equal(derivedKhz(1804800, undefined, 0.65, false), 1173120);
  assert.equal(indexAtMost([300000, 1075200, 1171200, 1420800], 1173120), 2);
});

test("derivedKhz returns top for custom and none even with a preset table", () => {
  const presets = { custom: { cpu_max_policy7: "1670400" }, none: { cpu_max_policy7: "1670400" }, large: { cpu_max_policy7: "1785600" } };
  assert.equal(derivedKhz(2841600, presetKhz(presets, "custom", "cpu_max_policy7"), 0.65, true), 2841600);
  assert.equal(derivedKhz(2841600, presetKhz(presets, "None", "cpu_max_policy7"), 0.65, true), 2841600);
  assert.equal(derivedKhz(2841600, presetKhz(presets, "large", "cpu_max_policy7"), 0.65, true), 1785600);
});

test("clusterRoles names clusters by their top frequency", () => {
  const policy = (id: number, top: number) => ({ id, khz: [300000, top] });
  assert.deepEqual(clusterRoles([policy(0, 1804800), policy(4, 2419200), policy(7, 2649600)]), ["little", "big", "prime"]);
  assert.deepEqual(clusterRoles([policy(0, 1804800), policy(2, 2419200), policy(5, 2208000), policy(7, 2649600)]), ["little", "big2", "big1", "prime"]);
  assert.deepEqual(clusterRoles([policy(0, 3532800), policy(6, 4320000)]), ["big", "prime"]);
  assert.deepEqual(clusterRoles([policy(0, 2016000)]), ["big"]);
  assert.deepEqual(clusterRoles([policy(0, 2016000), policy(4, 2016000)]), ["big1", "big2"]);
});
