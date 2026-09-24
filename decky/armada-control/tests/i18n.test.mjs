import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { Buffer } from "node:buffer";
import ts from "typescript";

const compilerOptions = {
  module: ts.ModuleKind.ESNext,
  target: ts.ScriptTarget.ES2020,
};

async function compileModule(relativePath) {
  const source = await readFile(new URL(relativePath, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions, fileName: relativePath });
  return `data:text/javascript;base64,${Buffer.from(compiled.outputText).toString("base64")}`;
}

const localeModuleUrls = Object.fromEntries(await Promise.all(
  ["en", "zh-CN", "pt-BR", "pt-PT"].map(async (locale) => [
    `./locales/${locale}`,
    await compileModule(`../src/locales/${locale}.ts`),
  ]),
));
const i18nSource = await readFile(new URL("../src/i18n.ts", import.meta.url), "utf8");
let i18nOutput = ts.transpileModule(i18nSource, { compilerOptions, fileName: "i18n.ts" }).outputText;
for (const [modulePath, moduleUrl] of Object.entries(localeModuleUrls)) {
  i18nOutput = i18nOutput.replace(`from "${modulePath}"`, `from "${moduleUrl}"`);
}
const moduleUrl = `data:text/javascript;base64,${Buffer.from(i18nOutput).toString("base64")}`;
const {
  localeStrings,
  localeFromLanguage,
  resolveLocale,
  translate,
  translateLabelForLocale,
} = await import(moduleUrl);

for (const locale of ["zh-CN", "pt-BR", "pt-PT"]) {
  assert.deepEqual(Object.keys(localeStrings[locale]), Object.keys(localeStrings.en));
}

assert.equal(localeFromLanguage("english"), "en");
assert.equal(localeFromLanguage("schinese"), "zh-CN");
assert.equal(localeFromLanguage("SteamChina_SChinese"), "zh-CN");
assert.equal(localeFromLanguage("zh_Hans"), "zh-CN");
assert.equal(localeFromLanguage("pt_BR"), "pt-BR");
assert.equal(localeFromLanguage("brazilian"), "pt-BR");
assert.equal(localeFromLanguage("pt"), "pt-PT");
assert.equal(localeFromLanguage("portuguese"), "pt-PT");
assert.equal(localeFromLanguage("tchinese"), "en");
assert.equal(localeFromLanguage(""), null);

assert.equal(resolveLocale({ steamLanguage: "english", deckyLocales: ["zh-cn"] }), "en");
assert.equal(resolveLocale({ steamLanguage: "schinese", deckyLocales: ["en-us"] }), "zh-CN");
assert.equal(resolveLocale({ deckyLocales: ["zh-cn"], browserLanguages: ["en-US"] }), "zh-CN");
assert.equal(resolveLocale({ browserLanguages: ["zh-CN", "en-US"] }), "zh-CN");
assert.equal(resolveLocale({ steamLanguage: "brazilian", deckyLocales: ["pt-PT"] }), "pt-BR");
assert.equal(resolveLocale({ browserLanguages: ["pt-PT", "en-US"] }), "pt-PT");
assert.equal(resolveLocale({}), "en");

assert.equal(translate("en", "power.cpuGovernor"), "CPU Governor");
assert.equal(translate("zh-CN", "power.cpuGovernor"), "CPU 调频策略");
assert.equal(translate("zh-CN", "games.appFallback", { id: 123 }), "应用 123");
assert.equal(translate("pt-BR", "common.loading"), "Carregando");
assert.equal(translate("pt-PT", "common.loading"), "A carregar");
assert.equal(translate("en", "touchscreen.useDefault", { mode: "Direct touch" }), "Use Default (Direct touch)");
assert.equal(translateLabelForLocale("en", "Balanced"), "Balanced");
assert.equal(translateLabelForLocale("zh-CN", "Balanced"), "均衡");
assert.equal(translateLabelForLocale("zh-CN", "Big Cores (4-7)"), "大核心 (4-7)");
assert.equal(translateLabelForLocale("pt-BR", "Balanced"), "Balanceado");
assert.equal(translateLabelForLocale("pt-PT", "Balanced"), "Equilibrado");
assert.equal(translateLabelForLocale("zh-CN", "Untranslated runtime label"), "Untranslated runtime label");

console.log("i18n tests passed: locale parity, translations, precedence, interpolation, and runtime labels");
