import assert from "node:assert/strict";
import test from "node:test";
import { elements } from "./helpers/elements.ts";
import { loadModule } from "./helpers/loadModule.ts";
import { configChanges } from "../src/lib/configPatch.ts";
import { createConfigMutation, markConfigFieldChange, readAfterPendingConfigMutations, recordConfigFieldRead } from "../src/lib/configMutation.ts";

function owner(controllerType = "deck-uhid") {
  let config: any = { controllerType, sshEnabled: false };
  const set: any = (update: (current: any) => any) => { config = update(config); };
  return { set, get config() { return config; }, replace: (value: any) => { config = value; } };
}

const settle = () => new Promise((resolve) => setImmediate(resolve));

test("queued choices preserve newer intent and unrelated edits, and roll back to the last confirmed value", async () => {
  const app = owner();
  const writes: Array<ReturnType<typeof Promise.withResolvers<string>>> = [];
  const save = createConfigMutation("controllerType", () => {
    const request = Promise.withResolvers<string>();
    writes.push(request);
    return request.promise;
  });
  const first = save(app.config, app.set, "xbox");
  const second = save(app.config, app.set, "dualsense");
  app.set((current: any) => ({ ...current, sshEnabled: true }));
  await settle();
  assert.equal(writes.length, 1);
  writes[0].resolve("applied-xbox");
  await first;
  await settle();
  assert.equal(app.config.controllerType, "dualsense");
  writes[1].reject(new Error("latest write failed"));
  await second;
  assert.equal(app.config.controllerType, "applied-xbox");
  assert.equal(app.config.sshEnabled, true);
  app.replace({ ...app.config, controllerType: "external" });
  recordConfigFieldRead(app.set, "controllerType", "external");
  const next = save(app.config, app.set, "xbox");
  await settle();
  writes[2].reject(new Error("write after refresh failed"));
  await next;
  assert.equal(app.config.controllerType, "external");
});

test("confirmed writes and recovery finish before reopened reads, including nonoptimistic settings", async () => {
  const app = owner();
  app.replace({ ...app.config, sshEnabled: true });
  const write = Promise.withResolvers<boolean>();
  const recovery = Promise.withResolvers<any>();
  const save = createConfigMutation("sshEnabled", () => write.promise, { optimistic: false, read: () => recovery.promise });
  const pending = save(app.config, app.set, false);
  let readStarted = false;
  const reopened = readAfterPendingConfigMutations(app.set, ["sshEnabled"], async () => { readStarted = true; return app.config.sshEnabled; });
  await settle();
  assert.equal(app.config.sshEnabled, true);
  write.reject(new Error("write failed"));
  await settle();
  assert.equal(readStarted, false);
  recovery.resolve({ sshEnabled: true });
  await pending;
  assert.equal(await reopened, true);
});

test("different fields and owners do not block each other or recreate closed configuration", async () => {
  const left = owner("left");
  const right = owner("right");
  const writes: Array<ReturnType<typeof Promise.withResolvers<string>>> = [];
  const save = createConfigMutation("controllerType", () => {
    const request = Promise.withResolvers<string>();
    writes.push(request);
    return request.promise;
  });
  const first = save(left.config, left.set, "xbox");
  const second = save(right.config, right.set, "dualsense");
  await settle();
  assert.equal(writes.length, 2);
  assert.equal(await readAfterPendingConfigMutations(left.set, ["sshEnabled"], async () => "ready"), "ready");
  left.replace(null);
  writes[0].resolve("xbox");
  writes[1].reject(new Error("failed"));
  await Promise.all([first, second]);
  assert.equal(left.config, null);
  assert.equal(right.config.controllerType, "right");
});

test("targeted patches retain inheritance masks and safely delete custom environment keys", () => {
  const before = JSON.parse('{"global":{},"games":{"7":{"env":{"__proto__":"value","LOCAL":"1","GLOBAL":null}}}}');
  const after = { global: {}, games: { "7": { env: { GLOBAL: null } } } };
  assert.deepEqual(configChanges(before, after), [
    { path: ["games", "7", "env", "__proto__"], remove: true },
    { path: ["games", "7", "env", "LOCAL"], remove: true },
  ]);
  assert.deepEqual(configChanges({ global: {}, games: {} }, after), [
    { path: ["games", "7", "env", "GLOBAL"], value: null },
  ]);
  assert.deepEqual(configChanges(after, { global: {}, games: {} }), [{ path: ["games", "7"], remove: true }]);
});

test("loaded Controller state distinguishes absent calibration from legacy dates and gates gyro support", () => {
  const { Controller } = loadModule("tabs/Controller.tsx", {
    "@decky/api": {}, "@decky/ui": { PanelSection: "Section" },
    react: { useState: () => [false, () => {}], useRef: (current: any) => ({ current }) },
    "../backend": {}, "../components/Calibration": {},
    "../components/widgets": { ButtonRow: "Button", ReadOnlyRow: "ReadOnly", SelectEdit: "Select", ToggleRow: "Toggle", SectionDescription: "Description" },
    "../i18n": { t: (key: string) => key, translateLabel: (text: string) => text, getCurrentLocale: () => "en" },
    "../lib/configMutation": { createConfigMutation, markConfigFieldChange },
  });
  for (const [hasCalibration, calibratedAt, gyroSupported, expected] of [
    [false, null, true, "common.never"], [true, null, false, "common.unknown"], [true, "2026-10-26T12:00:00Z", true, "Oct 26, 2026"],
  ]) {
    const rows = elements(Controller({ config: { hasCalibration, calibratedAt, gyro: { supported: gyroSupported } }, setConfig: () => {} }));
    assert.equal(rows.find(row => row.type === "ReadOnly").props.description, expected);
    assert.equal(rows.some(row => row.props?.label === "settings.enableGyro"), gyroSupported);
  }
});
