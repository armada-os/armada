import assert from "node:assert/strict";
import test from "node:test";
import {
  HDR_RUNTIME_FALLBACK_MS,
  HdrRuntimeStateCoordinator,
} from "../src/lib/hdrRuntimeStateCoordinator.ts";

function runtime(overrides = {}) {
  return {
    available: true,
    display: ":0",
    supportsHdr: true,
    enabled: false,
    outputFeedback: false,
    sdrContentBrightnessNits: null,
    reason: "ok",
    ...overrides,
  };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

function settle() {
  return new Promise((resolve) => setImmediate(resolve));
}

function timerHarness() {
  let nextId = 1;
  const scheduled = new Map();
  const cancelled = [];
  return {
    scheduled,
    cancelled,
    schedule(callback, delayMs) {
      const id = nextId++;
      scheduled.set(id, { callback, delayMs });
      return id;
    },
    cancel(id) {
      cancelled.push(id);
      scheduled.delete(id);
    },
    run(id) {
      const task = scheduled.get(id);
      assert.ok(task, `timer ${id} is scheduled`);
      scheduled.delete(id);
      task.callback();
    },
  };
}

function coordinator(read, timers = timerHarness()) {
  return {
    timers,
    state: new HdrRuntimeStateCoordinator({
      read,
      schedule: timers.schedule,
      cancel: timers.cancel,
    }),
  };
}

test("two subscribers share one immediate read and one stable snapshot", async () => {
  const firstRead = deferred();
  let reads = 0;
  const { state } = coordinator(() => {
    reads += 1;
    return firstRead.promise;
  });
  const firstUpdates = [];
  const secondUpdates = [];

  const unsubscribeFirst = state.subscribe((snapshot) => firstUpdates.push(snapshot));
  const unsubscribeSecond = state.subscribe((snapshot) => secondUpdates.push(snapshot));
  assert.equal(reads, 1);

  firstRead.resolve(runtime());
  await settle();
  assert.equal(firstUpdates.length, 1);
  assert.equal(secondUpdates.length, 1);
  assert.equal(firstUpdates[0], secondUpdates[0]);
  assert.equal(state.getSnapshot(), firstUpdates[0]);

  unsubscribeFirst();
  unsubscribeSecond();
});

test("manual refreshes deduplicate in flight and notify only for a changed snapshot", async () => {
  const reads = [deferred(), deferred(), deferred()];
  let readIndex = 0;
  const { state } = coordinator(() => reads[readIndex++].promise);
  const updates = [];
  const unsubscribe = state.subscribe((snapshot) => updates.push(snapshot));
  reads[0].resolve(runtime());
  await settle();

  const firstRefresh = state.refresh();
  const duplicateRefresh = state.refresh();
  assert.equal(firstRefresh, duplicateRefresh);
  assert.equal(readIndex, 2);
  reads[1].resolve(runtime());
  await firstRefresh;
  assert.equal(updates.length, 1, "equivalent readback keeps the stable snapshot");

  const changedRefresh = state.refresh();
  reads[2].resolve(runtime({ enabled: true, outputFeedback: true }));
  await changedRefresh;
  assert.equal(updates.length, 2);
  assert.equal(updates[1].runtime.enabled, true);
  unsubscribe();
});

test("the final unsubscribe cancels fallback work and prevents further reads", async () => {
  let reads = 0;
  const { state, timers } = coordinator(async () => {
    reads += 1;
    return runtime();
  });
  const unsubscribeFirst = state.subscribe(() => {});
  const unsubscribeSecond = state.subscribe(() => {});
  await Promise.resolve();
  await settle();
  assert.equal(timers.scheduled.size, 1);
  const timerId = [...timers.scheduled.keys()][0];

  unsubscribeFirst();
  assert.equal(timers.cancelled.length, 0);
  unsubscribeSecond();
  assert.deepEqual(timers.cancelled, [timerId]);
  await state.refresh();
  assert.equal(reads, 1);
});

test("a completion from an unsubscribed generation is never published", async () => {
  const reads = [deferred(), deferred()];
  let readIndex = 0;
  const { state } = coordinator(() => reads[readIndex++].promise);
  const staleUpdates = [];
  const currentUpdates = [];

  const unsubscribeStale = state.subscribe((snapshot) => staleUpdates.push(snapshot));
  unsubscribeStale();
  const unsubscribeCurrent = state.subscribe((snapshot) => currentUpdates.push(snapshot));
  assert.equal(readIndex, 2, "a new generation does not inherit the stale in-flight read");

  reads[0].resolve(runtime({ reason: "stale" }));
  await settle();
  assert.equal(state.getSnapshot().initialized, false);
  assert.equal(staleUpdates.length, 0);
  assert.equal(currentUpdates.length, 0);

  reads[1].resolve(runtime({ reason: "current" }));
  await settle();
  assert.equal(state.getSnapshot().runtime.reason, "current");
  assert.equal(currentUpdates.length, 1);
  unsubscribeCurrent();
});

test("the slow fallback runs only while subscribed and reschedules at five seconds", async () => {
  let reads = 0;
  const { state, timers } = coordinator(async () => {
    reads += 1;
    return runtime({ sdrContentBrightnessNits: reads });
  });
  const unsubscribe = state.subscribe(() => {});
  await settle();

  assert.equal(timers.scheduled.size, 1);
  const firstTimerId = [...timers.scheduled.keys()][0];
  assert.equal(timers.scheduled.get(firstTimerId).delayMs, HDR_RUNTIME_FALLBACK_MS);
  timers.run(firstTimerId);
  await settle();
  assert.equal(reads, 2);
  assert.equal(timers.scheduled.size, 1);
  const secondTimerId = [...timers.scheduled.keys()][0];
  assert.notEqual(secondTimerId, firstTimerId);
  assert.equal(timers.scheduled.get(secondTimerId).delayMs, HDR_RUNTIME_FALLBACK_MS);
  unsubscribe();
});

test("read failures publish a safe snapshot instead of rejecting", async () => {
  const { state } = coordinator(async () => {
    throw new Error("read unavailable");
  });
  const updates = [];
  const unsubscribe = state.subscribe((snapshot) => updates.push(snapshot));
  await settle();
  assert.equal(updates.length, 1);
  assert.equal(updates[0].initialized, true);
  assert.equal(updates[0].runtime, undefined);
  assert.match(updates[0].error, /read unavailable/);
  unsubscribe();
});
