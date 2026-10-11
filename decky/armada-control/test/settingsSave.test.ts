import assert from "node:assert/strict";
import test from "node:test";
import { createDebouncedSave, createSettingsQueue, flushSettingsSaves } from "../src/lib/settingsSave.ts";

const settle = () => new Promise<void>((resolve) => setImmediate(resolve));

function setup() {
  let saved = false;
  const writes: boolean[] = [];
  const completions: Array<() => void> = [];
  const queue = createSettingsQueue();
  const writer = createDebouncedSave({
    snapshot: () => JSON.stringify(saved),
    delay: 900,
    save: (value: boolean) => queue.run(async () => {
      writes.push(value);
      await new Promise<void>((resolve) => completions.push(resolve));
      saved = value;
    }),
    onSaved: () => {},
    onError: (error) => { throw error; },
  });
  return { writer, writes, queue, read: () => saved, complete: () => completions.shift()!() };
}

test("closing before the debounce expires saves only the final edit", async () => {
  const { writer, writes, read, complete } = setup();
  writer.update(true);
  writer.update(false);
  writer.update(true);
  const closed = writer.flush();
  await settle();
  assert.deepEqual(writes, [true]);
  complete();
  await closed;
  assert.equal(read(), true);
});

test("reopening waits for a toggle back queued behind an in-flight save", async () => {
  const { writer, writes, queue, read, complete } = setup();
  writer.update(true);
  const first = writer.flush();
  await settle();
  writer.update(false);
  let reopened = false;
  const loaded = flushSettingsSaves().then(() => queue.run(async () => {
    reopened = true;
    return read();
  }));
  assert.deepEqual(writes, [true]);
  complete();
  await first;
  await settle();
  assert.deepEqual(writes, [true, false]);
  assert.equal(reopened, false);
  complete();
  assert.equal(await loaded, false);
});
