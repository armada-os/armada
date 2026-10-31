import assert from "node:assert/strict";
import test from "node:test";
import { createContentFixture } from "./helpers/content.ts";

const games = [{ appid: "1", name: "First game" }, { appid: "2", name: "Second game" }];

async function setup() {
  const app = createContentFixture({ games, autoLoad: true });
  await app.settle();
  return app;
}

test("startup without a game preserves automatic following through runtime changes and config reload", async () => {
  const app = await setup();
  assert.equal(app.config.selectedGame, undefined);
  app.setRuntime(games[0]);
  assert.equal(app.config.game.appid, "1");
  assert.equal(app.config.selectedGame, undefined);
  await app.reload();
  await app.settle();
  assert.equal(app.config.selectedGame, undefined);
  app.setRuntime(games[1]);
  assert.equal(app.config.game.appid, "2");
  assert.equal(app.config.selectedGame, undefined);
});

test("manual selection and explicit clearing survive runtime changes and config reload", async () => {
  const app = await setup();
  app.setRuntime(games[0]);
  app.select(games[1]);
  await app.reload();
  await app.settle();
  assert.equal(app.config.selectedGame.appid, "2");
  app.setRuntime(null);
  assert.equal(app.config.selectedGame.appid, "2");
  app.select(null);
  app.setRuntime(games[0]);
  await app.reload();
  await app.settle();
  assert.equal(app.config.game.appid, "1");
  assert.equal(app.config.selectedGame, null);
});
