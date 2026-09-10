import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

const source = readFileSync(new URL("../src/lib/compatManager.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

function setup(ready: Promise<boolean>) {
  const requests: Array<number | undefined> = [];
  const body: { appid?: number } = {};
  const messageClass = {
    Init: () => ({ Body: () => body }),
    InitFromObject: () => {},
    prototype: { SetBodyFields: () => {} },
  };
  const transport = {
    SendMsg: async (method: string, request: any) => {
      assert.equal(method, "CompatManager.GetCompatTools#1");
      requests.push(request.Body().appid);
      return { BSuccess: () => true, Body: () => ({ tools: [] }) };
    },
  };
  const webpack = Object.assign(
    () => ({ getStore: () => ({ GetDefaultTransport: () => transport }) }),
    { m: { transport: () => "Multiple attempts to set a default WebUI transport" } },
  );
  const exports: any = {};
  runInNewContext(compiled, {
    exports,
    require: () => ({ findModuleExport: () => messageClass }),
    window: {
      App: { WaitForServicesInitialized: () => ready },
      webpackChunksteamui: { push: (chunk: any) => chunk[2](webpack) },
    },
  });
  return { requests, getTools: exports.getCompatManagerTools };
}

test("does not send a compatibility request before Steam services initialize", async () => {
  let finish!: (value: boolean) => void;
  const ready = new Promise<boolean>((resolve) => { finish = resolve; });
  const { requests, getTools } = setup(ready);
  const result = getTools();
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(requests, []);
  finish(true);
  await result;
  assert.deepEqual(requests, [undefined]);
});

test("allows per-app requests once Steam services are initialized", async () => {
  const { requests, getTools } = setup(Promise.resolve(true));
  await getTools(391220);
  assert.deepEqual(requests, [391220]);
});

test("does not send a request when Steam initialization fails", async () => {
  const error = new Error("Steam initialization failed");
  const { requests, getTools } = setup(Promise.reject(error));
  await assert.rejects(getTools(), error);
  assert.deepEqual(requests, []);
});
