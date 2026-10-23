import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { Buffer } from "node:buffer";
import test from "node:test";
import ts from "typescript";

import type { Locale } from "../src/i18n.ts";
import type { PerformanceProfileOption } from "../src/lib/performanceProfileLabels.ts";

type Localize = <T extends PerformanceProfileOption>(
  options: T[] | undefined,
  locale: Locale,
) => T[] | undefined;

const compilerOptions = {
  module: ts.ModuleKind.ESNext,
  target: ts.ScriptTarget.ES2020,
};

async function transpile(relativePath: string): Promise<string> {
  const source = await readFile(new URL(relativePath, import.meta.url), "utf8");
  return ts.transpileModule(source, { compilerOptions, fileName: relativePath }).outputText;
}

const dataUrl = (output: string) =>
  `data:text/javascript;base64,${Buffer.from(output).toString("base64")}`;

// i18n.ts uses extensionless imports, which node's type stripping cannot resolve.
const localeUrls = Object.fromEntries(await Promise.all(
  ["en", "zh-CN", "pt-BR", "pt-PT"].map(async (locale) => [
    `./locales/${locale}`,
    dataUrl(await transpile(`../src/locales/${locale}.ts`)),
  ]),
));
let i18nOutput = await transpile("../src/i18n.ts");
for (const [modulePath, moduleUrl] of Object.entries(localeUrls)) {
  i18nOutput = i18nOutput.replace(`from "${modulePath}"`, `from "${moduleUrl}"`);
}
const i18nUrl = dataUrl(i18nOutput);

const helperOutput = (await transpile("../src/lib/performanceProfileLabels.ts")).replace(
  'from "../i18n"',
  `from "${i18nUrl}"`,
);
const helperUrl = dataUrl(helperOutput);
const { localizePerformanceProfileOptions } = await import(helperUrl) as {
  localizePerformanceProfileOptions: Localize;
};

type Option = PerformanceProfileOption & {
  data: string;
  label: string;
  icon?: string;
  onSelect?: () => void;
};

const nativeOptions = (): Option[] => [
  { data: "Eco", label: "Eco", icon: "eco.svg" },
  { data: "Balanced", label: "Balanced", icon: "balanced.svg" },
  { data: "Performance", label: "Performance", icon: "performance.svg" },
];

test("translates labels and keeps native data, order, and metadata", () => {
  const onSelect = () => {};
  const options = nativeOptions();
  options[0].onSelect = onSelect;
  const localized = localizePerformanceProfileOptions(options, "zh-CN");
  assert.ok(localized);
  assert.deepEqual(localized.map((option) => option.label), ["节能", "均衡", "性能"]);
  assert.deepEqual(localized.map((option) => option.data), ["Eco", "Balanced", "Performance"]);
  assert.deepEqual(localized.map((option) => option.icon), ["eco.svg", "balanced.svg", "performance.svg"]);
  assert.equal(localized[0].onSelect, onSelect);
  assert.notEqual(localized, options);
  assert.notEqual(localized[0], options[0]);
});

test("does not mutate the original options", () => {
  const options = nativeOptions();
  const before = JSON.stringify(options);
  localizePerformanceProfileOptions(options, "zh-CN");
  assert.equal(JSON.stringify(options), before);
  assert.equal(options[0].label, "Eco");
});

test("English leaves the dropdown untouched", () => {
  const options = nativeOptions();
  assert.equal(localizePerformanceProfileOptions(options, "en"), options);
});

test("accepts a shuffled native order", () => {
  const options = nativeOptions();
  const shuffled = [options[2], options[0], options[1]];
  const localized = localizePerformanceProfileOptions(shuffled, "zh-CN");
  assert.ok(localized);
  assert.deepEqual(localized.map((option) => option.label), ["性能", "节能", "均衡"]);
  assert.deepEqual(localized.map((option) => option.data), ["Performance", "Eco", "Balanced"]);
});

test("rejects custom labels on native data", () => {
  const options = nativeOptions();
  options[0] = { ...options[0], label: "Eco Mode" };
  assert.equal(localizePerformanceProfileOptions(options, "zh-CN"), options);
});

test("rejects unknown profile data", () => {
  const options = nativeOptions();
  options[2] = { data: "Turbo", label: "Turbo", icon: "turbo.svg" };
  assert.equal(localizePerformanceProfileOptions(options, "zh-CN"), options);
});

