const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../decky/armada-store');
const ts = require(path.join(root, 'node_modules/typescript'));
const code = ts.transpileModule(fs.readFileSync(path.join(root, 'src/lib/shortcuts.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
let added = 0, fail = true, created;
const context = { exports: {}, window: { SteamClient: { Apps: {
  AddShortcut: async () => { added++; return 123; },
  SpecifyCompatTool: async () => { if (fail) throw Error('temporary failure'); },
} } } };
vm.runInNewContext(code, context);
(async () => {
  const launch = { name: 'Example', exe: '/apps/base.apk', startDir: '/apps', launchOptions: '', compatTool: 'lepton_armada' };
  await assert.rejects(context.exports.addToSteam(launch, undefined, id => { created = id; }), /temporary failure/);
  assert.equal(created, 123);
  fail = false;
  assert.equal(await context.exports.addToSteam(launch, created), 123);
  assert.equal(added, 1);
  assert.equal(context.exports.shortcutGameId(123), ((123n << 32n) | 0x02000000n).toString());
  console.log('Store shortcut retry tests passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
