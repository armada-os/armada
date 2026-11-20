import assert from "node:assert/strict";
import test from "node:test";
import { createContentFixture as setup } from "./helpers/content.ts";

test("a failed initial load provides a native retry and clears the error while retrying", async () => {
  const app = setup();
  app.requests[0].reject(new Error("connection unavailable"));
  await app.settle();
  assert.equal(app.state.type, "PanelSection");
  assert.equal(app.state.props.title, undefined);
  assert.equal(app.state.props.children[0].props.role, "alert");
  const error = app.state.props.children[0].props.children;
  assert.equal(error.type, "SupportingText");
  assert.match(error.props.children.join(""), /common.loadError: Error: connection unavailable/);
  const retry = app.state.props.children[1];
  assert.equal(retry.type, "ButtonRow");
  assert.equal(retry.props.children, "common.retry");
  retry.props.onClick();
  app.render();
  assert.equal(app.requests.length, 2);
  assert.deepEqual(app.readers, ["startup", "initial"]);
  assert.equal(app.state.type, "LoadingState");
  app.resolve(1);
  await app.settle();
  assert.equal(app.state.type, "TabNavigation");
  assert.equal(app.config.tweaks.global.marker, "loaded");
  app.unmount();
});

test("StrictMode effect replay rejects the old load while preserving later save recovery", async () => {
  const app = setup();
  app.replayEffects();
  assert.equal(app.requests.length, 2);
  app.resolve(0, "discarded mount");
  await app.settle();
  assert.equal(app.state.type, "LoadingState");
  app.resolve(1, "active mount");
  await app.settle();
  assert.equal(app.config.tweaks.global.marker, "active mount");
  const recovery = app.reload();
  app.resolve(2, "recovered");
  await recovery;
  await app.settle();
  assert.equal(app.state.type, "TabNavigation");
  assert.equal(app.config.tweaks.global.marker, "recovered");
  app.unmount();
});

test("recovery preserves an explicit tweak choice changed away and back during its read", async () => {
  const app = setup();
  app.resolve(0);
  await app.settle();
  const recovery = app.reload();
  const setMarker = (marker: string) => app.edit((current) => ({ ...current,
    tweaks: { ...current.tweaks, global: { ...current.tweaks.global, marker } } }));
  setMarker("temporary");
  setMarker("loaded");
  app.resolve(1, "server");
  const result = await recovery;
  assert.equal(result.config.tweaks.global.marker, "loaded");
  assert.equal(result.saved.tweaks.global.marker, "server");
  app.render();
  assert.equal(app.config.tweaks.global.marker, "loaded");
  app.unmount();
});