test("rejects unrelated dropdowns that reuse the same words", () => {
  const lowercase = [
    { data: "eco", label: "eco" },
    { data: "balanced", label: "balanced" },
    { data: "performance", label: "performance" },
  ];
  assert.equal(localizePerformanceProfileOptions(lowercase, "zh-CN"), lowercase);

  const duplicated = [
    { data: "Eco", label: "Eco" },
    { data: "Eco", label: "Eco" },
    { data: "Eco", label: "Eco" },
  ];
  assert.equal(localizePerformanceProfileOptions(duplicated, "zh-CN"), duplicated);
});

test("rejects dropdowns that are not exactly three options", () => {
  const options = nativeOptions();
  const two = options.slice(0, 2);
  assert.equal(localizePerformanceProfileOptions(two, "zh-CN"), two);
  assert.equal(localizePerformanceProfileOptions([], "zh-CN")?.length, 0);
  assert.equal(localizePerformanceProfileOptions(undefined, "zh-CN"), undefined);
});

// Stand-in for @decky/ui: Dropdown instance hooks plus the loader's replacePatch ABI.
const uiModuleSource = `
let installed = 0;
export class Dropdown {
  constructor(props) {
    this.props = props;
    this.state = {
      value: (props.rgOptions || []).find((option) => option.data === props.selectedOption),
    };
  }
  render(...args) {
    if (this.failWith) throw this.failWith;
    let buttonLabel = this.state.value?.label ?? this.props.strDefaultLabel;
    if (this.props.renderButtonValue != null) {
      buttonLabel = this.props.renderButtonValue(buttonLabel);
    }
    return { hook: "render", args, options: this.props.rgOptions, buttonLabel };
  }
  BuildMenu(...args) {
    if (this.failWith) throw this.failWith;
    return { hook: "BuildMenu", args, options: this.props.rgOptions };
  }
}
export function replacePatch(target, name, handler) {
  const original = target[name];
  const wrapper = function (...args) {
    return handler.call(this, args);
  };
  target[name] = wrapper;
  installed += 1;
  let live = true;
  return {
    original,
    unpatch() {
      if (!live || target[name] !== wrapper) return;
      live = false;
      target[name] = original;
      installed -= 1;
    },
  };
}
export function installedPatchCount() {
  return installed;
}
`;
const uiUrl = dataUrl(uiModuleSource);

let integrationOutput = await transpile("../src/lib/steamProfileLocalization.ts");
for (const [specifier, moduleUrl] of [
  ["@decky/ui", uiUrl],
  ["../i18n", i18nUrl],
  ["./performanceProfileLabels", helperUrl],
] as const) {
  for (const quote of ['"', "'"]) {
    integrationOutput = integrationOutput.replace(`${quote}${specifier}${quote}`, `"${moduleUrl}"`);
  }
}

type HookResult = {
  hook: string;
  args: unknown[];
  options: Array<{ data?: unknown; label?: unknown; icon?: unknown; onSelect?: unknown }>;
  buttonLabel?: unknown;
};

type FakeDropdown = {
  props: Record<string, unknown>;
  state: { value?: { data?: unknown; label?: unknown } };
  failWith?: Error;
  render: (...args: unknown[]) => HookResult;
  BuildMenu: (...args: unknown[]) => HookResult;
};

type UiModule = {
  Dropdown: { prototype: FakeDropdown; new (props: Record<string, unknown>): FakeDropdown };
  installedPatchCount: () => number;
};

const ui = await import(uiUrl) as UiModule;
const { registerSteamProfileLocalization } = await import(dataUrl(integrationOutput)) as {
  registerSteamProfileLocalization: () => () => void;
};

