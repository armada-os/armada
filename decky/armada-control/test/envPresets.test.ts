import assert from "node:assert/strict";
import test from "node:test";
import { envPresets, findPreset, resolveEnvValues } from "../src/lib/envPresets.ts";

// The modal rejects names that are empty or carry '=' or NUL, so a preset that
// broke those rules would be unsaveable from the picker it ships in.
test("every preset name is a saveable variable name, listed once", () => {
  const names = envPresets.map((preset) => preset.name);
  assert.equal(new Set(names).size, names.length, "duplicate preset name");
  for (const name of names) assert.match(name, /^[A-Z][A-Z0-9_]*$/);
});

// The modal picks its value widget from exactly one of these fields. Two of them
// on one preset means the widget chosen silently ignores the other.
test("each preset declares one shape of value: options, a fixed value, or an example", () => {
  for (const preset of envPresets) {
    const shapes = [preset.options, preset.value, preset.example].filter((shape) => shape !== undefined);
    assert.equal(shapes.length, 1, `${preset.name} declares ${shapes.length} value shapes`);
  }
});

// An empty option or label reaches the dropdown as a blank row the user cannot read.
test("no option ships an empty value or an empty label", () => {
  for (const preset of envPresets) {
    for (const option of preset.options || []) {
      assert.notEqual(option.data, "", `${preset.name} has an empty option value`);
      assert.notEqual(option.label, "", `${preset.name} has an empty option label`);
    }
  }
});

// The whole point of the picker is that a name like VKD3D_SHADER_MODEL explains
// itself. A preset without a description is just an acronym in a list.
test("every preset carries the description the docs publish for it", () => {
  for (const preset of envPresets) {
    assert.ok(preset.description.length > 0, `${preset.name} has no description`);
  }
});

// Variable names are case sensitive, so a near miss must not resolve to a preset
// and hand the user a dropdown for a variable they did not name.
test("findPreset matches the exact name and nothing else", () => {
  assert.equal(findPreset("VKD3D_SHADER_MODEL")?.name, "VKD3D_SHADER_MODEL");
  assert.equal(findPreset("vkd3d_shader_model"), undefined);
  assert.equal(findPreset("VKD3D_SHADER_MODEL "), undefined);
  assert.equal(findPreset("MY_OWN_VARIABLE"), undefined);
  assert.equal(findPreset(""), undefined);
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
