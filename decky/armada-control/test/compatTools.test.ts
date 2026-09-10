import assert from "node:assert/strict";
import test from "node:test";
import { mapCompatTools, readCompatTools } from "../src/lib/compatTools.ts";

const id = "proton-experimental-arm64";
const label = "Proton Experimental (ARM64)";
const expected = [{ id, label }];
const modern = {
  tools: [{ name: id, display_name: label, is_incompatible: false }],
  aliases: [{ alias: "proton-stable", current_tool_name: "proton_11-arm64" }],
  selected_tool_identifier: "",
  default_tool_identifier: "proton-stable",
};

test("maps the CompatManager response, keeping concrete tool IDs and labels", () => {
  assert.deepEqual(mapCompatTools(modern), expected);
});

test("maps legacy native response fields and falls back to the tool ID for empty labels", () => {
  assert.deepEqual(mapCompatTools([{ strToolName: id, strDisplayName: label }]), expected);
  assert.deepEqual(mapCompatTools([{ strName: id, strDisplayName: "" }]), [{ id, label: id }]);
  assert.deepEqual(mapCompatTools([{ name: id }]), [{ id, label: id }]);
});

test("ignores malformed entries and incompatible tools", () => {
  assert.deepEqual(mapCompatTools({ tools: [null, {}, { name: id, is_incompatible: true }] }), []);
  for (const raw of [null, undefined, {}, { tools: {} }]) assert.deepEqual(mapCompatTools(raw), []);
});

test("uses CompatManager when the beta removes the native methods", async () => {
  const requests: Array<number | undefined> = [];
  const fetch = async (appid?: number) => { requests.push(appid); return modern; };
  assert.deepEqual(await readCompatTools({ Settings: {}, Apps: {} }, fetch), expected);
  assert.deepEqual(await readCompatTools({ Settings: {}, Apps: {} }, fetch, 391220), expected);
  assert.deepEqual(requests, [undefined, 391220]);
});

test("preserves native methods and their receiver on older clients", async () => {
  const fallback = async () => { assert.fail("must use the native API"); };
  const settings = {
    async GetGlobalCompatTools() { assert.equal(this, settings); return [{ strToolName: id, strDisplayName: label }]; },
  };
  const apps = {
    async GetAvailableCompatTools(appid: number) {
      assert.equal(this, apps);
      assert.equal(appid, 391220);
      return [{ strToolName: id, strDisplayName: label }];
    },
  };
  const client = { Settings: settings, Apps: apps };
  assert.deepEqual(await readCompatTools(client, fallback), expected);
  assert.deepEqual(await readCompatTools(client, fallback, 391220), expected);
});

test("does not switch APIs on a legitimate empty native response", async () => {
  const client = { Settings: { GetGlobalCompatTools: async () => [] } };
  assert.deepEqual(await readCompatTools(client, async () => { assert.fail(); }), []);
});

test("propagates discovery failures to the caller's existing cache/error handling", async () => {
  const error = new Error("transport unavailable");
  await assert.rejects(readCompatTools({}, async () => { throw error; }), error);
});