test("localizes both native dropdown hooks through the real prototype", async () => {
  const globalRecord = globalThis as { window?: unknown };
  const savedWindow = globalRecord.window;
  const steamSettings = { GetCurrentLanguage: () => Promise.resolve("schinese") };
  globalRecord.window = {
    LocalizationManager: { m_rgLocalesToUse: ["schinese"] },
    SteamClient: { Settings: steamSettings },
  };
  try {
    const nativeRender = ui.Dropdown.prototype.render;
    const nativeBuildMenu = ui.Dropdown.prototype.BuildMenu;
    const onSelect = () => {};
    const options = [
      { data: "Eco", label: "Eco", icon: "eco.svg", onSelect },
      { data: "Balanced", label: "Balanced", icon: "balanced.svg" },
      { data: "Performance", label: "Performance", icon: "performance.svg" },
    ];
    const props = {
      rgOptions: options,
      selectedOption: "Eco",
      strDefaultLabel: "Profile",
    };

    let unregister = registerSteamProfileLocalization();
    await Promise.resolve();
    assert.equal(ui.installedPatchCount(), 2);
    assert.notEqual(ui.Dropdown.prototype.render, nativeRender);

    const dropdown = new ui.Dropdown(props);
    for (const hook of ["render", "BuildMenu"] as const) {
      const result = dropdown[hook]("forwarded", 7);
      assert.equal(result.hook, hook);
      assert.deepEqual(result.args, ["forwarded", 7]);
      assert.deepEqual(result.options.map((option) => option.label), ["节能", "均衡", "性能"]);
      assert.deepEqual(result.options.map((option) => option.data), ["Eco", "Balanced", "Performance"]);
      assert.deepEqual(result.options.map((option) => option.icon), ["eco.svg", "balanced.svg", "performance.svg"]);
      assert.equal(result.options[0].onSelect, onSelect);
      // Cached selected option is English; only the button callback can translate it.
      assert.equal(result.buttonLabel, hook === "render" ? "节能" : undefined);
      assert.equal(dropdown.state.value, options[0]);
      assert.equal(dropdown.state.value.label, "Eco");
      assert.equal(dropdown.props, props);
      assert.equal(props.rgOptions, options);
      assert.equal(options[0].label, "Eco");
      assert.equal(props.selectedOption, "Eco");
    }

    let formatterCalls = 0;
    const formatter = (value: unknown) => {
      formatterCalls += 1;
      return `[${value}]`;
    };
    const formatted = new ui.Dropdown({ ...props, renderButtonValue: formatter });
    assert.equal(formatted.render().buttonLabel, "[节能]");
    assert.equal(formatterCalls, 1);
    assert.equal(formatted.state.value, options[0]);
    assert.equal(formatted.props.renderButtonValue, formatter);
    assert.equal("renderButtonValue" in props, false);

    const failing = new ui.Dropdown(props);
    failing.failWith = new Error("native render failed");
    assert.throws(() => failing.render(), /native render failed/);
    assert.equal(failing.props, props);
    assert.equal(failing.state.value, options[0]);

    unregister();
    assert.equal(ui.installedPatchCount(), 0);
    assert.equal(ui.Dropdown.prototype.render, nativeRender);
    assert.equal(ui.Dropdown.prototype.BuildMenu, nativeBuildMenu);
    const restored = new ui.Dropdown(props);
    assert.deepEqual(restored.render().options.map((option) => option.label), ["Eco", "Balanced", "Performance"]);
    assert.equal(restored.render().buttonLabel, "Eco");
    assert.equal(restored.props, props);

    unregister = registerSteamProfileLocalization();
    assert.equal(ui.installedPatchCount(), 2);
    assert.deepEqual(
      new ui.Dropdown(props).BuildMenu().options.map((option) => option.label),
      ["节能", "均衡", "性能"],
    );
    unregister();
    assert.equal(ui.installedPatchCount(), 0);

    // Steam language wins over the Chinese Decky fallback, including unsupported languages.
    for (const steamLanguage of ["english", "german"]) {
      steamSettings.GetCurrentLanguage = () => Promise.resolve(steamLanguage);
      unregister = registerSteamProfileLocalization();
      await Promise.resolve();
      await Promise.resolve();
      assert.equal(ui.installedPatchCount(), 2);
      const english = new ui.Dropdown(props);
      for (const hook of ["render", "BuildMenu"] as const) {
        const result = english[hook]("forwarded", 7);
        assert.equal(result.hook, hook);
        assert.deepEqual(result.args, ["forwarded", 7]);
        assert.equal(result.options, options);
        assert.deepEqual(result.options.map((option) => option.label), ["Eco", "Balanced", "Performance"]);
        assert.deepEqual(result.options.map((option) => option.data), ["Eco", "Balanced", "Performance"]);
        assert.equal(english.props, props);
        assert.equal(props.rgOptions, options);
        assert.equal(options[0].label, "Eco");
      }
      unregister();
      assert.equal(ui.installedPatchCount(), 0);
    }
  } finally {
    if (savedWindow === undefined) delete globalRecord.window;
    else globalRecord.window = savedWindow;
  }
});
