import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./helpers/loadModule.ts";
import { configChanges } from "../src/lib/configPatch.ts";
import * as saves from "../src/lib/configSaveQueue.ts";
const settle = () => new Promise((resolve) => setImmediate(resolve));

function setup() {
  const calls: Array<{ name: string; args: unknown[]; resolve: (value: any) => void; reject: (error: Error) => void }> = [];
  const api = loadModule("backend.ts", {
    "./lib/configPatch": { configChanges },
    "./lib/configSaveQueue": saves,
    "@decky/api": { call: (name: string, ...args: unknown[]) => new Promise((resolve, reject) => { calls.push({ name, args, resolve, reject }); }) },
  });
  return { api, calls };
}

test("startup shares an overlapping request and releases both success and failure for subsequent reads", async () => {
  const { api, calls } = setup();
  const first = api.getStartupConfig();
  assert.equal(api.getStartupConfig(), first);
  await settle();
  assert.equal(calls.length, 1);
  calls[0].resolve({ ready: true });
  await first;
  const failed = api.getStartupConfig();
  const rejected = assert.rejects(failed, /offline/);
  await settle();
  calls[1].reject(new Error("offline"));
  await rejected;
  const retry = api.getStartupConfig();
  await settle();
  calls[2].resolve({ ready: true });
  assert.deepEqual(await retry, { ready: true });
});

test("reopening waits for pending metadata saves while fresh recovery reads remain independent", async () => {
  const { api, calls } = setup();
  let finish!: () => void;
  saves.trackConfigSave(new Promise<void>((resolve) => { finish = resolve; }));
  const startup = api.getStartupConfig();
  const recovery = api.getConfig();
  await settle();
  assert.deepEqual(calls.map((call) => call.name), ["get_config"]);
  calls[0].resolve({ recovered: true });
  await recovery;
  finish();
  await settle();
  assert.equal(calls[1].name, "get_initial_config");
  calls[1].resolve({ ready: true });
  assert.deepEqual(await startup, { ready: true });
});
