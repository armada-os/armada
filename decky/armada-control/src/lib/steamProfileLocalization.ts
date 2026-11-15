import { Dropdown, replacePatch } from "@decky/ui";
import { detectLocaleFromEnvironment, resolveLocale, type Locale } from "../i18n";
import {
  localizePerformanceProfileOptions,
  type PerformanceProfileOption,
} from "./performanceProfileLabels";

type ButtonValueRenderer = (value: unknown) => unknown;

type DropdownProps = {
  setting?: unknown;
  rgOptions?: PerformanceProfileOption[];
  renderButtonValue?: ButtonValueRenderer;
} & Record<string, unknown>;

type SettingFiber = {
  pendingProps?: { setting?: unknown };
  memoizedProps?: { setting?: unknown };
  return?: SettingFiber | null;
};

type DropdownInstance = {
  props: DropdownProps;
  _reactInternals?: SettingFiber;
  forceUpdate?: () => void;
};

export type ProfileLock = {
  // the running game's own profile id while it is in force, else ""
  profile: () => string;
  subscribe: (listener: () => void) => () => void;
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

const PERFORMANCE_PROFILE_SETTING = "steamos_platform_performance_profile";

function isPerformanceProfileDropdown(dropdown: DropdownInstance): boolean {
  if (typeof dropdown.props?.setting === "string") {
    return dropdown.props.setting === PERFORMANCE_PROFILE_SETTING;
  }
  // Steam's setting wrapper consumes `setting` before rendering Dropdown.
  // The nearest setting owner identifies the control without inspecting options.
  for (let owner = dropdown._reactInternals?.return; owner; owner = owner.return) {
    const setting = owner.pendingProps?.setting ?? owner.memoizedProps?.setting;
    if (typeof setting === "string") return setting === PERFORMANCE_PROFILE_SETTING;
  }
  return false;
}

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

export function registerSteamProfileLocalization(lock?: ProfileLock): () => void {
  const prototype = (Dropdown as unknown as {
    prototype?: ReplaceableDropdownPrototype;
  }).prototype;
  if (!prototype || typeof prototype.render !== "function" || typeof prototype.BuildMenu !== "function") {
    return () => {};
  }

  let locale: Locale = detectLocaleFromEnvironment();
  let alive = true;
  let shown: DropdownInstance | undefined;

  const patchMethod = (name: "render" | "BuildMenu"): MethodPatch => {
    let patch: MethodPatch;
    const handler = function (this: DropdownInstance, args: unknown[]) {
      if ((locale === "en" && !lock) || !isPerformanceProfileDropdown(this)) {
        return patch.original.apply(this, args);
      }
      shown = this;
      const gameProfile = lock?.profile() ?? "";
      const props = this.props;
      const options = props?.rgOptions;
      const localized = localizePerformanceProfileOptions(options, locale);
      const translate = !!options && !!localized && localized !== options;
      if (!props || (!translate && !gameProfile)) {
        return patch.original.apply(this, args);
      }
      const next: DropdownProps = { ...props };
      if (translate) {
        next.rgOptions = localized;
        if (name === "render") {
          next.renderButtonValue = localizeButtonValue(options!, localized!, props.renderButtonValue);
        }
      }
      // Changing it while a game runs on its own profile hangs Steam's UI.
      if (gameProfile) {
        next.disabled = true;
        if (name === "render") {
          const option = (next.rgOptions ?? []).find(
            (entry) => typeof entry.data === "string" && entry.data.toLowerCase() === gameProfile,
          );
          const label = `${option?.label ?? gameProfile} · Armada Control`;
          next.renderButtonValue = () => (props.renderButtonValue ? props.renderButtonValue(label) : label);
        }
      }
      this.props = next;
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
  // Steam keeps the dropdown mounted across quick-menu tabs, so a lock change
  // must repaint it or it shows the stale state.
  const unsubscribe = lock?.subscribe(() => shown?.forceUpdate?.()) ?? (() => {});

  readSteamLanguage()
    .then((language) => {
      if (!alive) return;
      locale = resolveLocale({ steamLanguage: language, deckyLocales: [locale] });
    })
    .catch(() => {});

  return () => {
    if (!alive) return;
    alive = false;
    unsubscribe();
    for (const patch of patches.reverse()) patch.unpatch();
  };
}
