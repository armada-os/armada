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
  ["en", "zh-CN"].map(async (locale) => [
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
  detectLocaleFromEnvironment,
  setCurrentLocale,
  getCurrentLocale,
  translate,
  t,
} = await import(moduleUrl);

// Dictionary parity: identical keys and identical {placeholders} in both locales.
assert.deepEqual(Object.keys(localeStrings["zh-CN"]), Object.keys(localeStrings.en));
const placeholders = (text) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
for (const key of Object.keys(localeStrings.en)) {
  assert.deepEqual(
    placeholders(localeStrings["zh-CN"][key]),
    placeholders(localeStrings.en[key]),
    `placeholder mismatch for ${key}`,
  );
}

// Simplified Chinese aliases, casing, and underscore separators.
assert.equal(localeFromLanguage("english"), "en");
assert.equal(localeFromLanguage("schinese"), "zh-CN");
assert.equal(localeFromLanguage("SteamChina_SChinese"), "zh-CN");
assert.equal(localeFromLanguage("SChinese"), "zh-CN");
assert.equal(localeFromLanguage("zh"), "zh-CN");
assert.equal(localeFromLanguage("zh-CN"), "zh-CN");
assert.equal(localeFromLanguage("zh-Hans"), "zh-CN");
assert.equal(localeFromLanguage("zh_SG"), "zh-CN");
assert.equal(localeFromLanguage("ZH-cn"), "zh-CN");
// Traditional Chinese and unknown languages fall back to English.
assert.equal(localeFromLanguage("tchinese"), "en");
assert.equal(localeFromLanguage("klingon"), "en");
// Empty and non-string inputs resolve to nothing.
assert.equal(localeFromLanguage(""), null);
assert.equal(localeFromLanguage("   "), null);
assert.equal(localeFromLanguage(null), null);
assert.equal(localeFromLanguage(undefined), null);
assert.equal(localeFromLanguage(42), null);

// Precedence: Steam beats Decky, Decky beats the browser, then English.
assert.equal(resolveLocale({ steamLanguage: "english", deckyLocales: ["zh-cn"], browserLanguages: ["zh-CN"] }), "en");
assert.equal(resolveLocale({ steamLanguage: "schinese", deckyLocales: ["en-us"], browserLanguages: ["en-US"] }), "zh-CN");
assert.equal(resolveLocale({ deckyLocales: ["zh-cn"], browserLanguages: ["en-US"] }), "zh-CN");
assert.equal(resolveLocale({ browserLanguages: ["zh-CN", "en-US"] }), "zh-CN");
assert.equal(resolveLocale({ browserLanguages: ["en-US"] }), "en");
// English or unknown Steam languages resolve to English instead of deferring.
assert.equal(resolveLocale({ steamLanguage: "klingon", deckyLocales: ["zh-CN"] }), "en");
// An empty Steam language defers to Decky, then the browser.
assert.equal(resolveLocale({ steamLanguage: "", deckyLocales: ["zh-cn"] }), "zh-CN");
assert.equal(resolveLocale({ steamLanguage: "  ", browserLanguages: ["zh-CN"] }), "zh-CN");
assert.equal(resolveLocale({}), "en");

// Environment detection: Decky locales outrank the browser, with English as the floor.
function overrideGlobals(values, run) {
  const saved = [];
  for (const [name, value] of Object.entries(values)) {
    saved.push([name, Object.getOwnPropertyDescriptor(globalThis, name)]);
    Object.defineProperty(globalThis, name, { value, configurable: true, writable: true, enumerable: true });
  }
  try {
    return run();
  } finally {
    for (const [name, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
  }
}

function removeGlobals(names, run) {
  const saved = names.map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)]);
  for (const [name] of saved) {
    try {
      delete globalThis[name];
    } catch (error) {
    }
  }
  try {
    return run();
  } finally {
    for (const [name, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
    }
  }
}

removeGlobals(["window", "navigator"], () => assert.equal(detectLocaleFromEnvironment(), "en"));
overrideGlobals(
  { window: { LocalizationManager: { m_rgLocalesToUse: ["zh-CN"] } }, navigator: { languages: ["en-US"], language: "en-US" } },
  () => assert.equal(detectLocaleFromEnvironment(), "zh-CN"),
);
overrideGlobals(
  { window: {}, navigator: { languages: ["zh-CN"], language: "zh-CN" } },
  () => assert.equal(detectLocaleFromEnvironment(), "zh-CN"),
);
overrideGlobals(
  { window: {}, navigator: { language: "en-US" } },
  () => assert.equal(detectLocaleFromEnvironment(), "en"),
);

// Translations and interpolation (every occurrence and numeric zero).
assert.equal(translate("en", "common.loading"), "Loading");
assert.equal(translate("zh-CN", "common.failed"), "操作失败");
assert.equal(translate("zh-CN", "jobs.resolving"), "正在查找版本");
assert.equal(translate("en", "actions.replaceVersion", { kind: "Flatpak" }), "Replace Flatpak version");
assert.equal(translate("zh-CN", "actions.replaceVersion", { kind: "Flatpak" }), "替换 Flatpak 版本");
assert.equal(translate("en", "actions.replaceVersion", { kind: 0 }), "Replace 0 version");

const probeKey = "__interpolate_probe";
localeStrings.en[probeKey] = "{a} + {a} = {b}";
localeStrings["zh-CN"][probeKey] = "{a} + {a} = {b}";
assert.equal(translate("en", probeKey, { a: 0, b: 0 }), "0 + 0 = 0");
assert.equal(translate("zh-CN", probeKey, { a: 1, b: 2 }), "1 + 1 = 2");
delete localeStrings.en[probeKey];
delete localeStrings["zh-CN"][probeKey];

// Module-level current locale and t().
assert.equal(getCurrentLocale(), "en");
setCurrentLocale("zh-CN");
assert.equal(getCurrentLocale(), "zh-CN");
assert.equal(t("common.cancel"), "取消");
assert.equal(t("actions.install"), "安装");
setCurrentLocale("en");
assert.equal(t("actions.install"), "Install");

console.log("i18n tests passed: dictionary parity, locales, precedence, environment, interpolation, and module locale");
