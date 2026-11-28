import assert from "node:assert/strict";
import test from "node:test";
import { runGameSettingsMutation } from "../src/lib/gameSettingsQueue.ts";

test("interactive edits wait for the active write, precede queued background work and release the queue on failure", async () => {
  const events: string[] = [];
  let finish!: () => void;
  const active = runGameSettingsMutation(async () => {
    await new Promise<void>((resolve) => { finish = resolve; });
    events.push("active background");
  }, "background");
  const background = runGameSettingsMutation(async () => { events.push("queued background"); }, "background");
  const edit = runGameSettingsMutation(async () => {
    events.push("interactive edit");
    throw new Error("write failed");
  });
  const failure = assert.rejects(edit, /write failed/);
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(events, []);
  finish();
  await Promise.all([active, background, failure]);
  assert.deepEqual(events, ["active background", "interactive edit", "queued background"]);
});
