import assert from "node:assert/strict";
import test from "node:test";
import { findPreset, localized, resolveEnvValues } from "../src/lib/envPresets.ts";
import type { EnvPreset } from "../src/types.ts";

// The factory list itself is data now, checked against the real file by
// tests/env-presets-test.sh. What is left here is the code that reads it.
const presets: EnvPreset[] = [
  { name: "VKD3D_SHADER_MODEL", description: { en: "Highest shader model." }, options: [
    { data: "6_0", label: "6_0 - Shader Model 6.0" },
  ] },
  { name: "DXVK_FRAME_RATE", description: "Frame limit.", example: "60" },
];

// Variable names are case sensitive, so a near miss must not resolve to a preset
// and hand the user a dropdown for a variable they did not name.
test("findPreset matches the exact name and nothing else", () => {
  assert.equal(findPreset(presets, "VKD3D_SHADER_MODEL")?.name, "VKD3D_SHADER_MODEL");
  assert.equal(findPreset(presets, "vkd3d_shader_model"), undefined);
  assert.equal(findPreset(presets, "VKD3D_SHADER_MODEL "), undefined);
  assert.equal(findPreset(presets, "MY_OWN_VARIABLE"), undefined);
  assert.equal(findPreset(presets, ""), undefined);
  assert.equal(findPreset([], "VKD3D_SHADER_MODEL"), undefined);
});

// A label with no text to translate ships as a bare string, so the reader must
// take both shapes or half the dropdown comes out blank.
test("localized takes a bare string as the text for every locale", () => {
  assert.equal(localized("6_0 - Shader Model 6.0", "zh-CN"), "6_0 - Shader Model 6.0");
  assert.equal(localized("6_0 - Shader Model 6.0", "en"), "6_0 - Shader Model 6.0");
});

// An admin adding a variable to /etc/armada writes the language they speak. The
// panel must still show something in the other three.
test("localized falls back to English, then to nothing at all", () => {
  const text = { en: "Frame limit.", "pt-BR": "Limite de quadros." };
  assert.equal(localized(text, "pt-BR"), "Limite de quadros.");
  assert.equal(localized(text, "zh-CN"), "Frame limit.");
  assert.equal(localized({ "pt-BR": "Limite de quadros." }, "zh-CN"), "");
  assert.equal(localized(undefined, "en"), "");
});

// The picker prefills from whatever the variable is set to today, so the user
// adjusts the current setting instead of retyping it.
test("resolveEnvValues prefers the profile's own value over the inherited one", () => {
  const own = { DXVK_FRAME_RATE: "45" };
  const global = { DXVK_FRAME_RATE: "60", VKD3D_FRAME_RATE: "30" };
  assert.deepEqual(resolveEnvValues(own, global), { DXVK_FRAME_RATE: "45", VKD3D_FRAME_RATE: "30" });
});

// A null is the tombstone that unchecks an inherited variable. Reading it as a
// value would prefill the picker with an empty string and wipe the global setting.
test("resolveEnvValues falls through a tombstone to the inherited value", () => {
  assert.deepEqual(resolveEnvValues({ DXVK_FRAME_RATE: null }, { DXVK_FRAME_RATE: "60" }), { DXVK_FRAME_RATE: "60" });
  assert.deepEqual(resolveEnvValues({ MY_OWN_VARIABLE: null }, {}), {});
});
