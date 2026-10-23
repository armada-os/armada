import { Dropdown, replacePatch } from "@decky/ui";
import { detectLocaleFromEnvironment, resolveLocale, type Locale } from "../i18n";
import {
  localizePerformanceProfileOptions,
  type PerformanceProfileOption,
} from "./performanceProfileLabels";

type ButtonValueRenderer = (value: unknown) => unknown;

type DropdownProps = {
  rgOptions?: PerformanceProfileOption[];
  renderButtonValue?: ButtonValueRenderer;
} & Record<string, unknown>;

type DropdownInstance = {
  props: DropdownProps;
};

type DropdownMethod = (this: DropdownInstance, ...args: unknown[]) => unknown;

type ReplaceableDropdownPrototype = {
  render?: DropdownMethod;
  BuildMenu?: DropdownMethod;
};

type MethodPatch = {
  original: DropdownMethod;
  unpatch: () => void;
};

type SteamSettings = {
  GetCurrentLanguage?: () => Promise<unknown> | unknown;
};

function readSteamLanguage(): Promise<unknown> {
  const steamClient = (window as unknown as {
    SteamClient?: { Settings?: SteamSettings };
  }).SteamClient;
  try {
    return Promise.resolve(steamClient?.Settings?.GetCurrentLanguage?.());
  } catch (error) {
    return Promise.resolve(undefined);
  }
}

// Uncontrolled dropdowns cache the English selected option in state, so the
// button label only reaches translated text through the renderButtonValue hook.
function localizeButtonValue(
  original: PerformanceProfileOption[],
  localized: PerformanceProfileOption[],
  renderButtonValue: ButtonValueRenderer | undefined,
): ButtonValueRenderer {
  return (value) => {
    let label = value;
    if (typeof value === "string") {
      const index = original.findIndex(
        (option) => option.label === value || option.data === value,
      );
      if (index !== -1) label = localized[index].label;
    }
    return renderButtonValue ? renderButtonValue(label) : label;
  };
}

export function registerSteamProfileLocalization(): () => void {
  const prototype = (Dropdown as unknown as {
    prototype?: ReplaceableDropdownPrototype;
  }).prototype;
  if (!prototype || typeof prototype.render !== "function" || typeof prototype.BuildMenu !== "function") {
    return () => {};
  }

  let locale: Locale = detectLocaleFromEnvironment();
  let alive = true;

  const patchMethod = (name: "render" | "BuildMenu"): MethodPatch => {
    let patch: MethodPatch;
    const handler = function (this: DropdownInstance, args: unknown[]) {
      const props = this.props;
      const options = props?.rgOptions;
      const localized = localizePerformanceProfileOptions(options, locale);
      if (!props || !options || !localized || localized === options) {
        return patch.original.apply(this, args);
      }
      this.props = name === "render"
        ? {
            ...props,
            rgOptions: localized,
            renderButtonValue: localizeButtonValue(options, localized, props.renderButtonValue),
          }
        : { ...props, rgOptions: localized };
      try {
        return patch.original.apply(this, args);
      } finally {
        this.props = props;
      }
    };
    patch = replacePatch(prototype, name, handler) as unknown as MethodPatch;
    return patch;
  };

  const patches = [patchMethod("render"), patchMethod("BuildMenu")];

  readSteamLanguage()
    .then((language) => {
      if (!alive) return;
      locale = resolveLocale({ steamLanguage: language, deckyLocales: [locale] });
    })
    .catch(() => {});

  return () => {
    if (!alive) return;
    alive = false;
    for (const patch of patches.reverse()) patch.unpatch();
  };
}
